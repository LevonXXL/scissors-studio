"""Focused checks for the Booking calendar in Django Admin."""

from datetime import datetime, timedelta, timezone

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from booking.models import Booking
from masters.models import Master, MasterSalon
from salons.models import Salon


class BookingCalendarAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.salon = Salon.objects.create(
            name='Красные Ворота', address='Адрес', latitude=0, longitude=0,
            yclients_company_id='128411',
        )
        cls.master = Master.objects.create(name='Мастер', )
        MasterSalon.objects.create(master=cls.master, salon=cls.salon, yclients_staff_id='317697')
        cls.booking = Booking.objects.create(
            salon=cls.salon, master=cls.master, service_title='Стрижка',
            client_name='Клиент', client_phone='',
            start_datetime=datetime(2026, 10, 24, 15, tzinfo=timezone(timedelta(hours=3))),
            end_datetime=datetime(2026, 10, 24, 17, tzinfo=timezone(timedelta(hours=3))),
            yclients_record_id='1862046093',
        )
        cls.superuser = get_user_model().objects.create_superuser(
            username='calendar-admin', email='admin@example.test', password='test-password',
        )

    def setUp(self):
        self.client.force_login(self.superuser)

    def events_url(self):
        return reverse('admin:booking_booking_calendar_events')

    def event_params(self):
        return {
            'start': '2026-10-20T00:00:00+03:00',
            'end': '2026-10-27T00:00:00+03:00',
            'salon': str(self.salon.pk),
        }

    def test_changelist_is_calendar(self):
        second = Master.objects.create(name='Второй мастер', position=2)
        MasterSalon.objects.create(master=second, salon=self.salon)
        response = self.client.get(reverse('admin:booking_booking_changelist'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/calendar.html')
        self.assertContains(response, 'Календарь записей')
        self.assertContains(response, 'booking/vendor/fullcalendar/index.global.min.js')
        self.assertContains(response, 'id="booking-master-day"')
        self.assertEqual(response.context['calendar_masters'][str(self.salon.pk)], [
            {'id': self.master.pk, 'name': self.master.name},
            {'id': second.pk, 'name': second.name},
        ])
        self.assertContains(response, 'Создать запись')

    def test_events_are_scoped_to_salon_and_range(self):
        response = self.client.get(self.events_url(), self.event_params())
        self.assertEqual(response.status_code, 200)
        events = response.json()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['start'], '2026-10-24T15:00:00+03:00')
        self.assertEqual(events[0]['end'], '2026-10-24T17:00:00+03:00')
        self.assertEqual(events[0]['url'], reverse('admin:booking_booking_change', args=(self.booking.pk,)))
        self.assertEqual(events[0]['extendedProps']['master_id'], self.master.pk)
        self.assertEqual(events[0]['extendedProps']['master_name'], self.master.name)

        other = Salon.objects.create(name='Другой', address='Адрес', latitude=0, longitude=0)
        params = {**self.event_params(), 'salon': str(other.pk)}
        self.assertEqual(self.client.get(self.events_url(), params).json(), [])

    def test_events_accept_fullcalendar_moscow_dates_without_offset(self):
        params = {
            'start': '2026-10-20T00:00:00',
            'end': '2026-10-27T00:00:00',
            'timeZone': 'Europe/Moscow',
            'salon': str(self.salon.pk),
        }
        response = self.client.get(self.events_url(), params)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([event['id'] for event in response.json()], [self.booking.pk])

    def test_events_require_admin_model_permission(self):
        self.client.logout()
        response = self.client.get(self.events_url(), self.event_params())
        self.assertEqual(response.status_code, 302)

        staff = get_user_model().objects.create_user(username='staff', password='test-password', is_staff=True)
        self.client.force_login(staff)
        response = self.client.get(self.events_url(), self.event_params())
        self.assertEqual(response.status_code, 403)

    def test_invalid_range_is_rejected(self):
        params = {**self.event_params(), 'end': '2027-01-01T00:00:00+03:00'}
        self.assertEqual(self.client.get(self.events_url(), params).status_code, 400)

    def test_modal_uses_unfold_change_form_and_saves(self):
        url = reverse('admin:booking_booking_change', args=(self.booking.pk,)) + '?calendar_modal=1'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/calendar_change_form.html')
        self.assertEqual(response['X-Frame-Options'], 'SAMEORIGIN')

        normal_response = self.client.get(reverse('admin:booking_booking_change', args=(self.booking.pk,)))
        self.assertEqual(normal_response['X-Frame-Options'], 'DENY')

        response = self.client.post(url, {
            'salon': self.salon.pk,
            'master': self.master.pk,
            'service_title': 'Стрижка',
            'client_name': 'Обновлённый клиент',
            'client_phone': '',
            'start_datetime_0': '2026-10-24',
            'start_datetime_1': '15:00:00',
            'end_datetime_0': '2026-10-24',
            'end_datetime_1': '17:00:00',
            'status': Booking.STATUS_CONFIRMED,
            '_save': 'Сохранить',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/calendar_saved.html')
        self.assertEqual(response['X-Frame-Options'], 'SAMEORIGIN')
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.client_name, 'Обновлённый клиент')

    def test_admin_can_create_booking_from_calendar_modal(self):
        url = reverse('admin:booking_booking_add') + f'?calendar_modal=1&salon={self.salon.pk}'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/calendar_change_form.html')
        self.assertEqual(response['X-Frame-Options'], 'SAMEORIGIN')
        self.assertEqual(response.context['adminform'].form['salon'].value(), str(self.salon.pk))

        response = self.client.post(url, {
            'salon': self.salon.pk,
            'master': self.master.pk,
            'service_title': 'Стрижка',
            'client_name': 'Новый клиент',
            'client_phone': '79670303036',
            'start_datetime_0': '2026-10-25',
            'start_datetime_1': '12:00:00',
            'end_datetime_0': '2026-10-25',
            'end_datetime_1': '13:00:00',
            'status': Booking.STATUS_CONFIRMED,
            '_save': 'Сохранить',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/calendar_saved.html')
        created = Booking.objects.get(client_name='Новый клиент')
        self.assertEqual(created.salon, self.salon)
        self.assertEqual(created.master, self.master)
        self.assertIsNone(created.yclients_record_id)
        events = self.client.get(self.events_url(), self.event_params()).json()
        self.assertIn(created.pk, [event['id'] for event in events])

    def test_admin_cannot_create_overlapping_booking(self):
        url = reverse('admin:booking_booking_add') + '?calendar_modal=1'
        response = self.client.post(url, {
            'salon': self.salon.pk,
            'master': self.master.pk,
            'service_title': 'Стрижка',
            'client_name': 'Конфликт',
            'client_phone': '79670303036',
            'start_datetime_0': '2026-10-24',
            'start_datetime_1': '15:30:00',
            'end_datetime_0': '2026-10-24',
            'end_datetime_1': '16:30:00',
            'status': Booking.STATUS_CONFIRMED,
            '_save': 'Сохранить',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/calendar_change_form.html')
        self.assertContains(response, 'У мастера уже есть запись в этот интервал')
        self.assertFalse(Booking.objects.filter(client_name='Конфликт').exists())

