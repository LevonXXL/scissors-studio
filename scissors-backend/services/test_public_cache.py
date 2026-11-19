from django.core.cache import caches
from django.test import TestCase, override_settings

from pages.models import Page
from salons.models import Salon

from .models import Service, ServiceCategory, ServiceSalon


@override_settings(DEBUG=False)
class ServiceCategoryMenuTests(TestCase):
    def setUp(self):
        caches['public_content'].clear()
        self.page = Page.objects.create(url='menu-cache-test', title='Название страницы')
        self.category = ServiceCategory.objects.create(
            title='Название категории', code='menu-cache-test', page=self.page,
        )
        salon = Salon.objects.create(name='Салон', address='Адрес', latitude=55, longitude=37)
        self.service_page = Page.objects.create(parent=self.page, url='service', title='Услуга')
        self.service = Service.objects.create(
            category=self.category, page=self.service_page, title='Услуга',
        )
        ServiceSalon.objects.create(service=self.service, salon=salon)

    def tearDown(self):
        caches['public_content'].clear()

    def test_menu_returns_only_the_label_and_url_path(self):
        response = self.client.get('/api/v1/service-categories/menu/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [{
            'link_title': 'Название страницы',
            'url_path': 'menu-cache-test',
        }])

    def test_page_edit_invalidates_cached_menu_after_commit(self):
        first = self.client.get('/api/v1/service-categories/menu/').json()
        self.assertEqual(first[0]['link_title'], 'Название страницы')

        with self.captureOnCommitCallbacks(execute=True):
            self.page.link_title = 'Короткое название'
            self.page.save(update_fields=['link_title'])

        second = self.client.get('/api/v1/service-categories/menu/').json()
        self.assertEqual(second[0]['link_title'], 'Короткое название')

    def test_service_edit_invalidates_cached_catalogue_after_commit(self):
        url = '/api/v1/service-categories/'
        first = self.client.get(url).json()
        self.assertEqual(first['results'][0]['services'][0]['title'], 'Услуга')

        with self.captureOnCommitCallbacks(execute=True):
            self.service.title = 'Обновлённая услуга'
            self.service.save(update_fields=['title'])

        second = self.client.get(url).json()
        self.assertEqual(second['results'][0]['services'][0]['title'], 'Обновлённая услуга')
