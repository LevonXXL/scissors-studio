from io import StringIO
from pathlib import Path
from shutil import copyfile
from tempfile import TemporaryDirectory

from django.contrib import admin
from django.core.management import call_command
from django.test import TestCase, override_settings
from filer.fields.image import FilerImageField

from pages.admin import PageAdmin, PagePictureInline
from pages.models import Page, PagePicture
from salons.models import Salon
from services.models import Service, ServiceCategory, ServiceSalon
from services.management.commands.import_tilda_service_images import get_or_upload
from services.tilda_images import CATEGORY_IMAGES, load_images, match_image


ASSETS = Path(__file__).resolve().parents[2] / 'scissors-frontend' / 'tilda_assets'


class TildaServiceImageTests(TestCase):
    def test_nail_group_photo_is_shown_once_and_old_service_copy_is_removed(self):
        card = next(item for item in load_images()['nails'] if item['title'] == 'Маникюр')
        root = Page.objects.get(url_path='uslugi')
        category_page = Page.objects.create(parent=root, url='nails', title='Ногтевой сервис')
        service_page = Page.objects.create(parent=category_page, url='manicure', title='Маникюр')
        category = ServiceCategory.objects.create(title='Ногтевой сервис', code='nails',
                                                  page=category_page)
        service = Service.objects.create(category=category, page=service_page,
                                         title='Маникюр — комбинированная техника',
                                         group_title='Маникюр')
        salon = Salon.objects.create(name='Зеленоград', slug='zelenograd', address='Адрес',
                                     latitude=55, longitude=37)
        ServiceSalon.objects.create(service=service, salon=salon)
        self.assertIsNone(match_image(service, load_images())[0])

        with TemporaryDirectory() as directory:
            source_root = Path(directory) / 'assets'
            source = source_root / card['asset']
            source.parent.mkdir(parents=True)
            copyfile(ASSETS / card['asset'], source)
            with override_settings(MEDIA_ROOT=Path(directory) / 'media'):
                image = get_or_upload(source, card['asset'], card['title'], {})
                PagePicture.objects.create(page=service_page, image=image, alt=service.title)
                output = StringIO()
                call_command('import_tilda_service_images', '--source-path', str(source_root),
                             stdout=output)
                self.assertIn('ошибочных фото услуг к удалению: 1', output.getvalue())
                self.assertEqual(PagePicture.objects.filter(page=service_page).count(), 1)

                call_command('import_tilda_service_images', '--source-path', str(source_root),
                             '--apply', stdout=StringIO())
                self.assertFalse(PagePicture.objects.filter(page=service_page).exists())
                self.assertEqual(PagePicture.objects.filter(page=category_page, alt='Маникюр').count(), 1)

                call_command('import_tilda_service_images', '--source-path', str(source_root),
                             '--apply', stdout=StringIO())
                self.assertEqual(PagePicture.objects.filter(page=category_page).count(), 1)
                response = self.client.get(f'/api/v1/service-categories/?salon={salon.pk}')
                data = response.data['results'] if isinstance(response.data, dict) else response.data
                self.assertEqual(data[0]['group_images'][0]['name'], 'Маникюр')
                self.assertEqual(data[0]['services'][0]['image'], '')

    def test_command_imports_once_and_api_uses_page_picture(self):
        card = next(item for item in load_images()['hair']
                    if item['title'] == 'ЖЕНСКАЯ СТРИЖКА')
        root = Page.objects.get(url_path='uslugi')
        category_page = Page.objects.create(parent=root, url='hair', title='Для волос')
        service_page = Page.objects.create(parent=category_page, url='zhenskaya-strizhka',
                                           title='Женская стрижка')
        category = ServiceCategory.objects.create(title='Для волос', code='hair', page=category_page)
        service = Service.objects.create(category=category, page=service_page, title='Женская стрижка')
        salon = Salon.objects.create(name='Зеленоград', slug='zelenograd', address='Адрес',
                                     latitude=55, longitude=37)
        ServiceSalon.objects.create(service=service, salon=salon)

        with TemporaryDirectory() as directory:
            source = Path(directory) / 'assets' / card['asset']
            source.parent.mkdir(parents=True)
            copyfile(ASSETS / card['asset'], source)
            category_source = Path(directory) / 'assets' / CATEGORY_IMAGES['hair']
            category_source.parent.mkdir(parents=True)
            copyfile(ASSETS / CATEGORY_IMAGES['hair'], category_source)
            with override_settings(MEDIA_ROOT=Path(directory) / 'media'):
                output = StringIO()
                call_command('import_tilda_service_images', '--source-path',
                             str(source.parents[1]), stdout=output)
                self.assertIn('Готово к добавлению: 1', output.getvalue())
                self.assertEqual(PagePicture.objects.count(), 0)

                call_command('import_tilda_service_images', '--source-path',
                             str(source.parents[1]), '--apply', stdout=StringIO())
                category.refresh_from_db()
                self.assertIsNotNone(category.image_id)
                picture = PagePicture.objects.get(page=service_page)
                self.assertIsNotNone(picture.image_id)
                self.assertEqual(picture.alt, service.title)

                call_command('import_tilda_service_images', '--source-path',
                             str(source.parents[1]), '--apply', stdout=StringIO())
                self.assertEqual(PagePicture.objects.filter(page=service_page).count(), 1)

                response = self.client.get(f'/api/v1/service-categories/?salon={salon.pk}')
                self.assertEqual(response.status_code, 200)
                data = response.data['results'] if isinstance(response.data, dict) else response.data
                self.assertIn('/media/', data[0]['image_url'])
                item = next(item for category in data for item in category['services'])
                self.assertIn('/media/', item['image'])
                root_response = self.client.get('/api/v1/service-categories/')
                root_data = root_response.data['results'] if isinstance(root_response.data, dict) else root_response.data
                self.assertEqual(data[0]['image_url'], root_data[0]['image_url'])
                self.assertEqual(item['image'], self.client.get(
                    '/api/v1/pages/by-path/uslugi/hair/zhenskaya-strizhka/',
                ).data['pictures'][0]['image'])

        self.assertIn(PagePictureInline, PageAdmin.inlines)
        self.assertIsInstance(PagePicture._meta.get_field('image'), FilerImageField)
        self.assertIsInstance(ServiceCategory._meta.get_field('image'), FilerImageField)
        self.assertEqual(admin.site._registry[Page].inlines, (PagePictureInline,))
        self.assertIn('image', admin.site._registry[ServiceCategory].form.base_fields)
        self.assertNotIn('image_path', admin.site._registry[ServiceCategory].form.base_fields)
