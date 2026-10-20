
import hashlib
import logging
from pathlib import Path
from urllib.parse import urlparse

import requests
from django.core.files.base import ContentFile
from filer.models import Folder, Image as FilerImage

from .models import ReviewImage

logger = logging.getLogger(__name__)

MAX_IMAGE_SIZE = 15 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {
    'image/jpeg': '.jpg',
    'image/png': '.png',
    'image/webp': '.webp',
    'image/gif': '.gif',
}


def get_review_folder():
    folder, _ = Folder.objects.get_or_create(
        name='rewio-reviews',
        parent=None,
    )
    return folder


def fetch_review_image(review, url, position):
    """Скачать фотографию отзыва в filer или вернуть уже сохранённую."""
    if not url:
        return None

    parsed = urlparse(url)
    if parsed.scheme != 'https' or not parsed.hostname:
        logger.warning('Пропущен недопустимый URL фото отзыва: %s', url)
        return None

    cached = (
        ReviewImage.objects
        .filter(review=review, source_url=url)
        .select_related('image')
        .first()
    )
    if cached:
        return cached

    try:
        with requests.get(
            url,
            timeout=20,
            stream=True,
            headers={'User-Agent': 'ScissorsStudio/1.0'},
        ) as response:
            response.raise_for_status()

            content_type = (
                response.headers.get('Content-Type', '')
                .split(';')[0].strip().lower()
            )
            extension = ALLOWED_CONTENT_TYPES.get(content_type)
            if not extension:
                logger.warning(
                    'Неподдерживаемый тип фото отзыва %s: %s',
                    url, content_type,
                )
                return None

            length = response.headers.get('Content-Length')
            if length and int(length) > MAX_IMAGE_SIZE:
                logger.warning('Фото отзыва слишком большое: %s', url)
                return None

            chunks = []
            size = 0
            for chunk in response.iter_content(chunk_size=64 * 1024):
                size += len(chunk)
                if size > MAX_IMAGE_SIZE:
                    logger.warning('Фото отзыва превышает лимит: %s', url)
                    return None
                chunks.append(chunk)

    except (requests.RequestException, ValueError) as exc:
        logger.warning('Не удалось скачать фото отзыва %s: %s', url, exc)
        return None

    filename = hashlib.sha256(url.encode('utf-8')).hexdigest() + extension

    try:
        filer_image = FilerImage.objects.create(
            file=ContentFile(b''.join(chunks), name=filename),
            original_filename=filename,
            folder=get_review_folder(),
        )
        try:
            return ReviewImage.objects.create(
                review=review,
                image=filer_image,
                source_url=url,
                position=position,
            )
        except Exception:
            filer_image.delete()
            raise
    except Exception:
        logger.exception('Не удалось сохранить фото отзыва %s', url)
        return None
