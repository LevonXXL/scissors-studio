"""Bounded downloads from known public image hosts used by integrations."""

from io import BytesIO
import re
from urllib.parse import urlsplit

import requests
from PIL import Image, UnidentifiedImageError


MAX_IMAGE_BYTES = 15 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
EXTENSIONS = {'JPEG': '.jpg', 'PNG': '.png', 'WEBP': '.webp', 'GIF': '.gif'}
EXACT_HOSTS = {'assets.yclients.com', 'be.cdn.yclients.com', 'avatars.mds.yandex.net'}


def allowed_image_url(url: str) -> bool:
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or '').lower()
        if parsed.scheme != 'https' or not host or parsed.username or parsed.password:
            return False
        if parsed.port not in (None, 443) or '\\' in url or any(ord(char) < 32 for char in url):
            return False
        return (host in EXACT_HOSTS
                or bool(re.fullmatch(r'p\d+\.zoon\.ru', host))
                or bool(re.fullmatch(r'cachizer\d+\.2gis\.com', host))
                or host == 'googleusercontent.com'
                or host.endswith('.googleusercontent.com'))
    except ValueError:
        return False


def download_image(url: str) -> tuple[bytes, str]:
    """Return verified image bytes and extension; reject redirects and oversized files."""
    if not allowed_image_url(url):
        raise ValueError('Недопустимый адрес изображения.')
    with requests.get(url, timeout=20, stream=True, allow_redirects=False) as response:
        response.raise_for_status()
        if response.is_redirect:
            raise ValueError('Перенаправление при загрузке изображения запрещено.')
        length = response.headers.get('Content-Length')
        if length and int(length) > MAX_IMAGE_BYTES:
            raise ValueError('Изображение превышает лимит размера.')
        chunks = []
        size = 0
        for chunk in response.iter_content(chunk_size=64 * 1024):
            size += len(chunk)
            if size > MAX_IMAGE_BYTES:
                raise ValueError('Изображение превышает лимит размера.')
            chunks.append(chunk)
    data = b''.join(chunks)
    try:
        with Image.open(BytesIO(data)) as image:
            if image.width * image.height > MAX_IMAGE_PIXELS:
                raise ValueError('Изображение слишком большого разрешения.')
            extension = EXTENSIONS.get(image.format)
            if not extension:
                raise ValueError('Неподдерживаемый формат изображения.')
            image.verify()
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError('Файл не является изображением.') from exc
    return data, extension
