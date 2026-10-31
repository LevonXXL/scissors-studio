"""Focused tests for importing local YCLIENTS salons into Booking."""

from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from booking.models import Booking
from masters.models import Master, MasterSalon
from salons.models import Salon


@override_settings(YCLIENTS_PARTNER_TOKEN='test-partner', YCLIENTS_USER_TOKEN='test-user')
class ImportYclientsRecordsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.salon = Salon.objects.create(
            name='Тестовый филиал', address='Адрес', latitude=0, longitude=0,
            yclients_company_id='128411',
        )
        cls.master = Master.objects.create(name='Мастер', )
        MasterSalon.objects.create(master=cls.master, salon=cls.salon, yclients_staff_id='317697')

    def setUp(self):
        self.record = {
            'id': 1862046093,
            'company_id': 128411,
            'datetime': '2026-10-24T15:00:00+03:00',
            'seance_length': 7200,
            'staff_id': 317697,
            'attendance': 0,
            'deleted': False,
            'services': [{'id': 5754349, 'title': 'Стрижка'}],
            'client': None,
        }
        records_patch = patch('booking.management.commands.import_yclients_records.get_records')
        client_patch = patch('booking.management.commands.import_yclients_records.YClientsDataClient')
        self.get_records = records_patch.start()
        self.yclients_client = client_patch.start()
        self.addCleanup(records_patch.stop)
        self.addCleanup(client_patch.stop)
        self.get_records.return_value = [self.record]

    def run_command(self, *, apply=False):
        output = StringIO()
        call_command(
            'import_yclients_records',
            from_date='2026-10-20', to_date='2026-10-26',
            apply=apply, stdout=output,
        )
        return output.getvalue()

    def test_preview_does_not_write(self):
        output = self.run_command()
        self.assertIn('ПРЕДВАРИТЕЛЬНЫЙ ПРОСМОТР', output)
        self.assertIn('создано 1', output)
        self.assertFalse(Booking.objects.exists())
        self.get_records.assert_called_once()
        self.assertEqual(self.get_records.call_args.args[1], '128411')

    def test_apply_and_repeat_are_idempotent(self):
        self.run_command(apply=True)
        booking = Booking.objects.get(yclients_record_id='1862046093')
        self.assertEqual(booking.master, self.master)
        self.assertEqual(booking.client_name, '')
        self.assertEqual(booking.client_phone, '')
        self.assertEqual(booking.service_title, 'Стрижка')
        self.assertEqual(booking.status, Booking.STATUS_CONFIRMED)
        self.assertEqual(booking.end_datetime - booking.start_datetime, timedelta(hours=2))

        output = self.run_command(apply=True)
        self.assertIn('без изменений 1', output)
        self.assertEqual(Booking.objects.count(), 1)

    def test_updates_same_external_record_and_preserves_local_user(self):
        self.run_command(apply=True)
        self.record['attendance'] = 1
        self.record['seance_length'] = 3600
        output = self.run_command(apply=True)
        booking = Booking.objects.get(yclients_record_id='1862046093')
        self.assertIn('обновлено 1', output)
        self.assertEqual(booking.status, Booking.STATUS_COMPLETED)
        self.assertEqual(booking.yclients_attendance, 1)
        self.assertEqual(booking.end_datetime - booking.start_datetime, timedelta(hours=1))

    def test_imports_busy_record_without_service_or_client(self):
        self.record['services'] = []
        self.run_command(apply=True)
        booking = Booking.objects.get(yclients_record_id='1862046093')
        self.assertEqual(booking.service_title, '')
        self.assertIsNone(booking.client_user)

    def test_yclients_phone_with_leading_seven_uses_profile_format(self):
        self.record['client'] = {'phone': '79991234567'}
        self.run_command(apply=True)
        self.assertEqual(Booking.objects.get().client_phone, '+79991234567')

    def test_service_order_from_api_does_not_trigger_updates(self):
        self.record['services'] = [
            {'id': 20, 'title': 'Укладка'},
            {'id': 10, 'title': 'Стрижка'},
        ]
        self.run_command(apply=True)
        self.record['services'].reverse()

        output = self.run_command()

        self.assertIn('без изменений 1', output)
        self.assertEqual(
            Booking.objects.get(yclients_record_id='1862046093').service_title,
            'Стрижка, Укладка',
        )

    def test_does_not_replace_mapped_master_with_another_salon(self):
        other_salon = Salon.objects.create(
            name='Другой филиал', address='Адрес', latitude=0, longitude=0,
            yclients_company_id='38297',
        )
        other_master = Master.objects.create(name='Другой', )
        MasterSalon.objects.create(master=other_master, salon=other_salon, yclients_staff_id='987654')
        self.record['staff_id'] = 987654
        with self.assertRaises(CommandError):
            self.run_command(apply=True)
        self.assertFalse(Booking.objects.exists())

    def test_api_error_in_one_salon_does_not_stop_next_salon(self):
        second_salon = Salon.objects.create(
            name='Второй филиал', address='Адрес', latitude=0, longitude=0,
            yclients_company_id='38297',
        )
        second_master = Master.objects.create(name='Второй мастер', )
        MasterSalon.objects.create(master=second_master, salon=second_salon, yclients_staff_id='987654')
        second_record = {
            **self.record, 'id': 42, 'company_id': 38297, 'staff_id': 987654,
        }
        self.get_records.side_effect = [CommandError('HTTP 403. Доступ запрещён.'), [second_record]]
        output = StringIO()

        with self.assertRaises(CommandError):
            call_command(
                'import_yclients_records', from_date='2026-10-20', to_date='2026-10-26',
                apply=True, stdout=output,
            )

        self.assertIn(f'Салон #{self.salon.pk}: HTTP 403', output.getvalue())
        self.assertIn('Перехожу к следующему салону', output.getvalue())
        self.assertIn(f'Салон #{second_salon.pk}', output.getvalue())
        self.assertIn('салонов с ошибкой 1', output.getvalue())
        self.assertEqual(self.get_records.call_count, 2)
        self.assertEqual(Booking.objects.count(), 1)
        self.assertEqual(Booking.objects.get().salon, second_salon)

    def test_invalid_company_id_does_not_stop_next_salon(self):
        self.salon.yclients_company_id = 'invalid'
        self.salon.save(update_fields=['yclients_company_id'])
        second_salon = Salon.objects.create(
            name='Второй филиал', address='Адрес', latitude=0, longitude=0,
            yclients_company_id='38297',
        )
        second_master = Master.objects.create(name='Второй мастер', )
        MasterSalon.objects.create(master=second_master, salon=second_salon, yclients_staff_id='987654')
        self.get_records.return_value = [{
            **self.record, 'id': 42, 'company_id': 38297, 'staff_id': 987654,
        }]
        output = StringIO()

        with self.assertRaises(CommandError):
            call_command(
                'import_yclients_records', from_date='2026-10-20', to_date='2026-10-26',
                apply=True, stdout=output,
            )

        self.assertIn('нет корректного yclients_company_id', output.getvalue())
        self.assertEqual(self.get_records.call_count, 1)
        self.assertEqual(Booking.objects.get().salon, second_salon)

    def test_unexpected_api_error_is_safe_and_next_salon_runs(self):
        second_salon = Salon.objects.create(
            name='Второй филиал', address='Адрес', latitude=0, longitude=0,
            yclients_company_id='38297',
        )
        second_master = Master.objects.create(name='Второй мастер', )
        MasterSalon.objects.create(master=second_master, salon=second_salon, yclients_staff_id='987654')
        second_record = {
            **self.record, 'id': 42, 'company_id': 38297, 'staff_id': 987654,
        }
        self.get_records.side_effect = [RuntimeError('secret token and client data'), [second_record]]
        output = StringIO()

        with self.assertRaises(CommandError):
            call_command(
                'import_yclients_records', from_date='2026-10-20', to_date='2026-10-26',
                apply=True, stdout=output,
            )

        self.assertIn('RuntimeError', output.getvalue())
        self.assertNotIn('secret token', output.getvalue())
        self.assertEqual(self.get_records.call_count, 2)
        self.assertEqual(Booking.objects.get().salon, second_salon)

    def test_no_show_is_preserved_as_distinct_status(self):
        self.record['attendance'] = -1
        self.run_command(apply=True)
        booking = Booking.objects.get(yclients_record_id='1862046093')
        self.assertEqual(booking.status, Booking.STATUS_NO_SHOW)
        self.assertEqual(booking.yclients_attendance, -1)

