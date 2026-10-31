from base64 import b64decode
from io import StringIO
from tempfile import TemporaryDirectory

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from filer.models import Image as FilerImage

from pages.models import Page, PagePicture
from services.models import Service, ServiceCategory


class AttachServicePageImagesTests(TestCase):
    def test_dry_run_apply_and_existing_image(self):
        root = Page.objects.get(url_path='uslugi')
        category_page = Page.objects.create(parent=root, url='photo-command', title='Фото')
        category = ServiceCategory.objects.create(title='Фото', code='photo-command',
                                                  page=category_page)
        first_page = Page.objects.create(parent=category_page, url='first', title='Первая')
        second_page = Page.objects.create(parent=category_page, url='second', title='Вторая')
        first_service = Service.objects.create(category=category, page=first_page, title='Первая')
        second_service = Service.objects.create(category=category, page=second_page, title='Вторая')
        gif = b64decode('R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs=')

        with TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            def photo(name):
                return FilerImage.objects.create(
                    original_filename=name, name=name,
                    file=SimpleUploadedFile(name, gif, content_type='image/gif'),
                )

            first_photo = photo('first.gif')
            later_photo = photo('later.gif')
            manual_photo = photo('manual.gif')
            PagePicture.objects.create(page=first_page, image=later_photo, position=1)
            PagePicture.objects.create(page=first_page, image=first_photo, position=0)
            second_service.image = manual_photo
            second_service.save(update_fields=['image'])
            PagePicture.objects.create(page=second_page, image=first_photo, position=0)

            preview = StringIO()
            call_command('attach_service_page_images', stdout=preview)
            first_service.refresh_from_db()
            self.assertIsNone(first_service.image_id)
            self.assertIn('Готово к привязке: 1', preview.getvalue())

            call_command('attach_service_page_images', '--apply', stdout=StringIO())
            first_service.refresh_from_db()
            second_service.refresh_from_db()
            self.assertEqual(first_service.image_id, first_photo.pk)
            self.assertEqual(second_service.image_id, manual_photo.pk)
            self.assertEqual(PagePicture.objects.filter(page=first_page).count(), 2)

            repeated = StringIO()
            call_command('attach_service_page_images', '--apply', stdout=repeated)
            self.assertIn('Привязано: 0', repeated.getvalue())
