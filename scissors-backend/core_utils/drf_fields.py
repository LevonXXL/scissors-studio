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
