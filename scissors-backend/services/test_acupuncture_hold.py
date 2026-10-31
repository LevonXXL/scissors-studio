from datetime import timedelta
from importlib import import_module

from django.apps import apps
from django.test import TestCase
from django.utils import timezone

from booking.models import Booking
from pages.management.commands.generate_sitemap import public_paths
from pages.models import Page
from salons.models import Salon

from .excel_import import apply_preview
from .models import Service, ServiceCategory, ServicePrice, ServiceSalon


hold_migration = import_module('services.migrations.0006_hold_acupuncture_until_review')


class AcupunctureHoldTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.salon = Salon.objects.create(name='Scissors Зеленоград', slug='zelenograd',
                                         address='Адрес', latitude=55, longitude=37)
        root = Page.objects.get(url_path='uslugi')
        category_page = Page.objects.create(title='Косметология', url='cosmetology', parent=root)
        cls.target_page = Page.objects.create(
            title=hold_migration.ORIGINAL_TITLE,
            url=hold_migration.PAGE_PATH.rsplit('/', 1)[1], parent=category_page,
        )
        cls.category = ServiceCategory.objects.create(
            title='Косметология', code='cosmetology', page=category_page,
        )
        cls.target = Service.objects.create(
            category=cls.category, page=cls.target_page,
            title=hold_migration.ORIGINAL_TITLE,
            description=hold_migration.ORIGINAL_DESCRIPTION,
        )
        cls.target_offer = ServiceSalon.objects.create(service=cls.target, salon=cls.salon)
        ServicePrice.objects.create(salon_service=cls.target_offer, level='', amount=2000)
        cls.other = Service.objects.create(category=cls.category, title='Другая услуга')
        ServiceSalon.objects.create(service=cls.other, salon=cls.salon)

    def hold(self):
        hold_migration.hold_acupuncture(apps, None)

    def test_hold_preserves_data_and_closes_catalogue_page_booking_and_sitemap(self):
        self.hold()
        self.hold()
        self.target.refresh_from_db()
        self.target_page.refresh_from_db()
        self.target_offer.refresh_from_db()
        self.assertFalse(self.target.is_active)
        self.assertFalse(self.target_page.is_published)
        self.assertFalse(self.target_offer.is_active)
        self.assertEqual(self.target.description, hold_migration.DRAFT_DESCRIPTION)
        self.assertEqual(self.target_page.title, 'Акупунктура тела')
        self.assertIn('<h2>', self.target_page.content)
        self.assertNotIn('2000', self.target_page.content)
        self.assertEqual(self.target_page.meta_description, hold_migration.DRAFT_META_DESCRIPTION)
        self.assertEqual(self.target_offer.prices.get().amount, 2000)
        self.assertTrue(Service.objects.filter(pk=self.target.pk).exists())

        catalogue = self.client.get('/api/v1/service-categories/', {'salon': self.salon.pk})
        self.assertEqual(catalogue.status_code, 200)
        categories = catalogue.data['results'] if isinstance(catalogue.data, dict) else catalogue.data
        service_ids = {service['id'] for category in categories for service in category['services']}
        self.assertNotIn(self.target.pk, service_ids)
        self.assertIn(self.other.pk, service_ids)
        self.assertEqual(self.client.get(f'/api/v1/pages/by-path/{self.target_page.url_path}/').status_code, 404)
        pages = self.client.get('/api/v1/pages/')
        page_rows = pages.data['results'] if isinstance(pages.data, dict) else pages.data
        self.assertNotIn(self.target_page.pk, {item['id'] for item in page_rows})
        options = self.client.get('/api/v1/booking-options/', {'salon': self.salon.pk})
        self.assertEqual(options.status_code, 200)
        self.assertNotIn(self.target.pk, {item['id'] for item in options.data['services']})
        self.assertIn(self.other.pk, {item['id'] for item in options.data['services']})
        request = self.client.post('/api/v1/booking-requests/', {
            'salon': self.salon.pk, 'service_ids': [self.target.pk],
            'requested_start': (timezone.now() + timedelta(days=2)).isoformat(),
            'name': 'Клиент', 'phone': '79991234567',
        }, content_type='application/json')
        self.assertEqual(request.status_code, 400)
        self.assertFalse(Booking.objects.exists())
        self.assertNotIn(self.target_page.url_path, public_paths())

    def test_reimport_does_not_republish_held_service(self):
        self.hold()
        preview = {'rows': [{
            'row': 42, 'category': 'cosmetology', 'group': 'Тело — ручные техники',
            'subgroup': '', 'title': hold_migration.ORIGINAL_TITLE,
            'description': hold_migration.ORIGINAL_DESCRIPTION,
            'duration_seconds': None, 'conditions': '',
            'prices': [{'level': '', 'status': 'amount', 'amount': '2000'}],
        }], 'errors': [], 'issues': []}
        apply_preview(preview, self.salon, {}, {42})
        self.target.refresh_from_db()
        self.target_page.refresh_from_db()
        self.assertFalse(self.target.is_active)
        self.assertFalse(self.target_page.is_published)
        self.assertEqual(Service.objects.filter(title=hold_migration.ORIGINAL_TITLE).count(), 1)

    def test_hold_preserves_existing_editorial_copy(self):
        self.target_page.content = '<h2>Текст редактора</h2><p>Сохранить при проверке.</p>'
        self.target_page.meta_description = 'Редакторское описание'
        self.target_page.save(update_fields=['content', 'meta_description'])
        self.hold()
        self.target_page.refresh_from_db()
        self.assertFalse(self.target_page.is_published)
        self.assertIn('Текст редактора', self.target_page.content)
        self.assertEqual(self.target_page.meta_description, 'Редакторское описание')
