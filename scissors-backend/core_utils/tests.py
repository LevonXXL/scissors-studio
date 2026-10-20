from io import BytesIO
from pathlib import Path
from stat import S_IMODE
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.http import Http404
from django.test import SimpleTestCase, override_settings
from PIL import Image

from .thumbnails import MAX_SOURCE_BYTES, _paths


class ThumbnailTests(SimpleTestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        override = override_settings(MEDIA_ROOT=directory.name)
        override.enable()
        self.addCleanup(override.disable)

        self.source = Path(directory.name) / 'filer_public' / 'sample.jpg'
        self.source.parent.mkdir(parents=True)
        Image.new('RGB', (600, 300), 'red').save(self.source)
        self.url = '/thumbnail/300/filer_public/sample.jpg'

    def test_generates_proportional_preview_and_reuses_file(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/jpeg')
        data = b''.join(response.streaming_content)
        response.close()
        with Image.open(BytesIO(data)) as preview:
            self.assertEqual(preview.size, (300, 150))

        destination = self.source.parents[1] / 'thumbnail' / '300' / 'filer_public' / 'sample.jpg'
        self.assertTrue(destination.is_file())
        self.assertEqual(S_IMODE(destination.stat().st_mode), 0o644)
        self.assertEqual(S_IMODE(destination.parent.stat().st_mode), 0o755)
        with patch('core_utils.thumbnails._create_thumbnail', side_effect=AssertionError('Regenerated')):
            response = self.client.get(self.url)
            self.assertEqual(response.status_code, 200)
            response.close()

    def test_rejects_missing_and_unsafe_sources(self):
        self.assertEqual(self.client.get('/thumbnail/300/filer_public/missing.jpg').status_code, 404)
        self.assertEqual(self.client.get('/thumbnail/300/other/sample.jpg').status_code, 404)
        self.assertEqual(self.client.get('/thumbnail/300/filer_public/sample.svg').status_code, 404)
        self.assertEqual(self.client.get('/thumbnail/3000/filer_public/sample.jpg').status_code, 400)
        with self.assertRaises(Http404):
            _paths(300, 'filer_public/../sample.jpg')

    def test_rejects_invalid_and_oversized_images(self):
        self.source.write_bytes(b'not an image')
        self.assertEqual(self.client.get(self.url).status_code, 415)

        with self.source.open('wb') as source:
            source.truncate(MAX_SOURCE_BYTES + 1)
        self.assertEqual(self.client.get(self.url).status_code, 413)

