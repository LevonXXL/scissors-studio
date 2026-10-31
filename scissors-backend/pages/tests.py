from base64 import b64decode
from importlib import import_module
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from xml.etree import ElementTree

from django.apps import apps
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import connection
from django.test import TestCase, override_settings
from django.utils.html import format_html
from filer.models import Image as FilerImage

from masters.models import Master
from salons.models import Salon
from services.models import Service, ServiceCategory

from .management.commands.populate_site_pages import LEGACY_PRIVACY_CONTENT, PRIVACY_CONTENT
from .management.commands.generate_sitemap import public_paths
from .models import Page, PagePicture


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

        self.assertEqual(public_paths(), ['', 'about', 'salons', 'salons/open', 'uslugi'])
        with TemporaryDirectory() as directory:
            output = Path(directory) / 'sitemap.xml'
            call_command('generate_sitemap', '--output', str(output), stdout=StringIO())
            root = ElementTree.parse(output).getroot()
            namespace = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
            locations = [node.text for node in root.findall('s:url/s:loc', namespace)]
            self.assertEqual(locations, [
                f'{settings.SITE_URL}/',
                f'{settings.SITE_URL}/about',
                f'{settings.SITE_URL}/salons',
                f'{settings.SITE_URL}/salons/open',
                f'{settings.SITE_URL}/uslugi',
            ])


class PagePathTests(TestCase):
    def test_copied_master_bio_cleanup_preserves_edited_page_content(self):
        team = Page.objects.create(title='Команда', url='team')
        copied_page = Page.objects.create(title='Автоматическая', url='copied', parent=team)
        edited_page = Page.objects.create(title='Авторская', url='edited', parent=team,
                                          content='<p>Авторский текст</p>')
        bio = '<p>Описание <strong>мастера</strong></p>'
        Master.objects.create(name='Первый', page=copied_page, bio=bio)
        Master.objects.create(name='Второй', page=edited_page, bio=bio)
        copied_page.content = format_html('<p>{}</p>', bio)
        copied_page.save(update_fields=['content'])

        migration = import_module('masters.migrations.0019_remove_copied_bio_from_pages')
        migration.remove_copied_bio(apps, SimpleNamespace(connection=connection))

        copied_page.refresh_from_db()
        edited_page.refresh_from_db()
        self.assertEqual(copied_page.content, '')
        self.assertEqual(edited_page.content, '<p>Авторский текст</p>')

    def test_master_page_returns_profile_photo_bio_content_and_gallery(self):
        team = Page.objects.create(title='Команда', url='team')
        page = Page.objects.create(title='Страница Светланы', url='svetlana', parent=team,
                                   content='<p>Дополнительный текст страницы</p>')
        master = Master.objects.create(name='Светлана Миронова', page=page,
                                       bio='<p>Стилист Светлана</p><ul><li>Обучение</li></ul>')
        gif = b64decode('R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs=')

        with TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            photo = FilerImage.objects.create(
                original_filename='portrait.gif', name='Портрет',
                file=SimpleUploadedFile('portrait.gif', gif, content_type='image/gif'),
            )
            work = FilerImage.objects.create(
                original_filename='work.gif', name='Работа',
                file=SimpleUploadedFile('work.gif', gif, content_type='image/gif'),
            )
            master.photo = photo
            master.save(update_fields=['photo'])
            PagePicture.objects.create(page=page, image=work, position=0)

            response = self.client.get('/api/v1/pages/by-path/team/svetlana/')

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['master']['name'], master.name)
            self.assertEqual(response.data['master']['bio'], master.bio)
            self.assertTrue(response.data['master']['photo'].endswith(photo.url))
            self.assertEqual(response.data['content'], page.content)
            self.assertTrue(response.data['pictures'][0]['image'].endswith(work.url))

    def test_old_catalogue_pages_are_not_public_after_excel_import(self):
        root = Page.objects.get(url_path='uslugi')
        old_category_page = Page.objects.create(title='Старые стрижки', url='old-cuts', parent=root)
        old_service_page = Page.objects.create(title='Старая стрижка', url='old-cut', parent=old_category_page)
        old_category = ServiceCategory.objects.create(
            title='Старые стрижки', page=old_category_page, is_active=False,
        )
        Service.objects.create(category=old_category, page=old_service_page, title='Старая стрижка')
        current_category_page = Page.objects.create(title='Для волос', url='hair', parent=root)
        current_service_page = Page.objects.create(title='Женская стрижка', url='cut', parent=current_category_page)
        current_category = ServiceCategory.objects.create(title='Для волос', code='hair', page=current_category_page)
        Service.objects.create(category=current_category, page=current_service_page, title='Женская стрижка')
        hidden_service_page = Page.objects.create(title='Скрытая услуга', url='hidden', parent=current_category_page)
        Service.objects.create(
            category=current_category, page=hidden_service_page, title='Скрытая услуга', is_active=False,
        )

        self.assertEqual(self.client.get('/api/v1/pages/by-path/uslugi/old-cuts/').status_code, 404)
        self.assertEqual(self.client.get('/api/v1/pages/by-path/uslugi/old-cuts/old-cut/').status_code, 404)
        self.assertEqual(self.client.get('/api/v1/pages/by-path/uslugi/hair/hidden/').status_code, 404)
        self.assertEqual(self.client.get('/api/v1/pages/by-path/uslugi/hair/cut/').status_code, 200)

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
        master = Master.objects.create(name='Тестовый мастер', bio='<p>Описание мастера</p>')

        call_command('populate_site_pages', stdout=StringIO())
        call_command('populate_site_pages', stdout=StringIO())

        self.assertEqual(Page.objects.filter(url_path='').count(), 1)
        self.assertEqual(Page.objects.filter(url_path='team').count(), 1)
        self.assertEqual(Page.objects.filter(url_path='privacy').count(), 1)
        self.assertEqual(Page.objects.filter(url_path=f'team/{master.slug}').count(), 1)
        master.refresh_from_db()
        self.assertEqual(master.page.content, '')
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
        categories = [ServiceCategory.objects.create(title='Стрижки', code='hair')]
        services = [Service.objects.create(category=categories[0], title='Женская стрижка')]

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
            self.assertEqual(category.page.parent.url_path, 'uslugi')
            self.assertEqual(service.page.parent_id, category.page_id)
        self.assertEqual(Page.objects.filter(url_path=categories[0].page.url_path).count(), 1)

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
        self.assertEqual(Page.objects.count(), 2)

        privacy.title = 'Мой заголовок политики'
        privacy.content = '<p>Изменено в админке</p>'
        privacy.save()
        call_command('populate_site_pages', '--only-privacy', stdout=StringIO())
        privacy.refresh_from_db()
        self.assertEqual(privacy.title, 'Мой заголовок политики')
        self.assertEqual(privacy.content, '<p>Изменено в админке</p>')
        self.assertEqual(Page.objects.count(), 2)
