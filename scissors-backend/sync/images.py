"""
Скачивание изображений из YCLIENTS в filer, с дедупликацией по URL.

YCLIENTS отдаёт частично полные URL (avatar/avatar_big/logo — с доменом
be.cdn.yclients.com или assets.yclients.com), а иногда — только
относительный путь (так приходит поле "photos" в ответе /company/{id}:
"general/f/f8/f89a41657dc6bd4_...png", без домена). normalize_image_url
приводит оба варианта к полному URL.
"""

from __future__ import annotations

import hashlib
import logging

import requests
from django.core.files.base import ContentFile

from filer.models import Image as FilerImage

from .models import SyncedImage

logger = logging.getLogger(__name__)

ASSETS_BASE_URL = 'https://assets.yclients.com/'

# Плейсхолдеры YCLIENTS для мастеров без фото — скачивать их как "реальное
# фото" мастера смысла нет, они одинаковые у всех и ничего не показывают.
PLACEHOLDER_MARKERS = ('no-master.png', 'no-master-sm.png')


def normalize_image_url(url: str) -> str:
    if url.startswith('http://') or url.startswith('https://'):
        return url
    return ASSETS_BASE_URL + url.lstrip('/')


def is_placeholder_image(url: str) -> bool:
    return any(marker in url for marker in PLACEHOLDER_MARKERS)


def fetch_and_store_image(url: str | None, *, folder_name: str = 'yclients') -> FilerImage | None:
    """
    Возвращает filer.Image для указанного URL, скачивая его при первом
    обращении и переиспользуя из кэша (SyncedImage) при повторных.
    Возвращает None для пустых URL и для плейсхолдеров YCLIENTS.
    """
    if not url:
        return None

    normalized = normalize_image_url(url)
    if is_placeholder_image(normalized):
        return None

    cached = SyncedImage.objects.filter(source_url=normalized).select_related('image').first()
    if cached:
        return cached.image

    try:
        response = requests.get(normalized, timeout=20)
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning('Не удалось скачать изображение %s: %s', normalized, exc)
        return None

    filename = hashlib.md5(normalized.encode('utf-8')).hexdigest() + _guess_extension(normalized)

    filer_image = FilerImage.objects.create(
        file=ContentFile(response.content, name=filename),
        original_filename=filename,
        folder=_get_or_create_folder(folder_name),
    )
    SyncedImage.objects.create(source_url=normalized, image=filer_image)
    return filer_image


def _guess_extension(url: str) -> str:
    for ext in ('.png', '.jpg', '.jpeg', '.webp', '.gif'):
        if url.lower().split('?')[0].endswith(ext):
            return ext
    return '.jpg'


def _get_or_create_folder(name: str):
    from filer.models import Folder
    folder, _ = Folder.objects.get_or_create(name=name, parent=None)
    return folder
