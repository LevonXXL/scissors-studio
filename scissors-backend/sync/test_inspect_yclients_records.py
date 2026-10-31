"""Focused tests for the read-only YCLIENTS records inspector."""

from io import StringIO
from types import SimpleNamespace
from unittest.mock import Mock, patch

import requests
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings


@override_settings(YCLIENTS_PARTNER_TOKEN='test-partner', YCLIENTS_USER_TOKEN='test-user')
class InspectYclientsRecordsTests(SimpleTestCase):
    def setUp(self):
        salon_exclude = patch('sync.management.commands.inspect_yclients_records.Salon.objects.exclude')
        client_type = patch('sync.management.commands.inspect_yclients_records.YClientsDataClient')
        api_get = patch('sync.management.commands.inspect_yclients_records.requests.get')
        api_post = patch('sync.management.commands.inspect_yclients_records.requests.post')
        self.salon_exclude = salon_exclude.start()
        self.client_type = client_type.start()
        self.api_get = api_get.start()
        self.api_post = api_post.start()
        for item in (salon_exclude, client_type, api_get, api_post):
            self.addCleanup(item.stop)

        self.salons = [SimpleNamespace(pk=7, name='Тестовый салон', yclients_company_id='12345')]
        self.salon_exclude.return_value.exclude.return_value.order_by.return_value = self.salons
        self.client_type.return_value.BASE_URL = 'https://api.yclients.com/api/v1'
        self.client_type.return_value.timeout = 20
        self.client_type.return_value._headers.return_value = {'Authorization': 'test-only'}

    def run_command(self):
        output = StringIO()
        call_command(
            'inspect_yclients_records',
            from_date='2026-10-20', to_date='2026-10-26', stdout=output,
        )
        return output.getvalue()

    def run_failed_command(self):
        output = StringIO()
        with self.assertRaises(CommandError) as caught:
            call_command(
                'inspect_yclients_records', from_date='2026-10-20',
                to_date='2026-10-26', stdout=output,
            )
        return output.getvalue(), str(caught.exception)

    def test_reads_pages_with_get_and_omits_client_data(self):
        first = Mock(status_code=200)
        first.json.return_value = {
            'success': True,
            'data': [
                {'id': 1, 'datetime': '2026-10-21T10:00:00+03:00', 'attendance': 0,
                 'staff_id': None, 'services': [{'id': 5}], 'seance_length': 3600,
                 'client': {'name': 'Не выводить', 'phone': '79990000000'}},
                {'id': 2, 'datetime': '2026-10-21T11:00:00+03:00', 'staff_id': 42,
                 'services': []},
            ],
            'meta': {'total_count': 3},
        }
        second = Mock(status_code=200)
        second.json.return_value = {
            'success': True,
            'data': [{'id': 3, 'datetime': '2026-10-22T12:00:00+03:00', 'services': []}],
            'meta': {'total_count': 3},
        }
        self.api_get.side_effect = [first, second]
        with patch('sync.management.commands.inspect_yclients_records.PAGE_SIZE', 2):
            output = self.run_command()

        self.assertIn('Филиал #7 (Тестовый салон), company_id=12345: 3 записей.', output)
        self.assertIn('Всего записей из доступных филиалов: 3', output)
        self.assertIn('специалист=не назначен', output)
        self.assertIn('специалист=42', output)
        self.assertIn('услуги=5', output)
        self.assertNotIn('Не выводить', output)
        self.assertNotIn('79990000000', output)
        self.assertEqual(self.api_get.call_count, 2)
        self.assertEqual([call.kwargs['params']['page'] for call in self.api_get.call_args_list], [1, 2])
        self.assertEqual(self.api_get.call_args_list[0].kwargs['params']['start_date'], '2026-10-20')
        self.assertEqual(self.api_get.call_args_list[0].kwargs['params']['end_date'], '2026-10-26')
        self.api_post.assert_not_called()

    def test_reads_every_local_branch(self):
        self.salons.append(SimpleNamespace(pk=8, name='Второй салон', yclients_company_id='67890'))
        first = Mock(status_code=200)
        first.json.return_value = {'success': True, 'data': [{'id': 1, 'services': []}], 'meta': {'total_count': 1}}
        second = Mock(status_code=200)
        second.json.return_value = {'success': True, 'data': [{'id': 2, 'services': []}], 'meta': {'total_count': 1}}
        self.api_get.side_effect = [first, second]

        output = self.run_command()

        self.assertIn('Филиал #7', output)
        self.assertIn('Филиал #8', output)
        self.assertIn('Всего записей из доступных филиалов: 2', output)
        self.assertEqual(
            [call.args[0] for call in self.api_get.call_args_list],
            ['https://api.yclients.com/api/v1/records/12345', 'https://api.yclients.com/api/v1/records/67890'],
        )
        self.api_post.assert_not_called()

    def test_no_local_branches_is_an_error(self):
        self.salons.clear()
        with self.assertRaises(CommandError) as caught:
            self.run_command()
        self.assertIn('нет филиалов', str(caught.exception))
        self.api_get.assert_not_called()

    def test_forbidden_is_error_with_status_but_without_response_body(self):
        response = Mock(status_code=403, text='secret token and client data')
        self.api_get.return_value = response

        output, error = self.run_failed_command()
        self.assertIn('Филиал #7', output)
        self.assertIn('HTTP 403', output)
        self.assertIn('права User-токена', output)
        self.assertNotIn('secret token', output + error)
        self.assertIn('с ошибками: 1', output)
        self.api_post.assert_not_called()

    def test_forbidden_branch_does_not_skip_other_branches(self):
        self.salons.append(SimpleNamespace(pk=8, name='Второй салон', yclients_company_id='67890'))
        forbidden = Mock(status_code=403, text='secret token')
        allowed = Mock(status_code=200)
        allowed.json.return_value = {
            'success': True, 'data': [{'id': 2, 'services': []}], 'meta': {'total_count': 1},
        }
        self.api_get.side_effect = [forbidden, allowed]
        output, error = self.run_failed_command()

        self.assertIn('HTTP 403', output)
        self.assertIn('Филиал #7', output)
        self.assertIn('Филиал #8', output)
        self.assertIn('Всего записей из доступных филиалов: 1', output)
        self.assertIn('1 из 2 филиалов', error)
        self.assertEqual(self.api_get.call_count, 2)
        self.api_post.assert_not_called()

    def test_invalid_local_company_id_does_not_skip_other_branches(self):
        self.salons[0].yclients_company_id = 'bad-id'
        self.salons.append(SimpleNamespace(pk=8, name='Второй салон', yclients_company_id='67890'))
        allowed = Mock(status_code=200)
        allowed.json.return_value = {'success': True, 'data': [], 'meta': {'total_count': 0}}
        self.api_get.return_value = allowed

        output, _ = self.run_failed_command()

        self.assertIn('Некорректный yclients_company_id', output)
        self.assertIn('Филиал #8', output)
        self.assertEqual(self.api_get.call_count, 1)

    def test_unexpected_branch_error_does_not_skip_other_branches(self):
        self.salons.append(SimpleNamespace(pk=8, name='Второй салон', yclients_company_id='67890'))
        self.client_type.return_value._headers.side_effect = [ValueError('secret token'), {'Authorization': 'test-only'}]
        allowed = Mock(status_code=200)
        allowed.json.return_value = {'success': True, 'data': [], 'meta': {'total_count': 0}}
        self.api_get.return_value = allowed

        output, _ = self.run_failed_command()

        self.assertIn('непредвиденная ошибка обработки (ValueError)', output)
        self.assertNotIn('secret token', output)
        self.assertIn('Филиал #8', output)
        self.assertEqual(self.api_get.call_count, 1)

    def test_malformed_response_is_not_reported_as_empty_list(self):
        response = Mock(status_code=200)
        response.json.return_value = {'success': True, 'data': {'unexpected': 'format'}}
        self.api_get.return_value = response

        output, _ = self.run_failed_command()
        self.assertIn('HTTP 200', output)
        self.assertIn('формат списка записей', output)

    def test_network_error_has_stage_without_exposing_request(self):
        self.api_get.side_effect = requests.ConnectionError('secret token and client data')

        output, error = self.run_failed_command()
        self.assertIn('страница 1', output)
        self.assertIn('HTTP —', output)
        self.assertNotIn('secret token', output + error)

    def test_invalid_period_stops_before_api_request(self):
        with self.assertRaises(CommandError) as caught:
            call_command(
                'inspect_yclients_records',
                from_date='2026-10-26', to_date='2026-10-20', stdout=StringIO(),
            )
        self.assertIn('Этап «параметры»', str(caught.exception))
        self.api_get.assert_not_called()
