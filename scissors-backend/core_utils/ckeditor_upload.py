"""Validate staff editor images before django-ckeditor-5 stores them in media."""

import secrets
import warnings

from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django_ckeditor_5.views import upload_file
from PIL import Image, UnidentifiedImageError


MAX_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 40_000_000
EXTENSIONS = {'JPEG': '.jpg', 'PNG': '.png', 'WEBP': '.webp', 'GIF': '.gif'}


@require_POST
def staff_image_upload(request):
    if not request.user.is_staff:
        return JsonResponse({'error': {'message': 'Нет доступа.'}}, status=403)
    upload = request.FILES.get('upload')
    if upload is None or upload.size > MAX_BYTES:
        return JsonResponse({'error': {'message': 'Выберите изображение до 10 МБ.'}}, status=400)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(upload) as image:
                if image.width * image.height > MAX_PIXELS:
                    raise ValueError('Слишком большое разрешение изображения.')
                extension = EXTENSIONS.get(image.format)
                if not extension:
                    raise ValueError('Неподдерживаемый формат изображения.')
                image.verify()
    except (UnidentifiedImageError, OSError, ValueError,
            Image.DecompressionBombWarning, Image.DecompressionBombError):
        return JsonResponse({'error': {'message': 'Некорректное изображение.'}}, status=400)
    finally:
        upload.seek(0)
    upload.name = f'{secrets.token_hex(16)}{extension}'
    return upload_file(request)
