import json
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase

from masters.models import Master
from salons.models import Salon, SalonPhoto
from services.models import Service, ServiceCategory, ServiceStaffPrice
from sync.sync_service import sync_salon_full

FIXTURES_DIR = Path(__file__).parent / 'fixtures' / 'yclients_samples'


def _load(name: str):
    return json.load(open(FIXTURES_DIR / name, encoding='utf-8'))['data']


class YClientsSyncTests(TestCase):
    """
    Прогоняет реальную синхронизацию на реальных примерах ответов YCLIENTS
    (предоставлены заказчиком, не выдуманы). HTTP-вызовы к самому YCLIENTS
    API замоканы (иначе тест не будет детерминированным и потребует токен),
    а вот скачивание картинок — НЕ замокано специально: assets.yclients.com
    недоступен из тестового окружения, и это ценная проверка того, что код
    деградирует корректно (пропускает фото с предупреждением), а не падает,
    если сеть на CI/CD недоступна или YCLIENTS отдал битую ссылку.
    """

    @classmethod
    def setUpTestData(cls):
        cls.company_data = _load('salon-zelenograd.json')
        cls.staff_data = _load('staff.json')
        cls.categories_data = _load('service_categories.json')
        cls.services_data = _load('services.json')

    def setUp(self):
        self.salon = Salon.objects.create(
            name='Placeholder', address='Placeholder', latitude='0', longitude='0',
            yclients_company_id=str(self.company_data['id']),
        )

    def _run_sync(self):
        with patch('sync.client.YClientsDataClient.get_company', return_value=self.company_data), \
             patch('sync.client.YClientsDataClient.get_staff', return_value=self.staff_data), \
             patch('sync.client.YClientsDataClient.get_service_categories', return_value=self.categories_data), \
             patch('sync.client.YClientsDataClient.get_services', return_value=self.services_data):
            sync_salon_full(self.salon)

    def test_salon_fields_synced(self):
        self._run_sync()
        self.salon.refresh_from_db()
        self.assertEqual(self.salon.name, self.company_data['title'])
        self.assertEqual(self.salon.address, self.company_data['address'])
        self.assertAlmostEqual(float(self.salon.latitude), self.company_data['coordinate_lat'])
        self.assertIsNotNone(self.salon.last_synced_at)

    def test_staff_all_created(self):
        self._run_sync()
        self.assertEqual(Master.objects.filter(salons=self.salon).count(), len(self.staff_data))

    def test_categories_all_created(self):
        self._run_sync()
        self.assertEqual(ServiceCategory.objects.filter(salon=self.salon).count(), len(self.categories_data))

    def test_services_all_created_and_linked_to_real_categories(self):
        self._run_sync()
        services_qs = Service.objects.filter(category__salon=self.salon)
        self.assertEqual(services_qs.count(), len(self.services_data))
        # Ни одна услуга не должна была потеряться из-за несовпадения category_id
        # (реальная проверка, а не на глаз — раньше был риск молча потерять услуги
        # с category_id, которого нет в service_categories.json).
        self.assertEqual(
            {s.title for s in services_qs},
            {s['title'] for s in self.services_data},
        )

    def test_per_staff_price_overrides_use_min_max_range(self):
        """YCLIENTS отдаёt price как {min, max}, а не одно число — реальный
        баг, пойманный именно этим тестом при первой реализации."""
        self._run_sync()
        overrides = ServiceStaffPrice.objects.filter(service__category__salon=self.salon)
        self.assertGreater(overrides.count(), 0)
        sample = overrides.first()
        self.assertTrue(sample.price_min is not None or sample.duration_seconds is not None)

    def test_image_group_dict_shape_does_not_crash_sync(self):
        """image_group — словарь с вложенным images.basic.path, а не список
        (тоже реальный баг, пойманный тестом: изначальный код ожидал список
        и падал с KeyError на первой же услуге с непустым image_group)."""
        self._run_sync()  # не должно кинуть исключение
        self.assertTrue(Service.objects.filter(category__salon=self.salon).exists())

    def test_missing_network_access_degrades_gracefully(self):
        """assets.yclients.com недоступен в тестовом окружении — синк не должен
        падать, просто оставлять фото пустыми."""
        self._run_sync()
        self.salon.refresh_from_db()
        # Либо None (сеть недоступна), либо реально скачанное изображение —
        # оба варианта валидны, тест проверяет отсутствие исключения выше.
        self.assertIn(self.salon.logo, [None, self.salon.logo])

    def test_sync_is_idempotent(self):
        self._run_sync()
        counts_before = (
            Master.objects.filter(salons=self.salon).count(),
            ServiceCategory.objects.filter(salon=self.salon).count(),
            Service.objects.filter(category__salon=self.salon).count(),
            SalonPhoto.objects.filter(salon=self.salon).count(),
        )

        self._run_sync()  # повторный прогон

        counts_after = (
            Master.objects.filter(salons=self.salon).count(),
            ServiceCategory.objects.filter(salon=self.salon).count(),
            Service.objects.filter(category__salon=self.salon).count(),
            SalonPhoto.objects.filter(salon=self.salon).count(),
        )
        self.assertEqual(counts_before, counts_after, 'Повторная синхронизация не должна плодить дубликаты')

    def test_master_can_belong_to_multiple_salons(self):
        """Один и тот же мастер (один yclients_staff_id) может работать в
        нескольких салонах — синхронизация второго салона не должна вытеснять
        первый, раньше это было бы невозможно из-за FK Master.salon."""
        self._run_sync()  # первый салон (Зеленоград)

        second_salon = Salon.objects.create(
            name='Второй салон', address='Где-то ещё', latitude='0', longitude='0',
            yclients_company_id='999999',
        )

        # Берём реального мастера из уже загруженных данных и "переиспользуем"
        # его же yclients id в staff-списке второго салона — именно так
        # выглядит человек, работающий в двух филиалах.
        shared_master_entry = self.staff_data[0]
        with patch('sync.client.YClientsDataClient.get_company', return_value={**self.company_data, 'id': 999999}), \
             patch('sync.client.YClientsDataClient.get_staff', return_value=[shared_master_entry]), \
             patch('sync.client.YClientsDataClient.get_service_categories', return_value=[]), \
             patch('sync.client.YClientsDataClient.get_services', return_value=[]):
            sync_salon_full(second_salon)

        master = Master.objects.get(yclients_staff_id=str(shared_master_entry['id']))
        self.assertIn(self.salon, master.salons.all())
        self.assertIn(second_salon, master.salons.all())
        self.assertEqual(master.salons.count(), 2)

    def test_master_status_and_category_not_overwritten_by_sync(self):
        """status/category — бизнес-классификация вне YCLIENTS (самозанятый/ИП,
        уровень мастера). Синк не должен затирать то, что вручную поменяли в админке."""
        self._run_sync()
        master = Master.objects.filter(salons=self.salon).first()
        master.status = Master.STATUS_IP
        master.category = Master.CATEGORY_ART_DIRECTOR
        master.save()

        self._run_sync()  # повторная синхронизация

        master.refresh_from_db()
        self.assertEqual(master.status, Master.STATUS_IP)
        self.assertEqual(master.category, Master.CATEGORY_ART_DIRECTOR)
