from io import BytesIO
from pathlib import Path
from stat import S_IMODE
from tempfile import TemporaryDirectory

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from filer.models import Image as FilerImage
from PIL import Image


class MediaStorageTests(TestCase):
    def test_uploaded_image_stays_inside_media_with_public_read_permissions(self):
        with TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            buffer = BytesIO()
            Image.new('RGB', (2, 2), 'red').save(buffer, format='PNG')
            upload = SimpleUploadedFile('../../escape.png', buffer.getvalue(), content_type='image/png')
            image = FilerImage.objects.create(file=upload, original_filename=upload.name)
            path = Path(image.file.path).resolve()
            self.assertTrue(path.is_relative_to(Path(directory).resolve()))
            self.assertEqual(S_IMODE(path.stat().st_mode), 0o644)
            self.assertFalse((Path(directory).parent / 'escape.png').exists())
