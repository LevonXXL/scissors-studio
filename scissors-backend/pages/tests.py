from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.etree import ElementTree

from django.core.management import call_command
from django.conf import settings
from django.test import TestCase

from masters.models import Master
from salons.models import Salon
from services.models import Service, ServiceCategory

from .management.commands.populate_site_pages import LEGACY_PRIVACY_CONTENT, PRIVACY_CONTENT
from .management.commands.generate_sitemap import public_paths
from .models import Page


class SitemapTests(TestCase):
    def test_command_lists_only_public_pages_and_active_salons(self):
        salons = Page.objects.create(title='Салоны', url='salons')
        Page.objects.create(title='О нас', url='about')
        Page.objects.create(title='Черновик', url='draft', is_published=False)
        Page.objects.create(title='Вход', url='login')
        active_page = Page.objects.create(title='Открытый', url='open', parent=salons)
        inactive_page = Page.objects.create(title='Закрытый', url='closed', parent=salons)
        for slug, page, active in (
            ('open', active_page, True), ('closed', inactive_page, False),
        ):
            Salon.objects.create(
                name=slug, slug=slug, page=page, address='Адрес',
                latitude='0', longitude='0', is_active=active,
            )

        self.assertEqual(public_paths(), ['', 'about', 'price-list', 'salons', 'salons/open'])
        with TemporaryDirectory() as directory:
            output = Path(directory) / 'sitemap.xml'
            call_command('generate_sitemap', '--output', str(output), stdout=StringIO())
            root = ElementTree.parse(output).getroot()
            namespace = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
            locations = [node.text for node in root.findall('s:url/s:loc', namespace)]
            self.assertEqual(locations, [
                f'{settings.SITE_URL}/',
                f'{settings.SITE_URL}/about',
                f'{settings.SITE_URL}/price-list',
                f'{settings.SITE_URL}/salons',
                f'{settings.SITE_URL}/salons/open',
            ])


