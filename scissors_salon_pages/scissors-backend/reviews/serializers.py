from rest_framework import serializers

from .models import Review


class ReviewSerializer(serializers.ModelSerializer):
    """Публичный сериализатор отзыва для главной страницы.

    Фронтенд ожидает Union-тип: видео-отзыв или текстовый с фото работы.
    Rewio отдаёт только текстовые отзывы с фото — видео нужно добавлять вручную
    через админку (или отдельный источник в будущем).
    """
    source_display = serializers.CharField(source='get_source_display', read_only=True)
    salon_name = serializers.CharField(source='salon.name', read_only=True)

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
        """Первое фото из массива, prefer 'image' (full), fallback 'preview'."""
        images = obj.images or []
        if images:
            return images[0].get('image') or images[0].get('preview', '')
        return ''
