from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from masters.models import Master, MasterSalon
from salons.models import Salon
from sync.master_price_levels import inferred_price_level


class MasterPriceLevelBackfillTests(TestCase):
    def setUp(self):
        self.first = Salon.objects.create(
            name='Первый', address='Адрес', latitude=55, longitude=37,
            yclients_company_id='100')
        self.second = Salon.objects.create(
            name='Второй', address='Адрес', latitude=55, longitude=37,
            yclients_company_id='200')
        self.stylist = Master.objects.create(name='Стилист', yclients_user_id='10')
        self.conflict = Master.objects.create(name='Разные должности', yclients_user_id='20')
        self.curated = Master.objects.create(name='Подтверждённый', yclients_user_id='30',
                                              price_level='nail_master')
        self.founder = Master.objects.create(name='Михаил Стець', yclients_user_id='40',
                                              price_level='art_director')
        for master, first_id, second_id in (
            (self.stylist, '11', '12'), (self.conflict, '21', '22'),
            (self.curated, '31', '32'), (self.founder, '41', '42'),
        ):
            MasterSalon.objects.create(master=master, salon=self.first,
                                       yclients_staff_id=first_id)
            MasterSalon.objects.create(master=master, salon=self.second,
                                       yclients_staff_id=second_id)

    def staff(self, staff_id, user_id, name, position):
        return {'id': staff_id, 'user_id': user_id, 'name': name,
                'position': {'title': position}}

    @patch('sync.management.commands.backfill_master_price_levels.YClientsDataClient')
    def test_preview_and_apply_only_unambiguous_missing_levels(self, client_class):
        client_class.return_value.get_staff.side_effect = [
            [self.staff('11', '10', 'Стилист', 'Стилист'),
             self.staff('21', '20', 'Разные должности', 'Стилист'),
             self.staff('31', '30', 'Подтверждённый', 'Мастер-модельер'),
             self.staff('41', '40', 'Михаил Стець', 'Топ-стилист')],
            [self.staff('12', '10', 'Стилист', 'Стилист'),
             self.staff('22', '20', 'Разные должности', 'Мастер-модельер'),
             self.staff('32', '30', 'Подтверждённый', 'Мастер-модельер'),
             self.staff('42', '40', 'Михаил Стець', 'Топ-стилист')],
        ] * 2
        output = StringIO()
        call_command('backfill_master_price_levels', stdout=output)
        self.stylist.refresh_from_db()
        self.assertEqual(self.stylist.price_level, '')
        self.assertIn('Кандидатов: 1', output.getvalue())
        self.assertIn('конфликт: 1', output.getvalue())

        call_command('backfill_master_price_levels', '--apply', stdout=StringIO())
        for master in (self.stylist, self.conflict, self.curated, self.founder):
            master.refresh_from_db()
        self.assertEqual(self.stylist.price_level, 'stylist')
        self.assertEqual(self.conflict.price_level, '')
        self.assertEqual(self.curated.price_level, 'nail_master')
        self.assertEqual(self.founder.price_level, 'art_director')

    def test_free_text_is_used_only_without_position(self):
        self.assertEqual(inferred_price_level({'specialization': 'Старший Нейл мастер'}),
                         'top_nail_master')
        self.assertIsNone(inferred_price_level({
            'position': {'title': 'Администратор'}, 'specialization': 'Стилист'}))
        self.assertIsNone(inferred_price_level({
            'position': {'title': 'Арт-директор'}}))
