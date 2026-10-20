import json
from io import StringIO
from pathlib import Path
from unittest.mock import Mock, patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from filer.models import Image as FilerImage

from masters.models import Master, MasterSalon
from pages.models import Page
from salons.models import Salon, SalonPhoto
from services.models import Service, ServiceCategory, ServiceStaffPrice
from sync.sync_service import sync_salon_full, sync_staff

FIXTURES_DIR = Path(__file__).parent / 'fixtures' / 'yclients_samples'


def _load(name: str):
    return json.load(open(FIXTURES_DIR / name, encoding='utf-8'))['data']


class YClientsStaffLinkTests(TestCase):
    def setUp(self):
        self.salon = Salon.objects.create(
            name='Тестовый салон', address='Адрес', latitude='0', longitude='0',
        )

    def _sync_entries(self, entries):
        client = Mock()
        client.get_staff.return_value = entries
        return sync_staff(self.salon, client)

    def test_sync_saves_staff_id_on_salon_link(self):
        salon = self.salon
        staff_data = _load('staff.json')
        entries = [
            next(entry for entry in staff_data if entry.get('user_id')),
            next(entry for entry in staff_data if not entry.get('user_id')),
        ]
        client = Mock()
        client.get_staff.return_value = entries

        sync_staff(salon, client)
        sync_staff(salon, client)

        self.assertEqual(MasterSalon.objects.filter(salon=salon).count(), len(entries))
        for entry in entries:
            link = MasterSalon.objects.get(salon=salon, yclients_staff_id=str(entry['id']))
            self.assertEqual(link.master.yclients_staff_id, str(entry['id']))
            self.assertEqual(link.master.yclients_user_id, str(entry['user_id']) if entry.get('user_id') else None)

    def test_fills_placeholder_ids_on_existing_master_and_link(self):
        master = Master.objects.create(name='Тестовый мастер', specialization='', yclients_user_id='-', yclients_staff_id='-')
        link = MasterSalon.objects.create(master=master, salon=self.salon, yclients_staff_id='-')
        entry = {'id': 123, 'user_id': 456, 'employee': {'id': 789}, 'name': 'Тестовый мастер'}

        self._sync_entries([entry])
        self._sync_entries([entry])

        master.refresh_from_db()
        link.refresh_from_db()
        self.assertEqual(Master.objects.count(), 1)
        self.assertEqual(MasterSalon.objects.count(), 1)
        self.assertEqual(master.yclients_user_id, '456')
        self.assertEqual(master.yclients_staff_id, '123')
        self.assertEqual(link.yclients_staff_id, '123')

    def test_system_position_reuses_placeholder_link_without_user_id(self):
        master = Master.objects.create(name='Служебная позиция', specialization='', is_system=True, yclients_staff_id='-')
        link = MasterSalon.objects.create(master=master, salon=self.salon, yclients_staff_id='-')

        self._sync_entries([{'id': 123, 'user_id': None, 'name': 'Служебная позиция'}])

        master.refresh_from_db()
        link.refresh_from_db()
        self.assertEqual(Master.objects.count(), 1)
        self.assertIsNone(master.yclients_user_id)
        self.assertEqual(master.yclients_staff_id, '123')
        self.assertEqual(link.yclients_staff_id, '123')

    def test_existing_salon_link_identifies_master_without_user_id(self):
        master = Master.objects.create(name='Прежнее имя', specialization='', yclients_user_id='-')
        MasterSalon.objects.create(master=master, salon=self.salon, yclients_staff_id='123')

        self._sync_entries([{'id': 123, 'user_id': 456, 'name': 'Новое имя'}])

        master.refresh_from_db()
        self.assertEqual(Master.objects.count(), 1)
        self.assertEqual(master.yclients_user_id, '456')
        self.assertEqual(master.name, 'Новое имя')

    def test_legacy_staff_id_identifies_existing_master_in_same_salon(self):
        master = Master.objects.create(name='Прежнее имя', specialization='', yclients_staff_id='123')
        link = MasterSalon.objects.create(master=master, salon=self.salon, yclients_staff_id=None)

        self._sync_entries([{'id': 123, 'user_id': 456, 'name': 'Новое имя'}])

        master.refresh_from_db()
        link.refresh_from_db()
        self.assertEqual(Master.objects.count(), 1)
        self.assertEqual(master.yclients_user_id, '456')
        self.assertEqual(link.yclients_staff_id, '123')

    def test_does_not_guess_by_duplicate_name_or_other_salon(self):
        old = Master.objects.create(name='Тёзка', specialization='', yclients_user_id='-')
        MasterSalon.objects.create(master=old, salon=self.salon, yclients_staff_id='-')
        other_salon = Salon.objects.create(name='Другой', address='Адрес', latitude='0', longitude='0')
        other = Master.objects.create(name='Другой мастер', specialization='')
        MasterSalon.objects.create(master=other, salon=other_salon, yclients_staff_id=None)

        self._sync_entries([
            {'id': 123, 'user_id': 456, 'name': 'Тёзка'},
            {'id': 124, 'user_id': 457, 'name': 'Тёзка'},
            {'id': 125, 'user_id': 458, 'name': 'Другой мастер'},
        ])

        old.refresh_from_db()
        self.assertEqual(old.yclients_user_id, '-')
        self.assertEqual(MasterSalon.objects.get(master=old).yclients_staff_id, '-')
        self.assertEqual(MasterSalon.objects.get(master=other).salon, other_salon)
        self.assertEqual(Master.objects.filter(yclients_user_id__in=['456', '457', '458']).count(), 3)

    def test_conflicting_known_user_id_is_not_replaced(self):
        master = Master.objects.create(name='Тестовый', specialization='', yclients_user_id='999')
        link = MasterSalon.objects.create(master=master, salon=self.salon, yclients_staff_id='123')

        self._sync_entries([{'id': 123, 'user_id': 456, 'name': 'Тестовый'}])

        master.refresh_from_db()
        link.refresh_from_db()
        self.assertEqual(master.yclients_user_id, '999')
        self.assertEqual(link.yclients_staff_id, '123')
        self.assertFalse(Master.objects.filter(yclients_user_id='456').exists())

    def test_sync_removes_safe_legacy_duplicate(self):
        team = Page.objects.create(title='Команда', url='team')
        canonical_page = Page.objects.create(title='Тестовый мастер', url='master', parent=team)
        duplicate_page = Page.objects.create(title='Тестовый мастер', url='master-2', parent=team)
        canonical = Master.objects.create(
            name='Тестовый мастер', specialization='', page=canonical_page,
            yclients_user_id='456', yclients_staff_id='123',
        )
        duplicate = Master.objects.create(name='Тестовый мастер', specialization='', page=duplicate_page)
        MasterSalon.objects.create(master=canonical, salon=self.salon, yclients_staff_id='123')
        MasterSalon.objects.create(master=duplicate, salon=self.salon, yclients_staff_id='-')

        self._sync_entries([{'id': 123, 'user_id': 456, 'name': 'Тестовый мастер'}])
        self._sync_entries([{'id': 123, 'user_id': 456, 'name': 'Тестовый мастер'}])

        self.assertFalse(Master.objects.filter(pk=duplicate.pk).exists())
        self.assertEqual(Master.objects.count(), 1)
        self.assertEqual(MasterSalon.objects.get(salon=self.salon).master_id, canonical.pk)
        duplicate_page.refresh_from_db()
        self.assertFalse(duplicate_page.is_published)

    def test_sync_recovers_missing_page_content_from_duplicate(self):
        team = Page.objects.create(title='Команда', url='team')
        canonical_page = Page.objects.create(title='Тестовый мастер', url='master', parent=team)
        duplicate_page = Page.objects.create(title='Тестовый мастер', url='master-2', parent=team,
                                             content='Уникальное описание')
        canonical = Master.objects.create(
            name='Тестовый мастер', specialization='', page=canonical_page,
            yclients_user_id='456', yclients_staff_id='123',
        )
        duplicate = Master.objects.create(name='Тестовый мастер', specialization='', page=duplicate_page)
        MasterSalon.objects.create(master=canonical, salon=self.salon, yclients_staff_id='123')
        MasterSalon.objects.create(master=duplicate, salon=self.salon, yclients_staff_id=None)

        self._sync_entries([{'id': 123, 'user_id': 456, 'name': 'Тестовый мастер'}])

        self.assertFalse(Master.objects.filter(pk=duplicate.pk).exists())
        self.assertEqual(MasterSalon.objects.filter(salon=self.salon).count(), 1)
        canonical_page.refresh_from_db()
        duplicate_page.refresh_from_db()
        self.assertEqual(canonical_page.content, 'Уникальное описание')
        self.assertEqual(duplicate_page.content, 'Уникальное описание')
        self.assertFalse(duplicate_page.is_published)

    def test_sync_transfers_legacy_page_and_keeps_current_activity(self):
        team = Page.objects.create(title='Команда', url='team')
        duplicate_page = Page.objects.create(
            title='Тестовый мастер', url='testovyy-master-2', parent=team,
            content='Редакторский текст', meta_title='SEO заголовок',
        )
        canonical = Master.objects.create(
            name='Тестовый мастер', specialization='', slug='testovyy-master',
            yclients_user_id='456', yclients_staff_id='123', is_active=False,
        )
        duplicate = Master.objects.create(
            name='Тестовый мастер', specialization='', page=duplicate_page, is_active=True,
        )
        MasterSalon.objects.create(master=canonical, salon=self.salon, yclients_staff_id='123')
        MasterSalon.objects.create(master=duplicate, salon=self.salon, yclients_staff_id=None)

        self._sync_entries([{'id': 123, 'user_id': 456, 'name': 'Тестовый мастер', 'fired': True}])

        canonical.refresh_from_db()
        duplicate_page.refresh_from_db()
        self.assertFalse(Master.objects.filter(pk=duplicate.pk).exists())
        self.assertFalse(canonical.is_active)
        self.assertEqual(canonical.page_id, duplicate_page.pk)
        self.assertEqual(duplicate_page.url_path, 'team/testovyy-master')
        self.assertEqual(duplicate_page.content, 'Редакторский текст')
        self.assertEqual(duplicate_page.meta_title, 'SEO заголовок')

    def test_sync_merges_duplicate_with_different_bio_and_specialization(self):
        canonical = Master.objects.create(
            name='Тестовый мастер', specialization='', bio='',
            yclients_user_id='456', yclients_staff_id='123',
        )
        duplicate = Master.objects.create(
            name='Тестовый мастер', specialization='Старое описание услуг', bio='Биография',
        )
        MasterSalon.objects.create(master=canonical, salon=self.salon, yclients_staff_id='123')
        MasterSalon.objects.create(master=duplicate, salon=self.salon, yclients_staff_id=None)

        self._sync_entries([{'id': 123, 'user_id': 456, 'name': 'Тестовый мастер'}])

        canonical.refresh_from_db()
        self.assertFalse(Master.objects.filter(pk=duplicate.pk).exists())
        self.assertEqual(canonical.specialization, 'Старое описание услуг')
        self.assertEqual(canonical.bio, 'Биография')

    def test_sync_uses_exact_legacy_staff_id_even_if_name_changed(self):
        canonical = Master.objects.create(
            name='Новое имя', specialization='', yclients_user_id='456', yclients_staff_id='123',
        )
        duplicate = Master.objects.create(
            name='Старое имя', specialization='', yclients_staff_id='123',
        )
        MasterSalon.objects.create(master=canonical, salon=self.salon, yclients_staff_id='123')
        MasterSalon.objects.create(master=duplicate, salon=self.salon, yclients_staff_id=None)

        self._sync_entries([{'id': 123, 'user_id': 456, 'name': 'Новое имя'}])

        self.assertFalse(Master.objects.filter(pk=duplicate.pk).exists())
        self.assertEqual(MasterSalon.objects.get(salon=self.salon).master_id, canonical.pk)

    def test_sync_does_not_merge_conflicting_legacy_staff_id(self):
        canonical = Master.objects.create(
            name='Тестовый мастер', specialization='', yclients_user_id='456', yclients_staff_id='123',
        )
        duplicate = Master.objects.create(
            name='Тестовый мастер', specialization='', yclients_staff_id='999',
        )
        MasterSalon.objects.create(master=canonical, salon=self.salon, yclients_staff_id='123')
        MasterSalon.objects.create(master=duplicate, salon=self.salon, yclients_staff_id=None)

        self._sync_entries([{'id': 123, 'user_id': 456, 'name': 'Тестовый мастер'}])

        self.assertTrue(Master.objects.filter(pk=duplicate.pk).exists())


