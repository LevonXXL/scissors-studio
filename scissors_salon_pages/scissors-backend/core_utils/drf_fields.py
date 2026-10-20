from rest_framework import serializers


class FilerImageUrlField(serializers.RelatedField):
    """
    FilerImageField — это ForeignKey на filer.Image, а не обычный Django
    ImageField. Стандартный ModelSerializer сериализовал бы его как ID
    связанной записи filer.Image, а не как URL файла, который ожидает
    фронтенд в <img src>. Это поле отдаёт наружу именно URL (или null,
    если картинка не задана).
    """

    def to_representation(self, value):
        request = self.context.get('request')
        url = value.url
        if request is not None:
            return request.build_absolute_uri(url)
        return url


def filer_thumbnail_url(filer_image, width: int, height: int, *, crop: bool = True, request=None):
    """
    URL превью filer-картинки нужного размера, сгенерированного "на лету"
    через easy-thumbnails (кэшируется на диске, повторные запросы бесплатны).
    Если превью сделать не удалось (файла нет на диске, битая картинка) —
    возвращает URL оригинала, чтобы API не падал из-за одной плохой фотографии.
    """
    from easy_thumbnails.files import get_thumbnailer

    try:
        thumb = get_thumbnailer(filer_image.file).get_thumbnail(
            {'size': (width, height), 'crop': crop, 'upscale': False},
        )
        url = thumb.url
    except Exception:  # noqa: BLE001 — любое повреждение файла не должно ронять API
        url = filer_image.url
    return request.build_absolute_uri(url) if request is not None else url
