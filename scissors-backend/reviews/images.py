
import logging
import secrets

import requests
from django.core.files.base import ContentFile
from filer.models import Folder, Image as FilerImage

from core_utils.remote_images import download_image
from .models import ReviewImage

logger = logging.getLogger(__name__)

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

    cached = (
        ReviewImage.objects
        .filter(review=review, source_url=url)
        .select_related('image')
        .first()
    )
    if cached:
        return cached

    try:
        data, extension = download_image(url)
    except (requests.RequestException, ValueError) as exc:
        logger.warning('Не удалось скачать фото отзыва: %s', type(exc).__name__)
        return None

    filename = secrets.token_hex(16) + extension

    try:
        filer_image = FilerImage.objects.create(
            file=ContentFile(data, name=filename),
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
        logger.exception('Не удалось сохранить фото отзыва (id=%s)', review.pk)
        return None