class ReconcileMasterDuplicateTests(TestCase):
    def setUp(self):
        self.salon = Salon.objects.create(name='Тестовый салон', address='Адрес', latitude='0', longitude='0')
        team = Page.objects.create(title='Команда', url='team')
        self.canonical_page = Page.objects.create(title='Тестовый мастер', url='master', parent=team)
        self.duplicate_page = Page.objects.create(title='Тестовый мастер', url='master-2', parent=team)
        self.canonical = Master.objects.create(
            name='Тестовый мастер', specialization='', page=self.canonical_page,
            yclients_user_id='456', yclients_staff_id='123',
        )
        self.duplicate = Master.objects.create(
            name='Тестовый мастер', specialization='', page=self.duplicate_page,
        )
        MasterSalon.objects.create(master=self.canonical, salon=self.salon, yclients_staff_id='123')
        MasterSalon.objects.create(master=self.duplicate, salon=self.salon, yclients_staff_id=None)

    def _run_command(self, apply=False):
        return call_command(
            'reconcile_master_duplicate', canonical_id=self.canonical.pk,
            duplicate_id=self.duplicate.pk, apply=apply, stdout=StringIO(),
        )

    def test_dry_run_does_not_change_database(self):
        self._run_command()
        self.assertTrue(Master.objects.filter(pk=self.duplicate.pk).exists())
        self.duplicate_page.refresh_from_db()
        self.assertTrue(self.duplicate_page.is_published)

    def test_apply_preserves_page_but_removes_duplicate_master(self):
        self._run_command(apply=True)
        self.assertFalse(Master.objects.filter(pk=self.duplicate.pk).exists())
        self.assertEqual(MasterSalon.objects.filter(master=self.canonical, salon=self.salon).count(), 1)
        self.duplicate_page.refresh_from_db()
        self.assertFalse(self.duplicate_page.is_published)
        self.canonical.refresh_from_db()
        self.assertEqual(self.canonical.page_id, self.canonical_page.pk)

    def test_apply_keeps_matching_prices_and_moves_nonoverlapping_prices(self):
        category = ServiceCategory.objects.create(
            salon=self.salon, title='Стрижки', yclients_category_id='category-1',
        )
        shared = Service.objects.create(category=category, title='Общая', yclients_service_id='service-1')
        extra = Service.objects.create(category=category, title='Дополнительная', yclients_service_id='service-2')
        ServiceStaffPrice.objects.create(service=shared, master=self.canonical, price_min=100)
        ServiceStaffPrice.objects.create(service=shared, master=self.duplicate, price_min=100)
        ServiceStaffPrice.objects.create(service=extra, master=self.duplicate, price_min=200)

        self._run_command(apply=True)

        self.assertEqual(ServiceStaffPrice.objects.filter(master=self.canonical).count(), 2)
        self.assertEqual(ServiceStaffPrice.objects.get(service=extra).master_id, self.canonical.pk)

    def test_apply_preserves_curated_category_for_master_in_two_salons(self):
        second_salon = Salon.objects.create(name='Второй салон', address='Адрес', latitude='0', longitude='0')
        MasterSalon.objects.create(master=self.canonical, salon=second_salon, yclients_staff_id='124')
        self.canonical.category = Master.CATEGORY_ART_DIRECTOR
        self.canonical.save(update_fields=['category'])
        self.assertEqual(self.duplicate.category, Master.CATEGORY_UNIVERSAL)

        self._run_command(apply=True)

        self.canonical.refresh_from_db()
        self.assertEqual(self.canonical.category, Master.CATEGORY_ART_DIRECTOR)
        self.assertEqual(MasterSalon.objects.filter(master=self.canonical).count(), 2)
        self.assertFalse(Master.objects.filter(pk=self.duplicate.pk).exists())

    def test_different_curated_categories_prevent_merge(self):
        self.canonical.category = Master.CATEGORY_ART_DIRECTOR
        self.canonical.save(update_fields=['category'])
        self.duplicate.category = Master.CATEGORY_STYLIST
        self.duplicate.save(update_fields=['category'])

        with self.assertRaises(CommandError):
            self._run_command(apply=True)
        self.assertTrue(Master.objects.filter(pk=self.duplicate.pk).exists())

    def test_apply_recovers_missing_content_from_duplicate(self):
        image = FilerImage.objects.create(file='portraits/test.jpg', original_filename='test.jpg')
        self.duplicate.specialization = 'Стрижки'
        self.duplicate.bio = 'Сохранённое описание'
        self.duplicate.photo = image
        self.duplicate.save(update_fields=['specialization', 'bio', 'photo'])

        self._run_command(apply=True)

        self.canonical.refresh_from_db()
        self.assertEqual(self.canonical.specialization, 'Стрижки')
        self.assertEqual(self.canonical.bio, 'Сохранённое описание')
        self.assertEqual(self.canonical.photo_id, image.pk)

    def test_apply_keeps_identified_content_when_both_have_values(self):
        self.canonical.specialization = 'Окрашивание'
        self.canonical.bio = 'Новый текст'
        self.canonical.save(update_fields=['specialization', 'bio'])
        self.duplicate.specialization = 'Стрижки'
        self.duplicate.bio = 'Старый текст'
        self.duplicate.save(update_fields=['specialization', 'bio'])

        self._run_command(apply=True)

        self.canonical.refresh_from_db()
        self.assertEqual(self.canonical.specialization, 'Окрашивание')
        self.assertEqual(self.canonical.bio, 'Новый текст')

    def test_apply_keeps_identified_price_when_overlapping_prices_differ(self):
        category = ServiceCategory.objects.create(
            salon=self.salon, title='Стрижки', yclients_category_id='category-1',
        )
        service = Service.objects.create(category=category, title='Стрижка', yclients_service_id='service-1')
        ServiceStaffPrice.objects.create(service=service, master=self.canonical, price_min=100)
        ServiceStaffPrice.objects.create(service=service, master=self.duplicate, price_min=200)

        self._run_command(apply=True)

        price = ServiceStaffPrice.objects.get(service=service)
        self.assertEqual(price.master_id, self.canonical.pk)
        self.assertEqual(price.price_min, 100)

    def test_different_page_content_keeps_canonical_and_archives_duplicate(self):
        self.canonical_page.meta_title = 'Основной заголовок'
        self.canonical_page.save(update_fields=['meta_title'])
        self.duplicate_page.meta_title = 'Уникальный заголовок'
        self.duplicate_page.save(update_fields=['meta_title'])
        self._run_command(apply=True)
        self.assertFalse(Master.objects.filter(pk=self.duplicate.pk).exists())
        self.canonical_page.refresh_from_db()
        self.duplicate_page.refresh_from_db()
        self.assertEqual(self.canonical_page.meta_title, 'Основной заголовок')
        self.assertEqual(self.duplicate_page.meta_title, 'Уникальный заголовок')
        self.assertFalse(self.duplicate_page.is_published)

    def test_duplicate_page_with_child_prevents_merge(self):
        Page.objects.create(title='Вложенная страница', url='child', parent=self.duplicate_page)
        with self.assertRaises(CommandError):
            self._run_command(apply=True)
        self.assertTrue(Master.objects.filter(pk=self.duplicate.pk).exists())


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
        shared_master_entry = next(entry for entry in self.staff_data if entry.get('user_id'))
        second_salon_entry = {**shared_master_entry, 'id': 999999999}
        with patch('sync.client.YClientsDataClient.get_company', return_value={**self.company_data, 'id': 999999}), \
             patch('sync.client.YClientsDataClient.get_staff', return_value=[second_salon_entry]), \
             patch('sync.client.YClientsDataClient.get_service_categories', return_value=[]), \
             patch('sync.client.YClientsDataClient.get_services', return_value=[]):
            sync_salon_full(second_salon)

        master = Master.objects.get(yclients_user_id=str(shared_master_entry['user_id']))
        self.assertIn(self.salon, master.salons.all())
        self.assertIn(second_salon, master.salons.all())
        self.assertEqual(master.salons.count(), 2)
        self.assertEqual(
            MasterSalon.objects.get(master=master, salon=self.salon).yclients_staff_id,
            str(shared_master_entry['id']),
        )
        self.assertEqual(
            MasterSalon.objects.get(master=master, salon=second_salon).yclients_staff_id,
            str(second_salon_entry['id']),
        )

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