class PagePathTests(TestCase):
    def test_root_and_nested_paths_follow_hierarchy(self):
        home = Page.objects.create(title='Главная', url='')
        team = Page.objects.create(title='Команда', url='team')
        master = Page.objects.create(title='Мастер', url='master', parent=team)

        self.assertEqual(home.url_path, '')
        self.assertEqual(team.url_path, 'team')
        self.assertEqual(master.url_path, 'team/master')

    def test_renaming_and_moving_subtree_updates_descendants(self):
        team = Page.objects.create(title='Команда', url='team')
        master = Page.objects.create(title='Мастер', url='master', parent=team)
        portfolio = Page.objects.create(title='Портфолио', url='portfolio', parent=master)
        about = Page.objects.create(title='О нас', url='about')

        team.url = 'artists'
        team.save(update_fields=['url'])
        portfolio.refresh_from_db()
        self.assertEqual(portfolio.url_path, 'artists/master/portfolio')

        master.parent = about
        master.save(update_fields=['parent'])
        master.refresh_from_db()
        portfolio.refresh_from_db()
        self.assertEqual(master.url_path, 'about/master')
        self.assertEqual(portfolio.url_path, 'about/master/portfolio')

    def test_mptt_move_to_updates_paths(self):
        team = Page.objects.create(title='Команда', url='team')
        about = Page.objects.create(title='О нас', url='about')
        master = Page.objects.create(title='Мастер', url='master', parent=team)
        portfolio = Page.objects.create(title='Портфолио', url='portfolio', parent=master)

        master.move_to(about, 'last-child')
        master.refresh_from_db()
        portfolio.refresh_from_db()
        self.assertEqual(master.url_path, 'about/master')
        self.assertEqual(portfolio.url_path, 'about/master/portfolio')

    def test_same_slug_is_allowed_in_different_branches(self):
        team = Page.objects.create(title='Команда', url='team')
        about = Page.objects.create(title='О нас', url='about')
        first = Page.objects.create(title='Первый', url='details', parent=team)
        second = Page.objects.create(title='Второй', url='details', parent=about)

        self.assertEqual(first.url_path, 'team/details')
        self.assertEqual(second.url_path, 'about/details')

    def test_content_population_reuses_existing_pages(self):
        old_team = Page.objects.create(title='Команда', url='komanda')
        master = Master.objects.create(name='Тестовый мастер', specialization='Стрижки')

        call_command('populate_site_pages', stdout=StringIO())
        call_command('populate_site_pages', stdout=StringIO())

        self.assertEqual(Page.objects.filter(url_path='').count(), 1)
        self.assertEqual(Page.objects.filter(url_path='team').count(), 1)
        self.assertEqual(Page.objects.filter(url_path='privacy').count(), 1)
        self.assertEqual(Page.objects.filter(url_path=f'team/{master.slug}').count(), 1)
        old_team.refresh_from_db()
        self.assertEqual(old_team.url_path, 'team')

    def test_population_is_repeatable_with_same_named_catalogue_items(self):
        salons = [
            Salon.objects.create(
                name=f'Салон {number}', address='Адрес', latitude=55,
                longitude=37,
            )
            for number in (1, 2)
        ]
        categories = [
            ServiceCategory.objects.create(
                salon=salon, title='Стрижки', yclients_category_id=str(number),
            )
            for number, salon in enumerate(salons, start=1)
        ]
        services = [
            Service.objects.create(
                category=category, title='Женская стрижка',
                yclients_service_id=str(number),
            )
            for number, category in enumerate(categories, start=1)
        ]

        call_command('populate_site_pages', stdout=StringIO())
        first_state = list(Page.objects.order_by('pk').values_list(
            'pk', 'url_path', 'title', 'content', 'meta_title', 'meta_description', 'parent_id',
        ))
        call_command('populate_site_pages', stdout=StringIO())

        self.assertEqual(list(Page.objects.order_by('pk').values_list(
            'pk', 'url_path', 'title', 'content', 'meta_title', 'meta_description', 'parent_id',
        )), first_state)
        for category, service in zip(categories, services):
            category.refresh_from_db()
            service.refresh_from_db()
            self.assertEqual(category.page.parent.url_path, 'services')
            self.assertEqual(service.page.parent_id, category.page_id)
        self.assertNotEqual(categories[0].page_id, categories[1].page_id)

    def test_population_uses_canonical_page_even_with_legacy_name_duplicate(self):
        canonical = Page.objects.create(title='О нас', url='about')
        Page.objects.create(title='О нас', url='old-about')

        call_command('populate_site_pages', stdout=StringIO())
        call_command('populate_site_pages', stdout=StringIO())

        canonical.refresh_from_db()
        self.assertEqual(Page.objects.filter(url_path='about').count(), 1)
        self.assertTrue(canonical.content)
        response = self.client.get('/api/v1/pages/by-path/about/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['url_path'], 'about')

    def test_population_updates_seeded_content_and_preserves_full_privacy_text(self):
        call_command('populate_site_pages', stdout=StringIO())
        about = Page.objects.get(url_path='about')
        about.content = '<p>Текст редактора</p>'
        about.meta_title = 'Заголовок редактора'
        about.meta_description = ''
        about.save()
        privacy = Page.objects.get(url_path='privacy')
        privacy.content = '<p>Полный текст политики</p>'
        privacy.save()

        call_command('populate_site_pages', stdout=StringIO())

        about.refresh_from_db()
        privacy.refresh_from_db()
        self.assertIn('Привет! Я Михаил Стець', about.content)
        self.assertEqual(about.meta_title, 'О нас — Scissors Studio')
        self.assertTrue(about.meta_description)
        self.assertEqual(privacy.content, '<p>Полный текст политики</p>')

    def test_privacy_population_replaces_only_known_placeholder(self):
        privacy = Page.objects.create(
            title='Политика обработки персональных данных', url='privacy',
            content=LEGACY_PRIVACY_CONTENT,
        )

        call_command('populate_site_pages', '--only-privacy', stdout=StringIO())
        privacy.refresh_from_db()
        self.assertEqual(privacy.content, PRIVACY_CONTENT)
        self.assertEqual(Page.objects.count(), 1)

        privacy.title = 'Мой заголовок политики'
        privacy.content = '<p>Изменено в админке</p>'
        privacy.save()
        call_command('populate_site_pages', '--only-privacy', stdout=StringIO())
        privacy.refresh_from_db()
        self.assertEqual(privacy.title, 'Мой заголовок политики')
        self.assertEqual(privacy.content, '<p>Изменено в админке</p>')
        self.assertEqual(Page.objects.count(), 1)
