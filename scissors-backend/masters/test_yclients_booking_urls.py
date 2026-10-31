from importlib import import_module
from types import SimpleNamespace

from django.apps import apps
from django.db import connection
from django.test import TestCase

from pages.models import Page
from salons.models import Salon

from .models import Master, MasterSalon


class YclientsBookingUrlsTests(TestCase):
    def setUp(self):
        self.zelenograd = Salon.objects.create(
            name='Зеленоград', address='Адрес', latitude=55, longitude=37,
            yclients_company_id='38297',
        )
        self.moscow = Salon.objects.create(
            name='Красные Ворота', address='Адрес', latitude=55, longitude=37,
            yclients_company_id='128411',
        )
        team = Page.objects.create(title='Команда', url='team')
        page = Page.objects.create(title='Михаил Стець', url='mikhail', parent=team)
        self.mikhail = Master.objects.create(
            name='Михаил Стець', 
            yclients_user_id='763752', page=page,
        )
        self.zelenograd_link = MasterSalon.objects.create(
            master=self.mikhail, salon=self.zelenograd,
            yclients_staff_id='61540',
        )
        self.moscow_link = MasterSalon.objects.create(
            master=self.mikhail, salon=self.moscow,
            yclients_staff_id='310282',
        )

    def test_migration_sets_branch_specific_urls_without_overwriting_edits(self):
        editor = SimpleNamespace(connection=connection)
        import_module('salons.migrations.0009_salon_yclients_booking_url').set_booking_urls(apps, editor)
        self.moscow_link.yclients_booking_url = 'https://example.com/manual'
        self.moscow_link.save(update_fields=['yclients_booking_url'])
        import_module('masters.migrations.0015_mastersalon_yclients_booking_url').set_booking_urls(apps, editor)

        self.zelenograd.refresh_from_db()
        self.moscow.refresh_from_db()
        self.zelenograd_link.refresh_from_db()
        self.moscow_link.refresh_from_db()
        self.assertEqual(self.zelenograd.yclients_booking_url, 'https://n20037.yclients.ru')
        self.assertEqual(self.moscow.yclients_booking_url, 'https://n117909.yclients.ru')
        self.assertEqual(self.zelenograd_link.yclients_booking_url, 'https://n2077170.yclients.ru')
        self.assertEqual(self.moscow_link.yclients_booking_url, 'https://example.com/manual')

    def test_public_api_exposes_salon_and_each_master_salon_url(self):
        self.zelenograd.yclients_booking_url = 'https://n20037.yclients.ru'
        self.zelenograd.save(update_fields=['yclients_booking_url'])
        self.zelenograd_link.yclients_booking_url = 'https://n2077170.yclients.ru'
        self.zelenograd_link.save(update_fields=['yclients_booking_url'])
        self.moscow.yclients_booking_url = 'https://n117909.yclients.ru'
        self.moscow.save(update_fields=['yclients_booking_url'])
        self.moscow_link.yclients_booking_url = 'https://n1022952.yclients.ru'
        self.moscow_link.save(update_fields=['yclients_booking_url'])

        salon_response = self.client.get(f'/api/v1/salons/by-slug/{self.zelenograd.slug}/')
        self.assertEqual(salon_response.status_code, 200)
        self.assertEqual(salon_response.json()['yclients_booking_url'], 'https://n20037.yclients.ru')

        master_response = self.client.get('/api/v1/masters/')
        self.assertEqual(master_response.status_code, 200)
        masters = master_response.json()
        if isinstance(masters, dict):
            masters = masters['results']
        links = {item['id']: item['yclients_booking_url'] for item in masters[0]['salon_details']}
        self.assertEqual(links, {
            self.zelenograd.id: 'https://n2077170.yclients.ru',
            self.moscow.id: 'https://n1022952.yclients.ru',
        })

        page_response = self.client.get('/api/v1/pages/by-path/team/mikhail/')
        self.assertEqual(page_response.status_code, 200)
        page_links = {item['salon_id']: item['url'] for item in page_response.json()['yclients_booking_links']}
        self.assertEqual(page_links, links)
