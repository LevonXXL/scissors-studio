from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from booking.services import YClientsClient, YClientsError


@override_settings(YCLIENTS_PARTNER_TOKEN='test-partner-token', YCLIENTS_USER_TOKEN='')
class YClientsClientTests(TestCase):
    def setUp(self):
        self.client_ = YClientsClient()

    @patch('booking.services.requests.request')
    def test_auth_header_partner_only(self, mock_request):
        mock_request.return_value = MagicMock(
            json=lambda: {'success': True, 'data': [{'id': 1, 'title': 'Стрижка'}]},
        )
        self.client_.get_services('12345')

        _, kwargs = mock_request.call_args
        self.assertEqual(kwargs['headers']['Authorization'], 'Bearer test-partner-token')

    @patch('booking.services.requests.request')
    def test_auth_header_with_user_token(self, mock_request):
        mock_request.return_value = MagicMock(json=lambda: {'success': True, 'data': []})
        client_ = YClientsClient(partner_token='p-tok', user_token='u-tok')
        client_.get_staff('12345')

        _, kwargs = mock_request.call_args
        self.assertEqual(kwargs['headers']['Authorization'], 'Bearer p-tok, User u-tok')

    @patch('booking.services.requests.request')
    def test_url_construction(self, mock_request):
        mock_request.return_value = MagicMock(json=lambda: {'success': True, 'data': []})
        self.client_.get_available_times('12345', staff_id='678', date='2026-08-01')

        args, kwargs = mock_request.call_args
        method, url = args[0], args[1]
        self.assertEqual(method, 'GET')
        self.assertEqual(url, 'https://api.yclients.com/api/v1/book_times/12345/678')
        self.assertEqual(kwargs['params'], {'date': '2026-08-01'})

    @patch('booking.services.requests.request')
    def test_api_error_raises(self, mock_request):
        mock_request.return_value = MagicMock(
            json=lambda: {'success': False, 'meta': {'message': 'Неверный service_id'}},
        )
        with self.assertRaises(YClientsError):
            self.client_.get_services('12345')

    @patch('booking.services.requests.request')
    def test_create_booking_returns_record_info(self, mock_request):
        mock_request.return_value = MagicMock(json=lambda: {
            'success': True,
            'data': [{'id': 1, 'record_id': 2820023, 'record_hash': 'abc123'}],
        })
        result = self.client_.create_booking(
            '12345', fullname='Тест Тестов', phone='+79990001122',
            staff_id='678', service_ids=['111'], start_datetime_iso='2026-08-01T10:00:00+03:00',
        )
        self.assertEqual(result['record_id'], 2820023)
        self.assertEqual(result['record_hash'], 'abc123')

    @patch('booking.services.requests.request')
    def test_network_error_wrapped(self, mock_request):
        import requests as requests_module
        mock_request.side_effect = requests_module.exceptions.ConnectionError('boom')
        with self.assertRaises(YClientsError):
            self.client_.get_services('12345')


class ReminderLogicTests(TestCase):
    """Проверяет reminders.py без Celery/Redis — чистая логика выборки по времени."""

    @classmethod
    def setUpTestData(cls):
        from django.utils import timezone

        from masters.models import Master
        from salons.models import Salon

        cls.salon = Salon.objects.create(
            name='Тестовый салон', address='Где-то', latitude='0', longitude='0',
        )
        cls.master = Master.objects.create(name='Тест Тестов', specialization='Стрижки')
        cls.master.salons.add(cls.salon)
        cls.now = timezone.now()

    def _make_booking(self, hours_from_now, **kwargs):
        from booking.models import Booking
        defaults = dict(
            salon=self.salon, master=self.master, service_title='Стрижка',
            client_name='Клиент', client_phone='+79990000000',
            yclients_record_id=str(hours_from_now) + '-' + kwargs.get('suffix', 'x'),
        )
        defaults.update({k: v for k, v in kwargs.items() if k != 'suffix'})
        return Booking.objects.create(
            start_datetime=self.now + timedelta(hours=hours_from_now), **defaults
        )

    def test_finds_booking_due_in_24h(self):
        from booking import reminders
        due = self._make_booking(24)
        not_due_yet = self._make_booking(30, suffix='b')
        already_passed_window = self._make_booking(2, suffix='c')

        result = list(reminders.find_bookings_due_for_reminder(reminders.REMINDER_24H, now=self.now))

        self.assertIn(due, result)
        self.assertNotIn(not_due_yet, result)
        self.assertNotIn(already_passed_window, result)

    def test_does_not_repeat_already_sent_reminder(self):
        from booking import reminders
        self._make_booking(24, reminder_24h_sent=True)

        result = list(reminders.find_bookings_due_for_reminder(reminders.REMINDER_24H, now=self.now))
        self.assertEqual(result, [])

    def test_ignores_cancelled_bookings(self):
        from booking import reminders
        from booking.models import Booking
        self._make_booking(1, status=Booking.STATUS_CANCELLED)

        result = list(reminders.find_bookings_due_for_reminder(reminders.REMINDER_1H, now=self.now))
        self.assertEqual(result, [])

    def test_mark_reminder_sent_is_idempotent_flag(self):
        from booking import reminders
        booking = self._make_booking(1)
        reminders.mark_reminder_sent(booking, reminders.REMINDER_1H)
        booking.refresh_from_db()
        self.assertTrue(booking.reminder_1h_sent)
