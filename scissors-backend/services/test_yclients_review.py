from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from masters.models import Master, MasterSalon
from salons.models import Salon

from .models import (Service, ServiceCategory, ServicePrice, ServiceSalon,
                     ServiceStaffPrice, YClientsServiceMatch)


class YClientsReviewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin_user = get_user_model().objects.create_superuser(
            'reviewer', 'reviewer@example.com', 'password',
        )
        cls.salon = Salon.objects.create(
            name='Тестовый салон', address='Адрес', latitude=55, longitude=37,
            yclients_company_id='100',
        )
        cls.category = ServiceCategory.objects.create(title='Стрижки', code='review-hair')
        cls.service = Service.objects.create(
            category=cls.category, title='Стрижка', duration_seconds=3600, price_code='TEST-1',
        )
        cls.offer = ServiceSalon.objects.create(service=cls.service, salon=cls.salon)
        ServicePrice.objects.create(salon_service=cls.offer, amount=1500)
        cls.master = Master.objects.create(name='Мастер')
        MasterSalon.objects.create(master=cls.master, salon=cls.salon, yclients_staff_id='222')

    def setUp(self):
        self.client.force_login(self.admin_user)
        self.url = reverse('admin:services_service_review_yclients')

    def source(self, staff_id=222):
        return [{
            'id': 999, 'title': 'Стрижка', 'category_id': 12, 'active': 1,
            'price_min': 500, 'price_max': 800,
            'staff': [{'id': staff_id, 'name': 'Мастер', 'price': 700, 'seance_length': 3000}],
        }]

    def fetch(self, source):
        with patch('services.admin.YClientsDataClient') as client_class:
            client_class.return_value.get_services.return_value = source
            return self.client.post(self.url, {'fetch': '1'})

    def test_empty_review_shows_prominent_fetch_action(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'name="fetch"')
        self.assertContains(response, 'bg-primary')

    def test_fetch_is_read_only_and_row_save_creates_only_assignments(self):
        response = self.fetch(self.source())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Сохранить строку')
        self.assertEqual(ServiceStaffPrice.objects.count(), 0)
        self.assertEqual(YClientsServiceMatch.objects.count(), 0)
        self.assertNotIn('price', str(self.client.session['service_yclients_assignment_review']))

        row_key = f'{self.salon.pk}:999'
        data = {'save_row': '1', 'row_key': row_key, 'target_id': str(self.service.pk)}
        saved_response = self.client.post(self.url, data)
        self.assertEqual(saved_response.status_code, 200)
        self.assertEqual(saved_response.context['rows'][0]['status'], 'saved')
        self.assertEqual(saved_response.context['saved_count'], 1)
        assignment = ServiceStaffPrice.objects.get(service=self.service, master=self.master, salon=self.salon)
        self.assertEqual(assignment.duration_seconds, 3000)
        self.assertIsNone(assignment.price_min)
        self.assertEqual(ServicePrice.objects.get(salon_service=self.offer).amount, 1500)
        self.assertTrue(YClientsServiceMatch.objects.filter(
            salon=self.salon, yclients_service_id='999', service=self.service,
        ).exists())
        self.service.refresh_from_db()
        self.assertEqual(self.service.yclients_service_id, '999')
        self.client.post(self.url, data)
        self.assertEqual(ServiceStaffPrice.objects.count(), 1)

    def test_multiple_targets_and_existing_values_are_preserved(self):
        second = Service.objects.create(category=self.category, title='Стрижка и укладка',
                                        duration_seconds=4200, price_code='TEST-2')
        ServiceSalon.objects.create(service=second, salon=self.salon)
        old = ServiceStaffPrice.objects.create(
            service=self.service, master=self.master, salon=self.salon,
            price_min=1234, duration_seconds=2700,
        )
        self.fetch(self.source())
        self.client.post(self.url, {
            'save_row': '1', 'row_key': f'{self.salon.pk}:999',
            'target_id': [str(self.service.pk), str(second.pk)],
        })
        old.refresh_from_db()
        self.assertEqual((old.price_min, old.duration_seconds), (1234, 2700))
        self.assertEqual(ServiceStaffPrice.objects.get(service=second).duration_seconds, 3000)
        self.assertEqual(YClientsServiceMatch.objects.filter(yclients_service_id='999').count(), 2)
        self.service.refresh_from_db()
        second.refresh_from_db()
        self.assertFalse(second.yclients_service_id)

    def test_existing_service_id_is_not_overwritten(self):
        self.service.yclients_service_id = 'old-id'
        self.service.save(update_fields=['yclients_service_id'])
        self.fetch(self.source())
        self.client.post(self.url, {
            'save_row': '1', 'row_key': f'{self.salon.pk}:999',
            'target_id': str(self.service.pk),
        })
        self.service.refresh_from_db()
        self.assertEqual(self.service.yclients_service_id, 'old-id')
        self.assertTrue(YClientsServiceMatch.objects.filter(
            service=self.service, yclients_service_id='999',
        ).exists())

    def test_bulk_applies_only_selected_ready_rows(self):
        other = Service.objects.create(category=self.category, title='Укладка', price_code='TEST-3')
        ServiceSalon.objects.create(service=other, salon=self.salon)
        sources = self.source() + [{
            'id': 1000, 'title': 'Укладка', 'active': 1,
            'staff': [{'id': 222, 'name': 'Мастер', 'seance_length': 2400}],
        }]
        self.fetch(sources)
        response = self.client.post(self.url, {
            'apply_selected': '1', 'selected_rows': [f'{self.salon.pk}:999'],
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ServiceStaffPrice.objects.count(), 1)
        self.assertFalse(YClientsServiceMatch.objects.filter(yclients_service_id='1000').exists())

    def test_unlinked_excel_services_are_offered_without_creating_new_services(self):
        other = Service.objects.create(category=self.category, title='Стрижка особая', price_code='TEST-4')
        ServiceSalon.objects.create(service=other, salon=self.salon)
        not_excel = Service.objects.create(category=self.category, title='Услуга без кода Excel')
        ServiceSalon.objects.create(service=not_excel, salon=self.salon)
        source = self.source()
        source[0]['title'] = 'Другое название'
        row = self.fetch(source).context['rows'][0]
        self.assertIn(other, row['unlinked_services'])
        self.assertNotIn(not_excel, row['unlinked_services'])
        self.assertEqual(Service.objects.count(), 3)

    def test_unlinked_catalogue_is_embedded_once_for_autocomplete(self):
        source = self.source() + [{
            'id': 1000, 'title': 'Другая услуга', 'active': 1,
            'staff': [{'id': 222, 'name': 'Мастер', 'seance_length': 3600}],
        }]
        response = self.fetch(source)
        self.assertContains(response, 'id="review-unlinked-services"', count=1)
        self.assertContains(response, 'Введите минимум 3 символа', count=2)
        self.assertNotContains(response, 'class="review-select"')

    def test_filters_hide_saved_assignments_and_keep_problem_rows(self):
        sources = self.source() + [{
            'id': 1000, 'title': 'Неизвестная услуга', 'active': 1,
            'staff': [{'id': 222, 'name': 'Мастер', 'seance_length': 2400}],
        }]
        self.fetch(sources)
        saved_response = self.client.post(self.url + '?filter=unassigned', {
            'save_row': '1', 'row_key': f'{self.salon.pk}:999',
            'target_id': str(self.service.pk),
        })
        self.assertEqual([row['source_id'] for row in saved_response.context['rows']], ['1000'])
        all_rows = self.client.get(self.url).context['rows']
        self.assertEqual(len(all_rows), 2)
        self.assertEqual({row['source_id'] for row in all_rows if row['status'] == 'saved'}, {'999'})
        problems = self.client.get(self.url + '?filter=problems')
        self.assertEqual([row['source_id'] for row in problems.context['rows']], ['1000'])
        unassigned = self.client.get(self.url + '?filter=unassigned')
        self.assertEqual([row['source_id'] for row in unassigned.context['rows']], ['1000'])
        self.assertContains(unassigned, 'Без назначений · 1')

    def test_unknown_staff_blocks_entire_row(self):
        self.fetch(self.source(staff_id=333))
        response = self.client.post(self.url, {
            'save_row': '1', 'row_key': f'{self.salon.pk}:999',
            'target_id': str(self.service.pk),
        })
        self.assertContains(response, 'не сопоставлен с мастером в БД')
        self.assertFalse(ServiceStaffPrice.objects.exists())
        self.assertFalse(YClientsServiceMatch.objects.exists())

    def test_validation_failure_rolls_back_other_targets(self):
        second = Service.objects.create(category=self.category, title='Другая стрижка', price_code='TEST-5')
        ServiceSalon.objects.create(service=second, salon=self.salon)
        self.master.price_level = 'stylist'
        self.master.save(update_fields=['price_level'])
        self.fetch(self.source())
        response = self.client.post(self.url, {
            'save_row': '1', 'row_key': f'{self.salon.pk}:999',
            'target_id': [str(self.service.pk), str(second.pk)],
        })
        self.assertContains(response, 'Нельзя назначить')
        self.assertFalse(ServiceStaffPrice.objects.exists())
        self.assertFalse(YClientsServiceMatch.objects.exists())

    def test_pipe_suffix_matches_base_title_but_ambiguity_needs_review(self):
        cut = Service.objects.create(category=self.category, title='Мужская стрижка', price_code='TEST-6')
        ServiceSalon.objects.create(service=cut, salon=self.salon)
        source = self.source()
        source[0]['title'] = 'Мужская стрижка | Man Cut'
        row = self.fetch(source).context['rows'][0]
        self.assertEqual(row['suggested_ids'], {cut.pk})
        self.assertEqual(row['reason'], 'Совпадение основного названия до |')
        self.assertEqual(ServiceStaffPrice.objects.count(), 0)

        other = Service.objects.create(category=self.category, title='Мужская стрижка | Mens Cut',
                                       price_code='TEST-7')
        ServiceSalon.objects.create(service=other, salon=self.salon)
        row = self.fetch(source).context['rows'][0]
        self.assertFalse(row['suggested_ids'])
        self.assertTrue({cut.pk, other.pk} <= {service.pk for service in row['candidates']})

    def test_ai_name_hint_is_unchecked_and_requires_matching_source_title(self):
        blonde = Service.objects.create(
            category=self.category, title='Первичный блонд. Короткие',
            code='hair-94d8c5641d6db600', price_code='TEST-8',
        )
        ServiceSalon.objects.create(service=blonde, salon=self.salon)
        source = self.source()
        source[0]['id'] = 5754399
        source[0]['title'] = 'Первичный блонд | Blond. The First (короткие волосы)'
        row = self.fetch(source).context['rows'][0]
        self.assertEqual(row['ai_ids'], {blonde.pk})
        self.assertFalse(row['suggested_ids'])
        self.assertContains(self.fetch(source), 'Предложение ИИ · проверить')
        self.assertFalse(YClientsServiceMatch.objects.exists())

        source[0]['title'] = 'Другая услуга'
        row = self.fetch(source).context['rows'][0]
        self.assertFalse(row['ai_ids'])
