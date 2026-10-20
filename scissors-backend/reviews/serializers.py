from rest_framework import serializers

from .models import Review


def _public_image_url(url, request):
    return request.build_absolute_uri(url) if request and url.startswith('/') else url


class ReviewSerializer(serializers.ModelSerializer):
    """Публичный сериализатор отзыва для главной страницы.

    Фронтенд ожидает Union-тип: видео-отзыв или текстовый с фото работы.
    Rewio отдаёт только текстовые отзывы с фото — видео нужно добавлять вручную
    через админку (или отдельный источник в будущем).
    """
    source_display = serializers.CharField(source='get_source_display', read_only=True)
    salon_name = serializers.CharField(source='salon.name', read_only=True)
    images = serializers.SerializerMethodField()

    def get_images(self, obj):
        request = self.context.get('request')

        local_images = list(obj.local_images.select_related('image').all())

        if local_images:
            return [
                {
                    'preview': _public_image_url(item.image.url, request),
                    'image': _public_image_url(item.image.url, request),
                }
                for item in local_images
                if item.image
            ]

        return [
            {
                key: _public_image_url(image.get(key, ''), request)
                for key in ('preview', 'image')
            }
            for image in (obj.images or [])
            if isinstance(image, dict)
               and (image.get('image') or image.get('preview'))
        ]

    class Meta:
        model = Review
        fields = (
            'id', 'salon', 'salon_name',
            'source', 'source_display',
            'author', 'text', 'rating',
            'review_date', 'review_url',
            'reply_text', 'reply_date',
            'has_images', 'images',
            'has_videos', 'videos',
        )
        read_only_fields = fields


class HomeReviewSerializer(serializers.ModelSerializer):
    """Упрощённый формат для главной страницы — совместим с текущим фронтендом.

    Фронтенд показывает: карточки с фото + текст отзыва + рейтинг.
    Первое фото из массива images используется как обложка.
    """
    type = serializers.SerializerMethodField()
    author = serializers.CharField(read_only=True)
    text = serializers.CharField(read_only=True)
    rating = serializers.IntegerField(read_only=True)
    workImage = serializers.SerializerMethodField()
    review_url = serializers.URLField(read_only=True)

    class Meta:
        model = Review
        fields = ('id', 'type', 'author', 'text', 'rating', 'workImage', 'review_url')

    def get_type(self, obj) -> str:
        return 'text'

    def get_workImage(self, obj) -> str:
        request = self.context.get('request')

        local_image = (
            obj.local_images
            .select_related('image')
            .first()
        )

        if local_image and local_image.image:
            return _public_image_url(local_image.image.url, request)

        for image in obj.images or []:
            if isinstance(image, dict):
                url = image.get('image') or image.get('preview') or ''
                if url:
                    return _public_image_url(url, request)

        return ''
