"""Generate on-demand previews for images stored by django-filer."""

import os
import tempfile
import warnings
from pathlib import Path, PurePosixPath

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse
from django.views.decorators.http import require_safe
from PIL import Image, ImageOps, UnidentifiedImageError


MAX_WIDTH = 2000
MAX_SOURCE_BYTES = 20 * 1024 * 1024
MAX_SOURCE_PIXELS = 25_000_000
FORMATS = {
    '.jpg': ('JPEG', 'image/jpeg'),
    '.jpeg': ('JPEG', 'image/jpeg'),
    '.png': ('PNG', 'image/png'),
    '.webp': ('WEBP', 'image/webp'),
    '.gif': ('GIF', 'image/gif'),
}


def _paths(width, source_path):
    relative = PurePosixPath(source_path)
    if (
        not source_path.startswith('filer_public/')
        or not relative.parts
        or any(part in {'', '.', '..'} for part in source_path.split('/'))
        or '\\' in source_path
        or '\x00' in source_path
        or relative.suffix.lower() not in FORMATS
    ):
        raise Http404

    media_root = Path(settings.MEDIA_ROOT).resolve()
    originals_root = (media_root / 'filer_public').resolve()
    source = (media_root / relative).resolve()
    destination_root = media_root / 'thumbnail'
    destination = (destination_root / str(width) / relative).resolve()
    if not source.is_relative_to(originals_root) or not destination.is_relative_to(destination_root):
        raise Http404
    return source, destination


def _create_thumbnail(source, destination, width, image_format):
    with warnings.catch_warnings():
        warnings.simplefilter('error', Image.DecompressionBombWarning)
        with Image.open(source) as original:
            if original.width * original.height > MAX_SOURCE_PIXELS:
                raise ValueError('Image pixel limit exceeded')
            image = ImageOps.exif_transpose(original)
            image.thumbnail((width, image.height), Image.Resampling.LANCZOS)

            if image_format == 'JPEG':
                if image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info):
                    rgba = image.convert('RGBA')
                    background = Image.new('RGB', rgba.size, 'white')
                    background.paste(rgba, mask=rgba.getchannel('A'))
                    image = background
                else:
                    image = image.convert('RGB')
            elif image_format == 'GIF':
                image = image.convert('P')

            destination.parent.mkdir(parents=True, exist_ok=True)
            thumbnail_root = Path(settings.MEDIA_ROOT).resolve() / 'thumbnail'
            directory = destination.parent
            while directory != thumbnail_root.parent:
                os.chmod(directory, 0o755)
                directory = directory.parent
            temporary_path = None
            try:
                with tempfile.NamedTemporaryFile(
                    dir=destination.parent, prefix='.thumbnail-', suffix=destination.suffix,
                    delete=False,
                ) as temporary:
                    temporary_path = Path(temporary.name)
                    options = {'quality': 82} if image_format in {'JPEG', 'WEBP'} else {}
                    image.save(temporary, format=image_format, **options)
                os.chmod(temporary_path, 0o644)
                os.replace(temporary_path, destination)
            finally:
                if temporary_path is not None:
                    temporary_path.unlink(missing_ok=True)


@require_safe
def thumbnail(request, width, source_path):
    """Serve a preview on cache miss; Angie serves subsequent requests from disk."""
    if not 1 <= width <= MAX_WIDTH:
        return HttpResponse(status=400)

    source, destination = _paths(width, source_path)
    if not source.is_file():
        raise Http404
    try:
        if source.stat().st_size > MAX_SOURCE_BYTES:
            return HttpResponse(status=413)
        if not destination.is_file():
            image_format = FORMATS[destination.suffix.lower()][0]
            try:
                _create_thumbnail(source, destination, width, image_format)
            except (UnidentifiedImageError, Image.DecompressionBombWarning,
                    Image.DecompressionBombError, ValueError):
                return HttpResponse(status=415)
    except OSError:
        return HttpResponse(status=503)

    content_type = FORMATS[destination.suffix.lower()][1]
    try:
        response = FileResponse(destination.open('rb'), content_type=content_type)
    except OSError:
        return HttpResponse(status=503)
    response['Cache-Control'] = 'public, max-age=604800'
    response['X-Content-Type-Options'] = 'nosniff'
    return response
