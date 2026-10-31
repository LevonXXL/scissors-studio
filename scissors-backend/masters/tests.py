from importlib import import_module

from django.apps import apps
from django.test import TestCase

from salons.models import Salon
from .models import Master, MasterSalon


class NailLevelMigrationTests(TestCase):
    def test_confirmed_top_master_is_scoped_to_maria_in_zelenograd(self):
        zelenograd = Salon.objects.create(name='Scissors Зеленоград 17/мкр',
                                          address='Адрес', latitude=55, longitude=37)
        moscow = Salon.objects.create(name='Scissors Красные Ворота',
                                      address='Адрес', latitude=55, longitude=37)
        maria = Master.objects.create(name='Мария Ким', )
        other = Master.objects.create(name='Мария Ким', )
        MasterSalon.objects.create(master=maria, salon=zelenograd)
        MasterSalon.objects.create(master=other, salon=moscow)

        migration = import_module('masters.migrations.0014_maria_top_nail_master')
        migration.set_confirmed_top_nail_master(apps, None)

        maria.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual(maria.price_level, 'top_nail_master')
        self.assertEqual(other.price_level, '')


class MasterCatalogueTests(TestCase):
    def test_api_returns_confirmed_price_level(self):
        master = Master.objects.create(name='Мастер', yclients_user_id='price-level-test',
                                       price_level='top_stylist')

        response = self.client.get('/api/v1/masters/')
        self.assertEqual(response.status_code, 200)
        rows = response.data['results'] if isinstance(response.data, dict) else response.data
        item = next(row for row in rows if row['id'] == master.pk)
        self.assertEqual(item['price_level_display'], 'Топ-стилист')
        self.assertNotIn('category_display', item)
        self.assertNotIn('specialization', item)
