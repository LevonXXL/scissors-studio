from io import BytesIO
from unittest.mock import patch

from django.test import SimpleTestCase
from PIL import Image

from .remote_images import MAX_IMAGE_BYTES, allowed_image_url, download_image


class FakeResponse:
    def __init__(self, chunks, *, redirect=False, headers=None):
        self.chunks = chunks
        self.is_redirect = redirect
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size):
        yield from self.chunks


class RemoteImageTests(SimpleTestCase):
    def test_rejects_private_hosts_credentials_and_bad_ports_before_network(self):
        for url in (
            'http://assets.yclients.com/photo.jpg',
            'https://127.0.0.1/photo.jpg',
            'https://assets.yclients.com.evil.test/photo.jpg',
            'https://user:pass@assets.yclients.com/photo.jpg',
            'https://assets.yclients.com:8443/photo.jpg',
            'https://assets.yclients.com\\@evil.test/photo.jpg',
        ):
            with self.subTest(url=url), patch('core_utils.remote_images.requests.get') as get:
                self.assertFalse(allowed_image_url(url))
                with self.assertRaises(ValueError):
                    download_image(url)
                get.assert_not_called()

    def test_accepts_verified_image_and_rejects_redirects_and_size_bombs(self):
        buffer = BytesIO()
        Image.new('RGB', (2, 2), 'red').save(buffer, format='PNG')
        url = 'https://assets.yclients.com/photo.png'
        with patch('core_utils.remote_images.requests.get', return_value=FakeResponse([buffer.getvalue()])) as get:
            data, extension = download_image(url)
            self.assertEqual((data, extension), (buffer.getvalue(), '.png'))
            self.assertEqual(get.call_args.kwargs['allow_redirects'], False)
            self.assertEqual(get.call_args.kwargs['stream'], True)
        with patch('core_utils.remote_images.requests.get', return_value=FakeResponse([], redirect=True)):
            with self.assertRaisesRegex(ValueError, 'Перенаправление'):
                download_image(url)
        with patch('core_utils.remote_images.requests.get', return_value=FakeResponse(
            [], headers={'Content-Length': str(MAX_IMAGE_BYTES + 1)},
        )):
            with self.assertRaisesRegex(ValueError, 'лимит'):
                download_image(url)
        with patch('core_utils.remote_images.requests.get', return_value=FakeResponse(
            [b'a' * MAX_IMAGE_BYTES, b'a'],
        )):
            with self.assertRaisesRegex(ValueError, 'лимит'):
                download_image(url)

    def test_rejects_non_image_body(self):
        with patch('core_utils.remote_images.requests.get', return_value=FakeResponse([b'<html>'])):
            with self.assertRaisesRegex(ValueError, 'не является изображением'):
                download_image('https://avatars.mds.yandex.net/photo')
