from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image


class CkeditorUploadTests(TestCase):
    def setUp(self):
        buffer = BytesIO()
        Image.new('RGB', (2, 2), 'red').save(buffer, format='PNG')
        self.image_bytes = buffer.getvalue()
        self.staff = get_user_model().objects.create_user('editor', password='test', is_staff=True)

    def upload(self, name='../../submitted-name.png'):
        return self.client.post('/ckeditor5/image_upload/', {
            'upload': SimpleUploadedFile(name, self.image_bytes, content_type='image/png'),
        })

    def test_requires_staff_and_stores_random_name_inside_media(self):
        with TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory, MEDIA_URL='/media/'):
            self.assertEqual(self.upload().status_code, 403)
            self.client.force_login(self.staff)
            response = self.upload()
            self.assertEqual(response.status_code, 200)
            files = list(Path(directory).rglob('*.png'))
            self.assertEqual(len(files), 1)
            self.assertRegex(files[0].name, r'^[0-9a-f]{32}\.png$')
            self.assertNotIn('submitted-name', response.json()['url'])
            self.assertTrue(files[0].resolve().is_relative_to(Path(directory).resolve()))

    def test_rejects_oversized_and_excessive_dimensions(self):
        self.client.force_login(self.staff)
        with patch('core_utils.ckeditor_upload.MAX_BYTES', 1):
            self.assertEqual(self.upload().status_code, 400)
        with patch('core_utils.ckeditor_upload.MAX_PIXELS', 1):
            self.assertEqual(self.upload().status_code, 400)
