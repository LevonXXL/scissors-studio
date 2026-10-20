from rest_framework import serializers, viewsets

from core_utils.drf_fields import FilerImageUrlField, filer_thumbnail_url

from .models import Salon, SalonPhoto


class SalonPhotoSerializer(serializers.ModelSerializer):
    """image — крупная версия (до 1600px по ширине, для просмотра/og:image),
    thumbnail — превью для сетки галереи (600x400, кадрирование). width/height
    описывают именно thumbnail — фронтенд ставит их в <img width height>, чтобы
    страница не "прыгала" при загрузке (CLS — метрика Core Web Vitals)."""

    image = serializers.SerializerMethodField()
    thumbnail = serializers.SerializerMethodField()
    thumbnail_width = serializers.SerializerMethodField()
    thumbnail_height = serializers.SerializerMethodField()

    THUMB_W, THUMB_H = 600, 400

    class Meta:
        model = SalonPhoto
        fields = ('id', 'image', 'thumbnail', 'thumbnail_width', 'thumbnail_height', 'position')

    def get_image(self, obj):
        # Без кадрирования: сохраняем пропорции оригинала, ограничиваем ширину.
        return filer_thumbnail_url(obj.image, 1600, 1600, crop=False, request=self.context.get('request'))

    def get_thumbnail(self, obj):
        return filer_thumbnail_url(obj.image, self.THUMB_W, self.THUMB_H, request=self.context.get('request'))

    def get_thumbnail_width(self, obj):
        return self.THUMB_W

    def get_thumbnail_height(self, obj):
        return self.THUMB_H


class SalonSerializer(serializers.ModelSerializer):
    coordinates = serializers.ReadOnlyField()
    logo = FilerImageUrlField(read_only=True)
    photos = SalonPhotoSerializer(many=True, read_only=True)

    class Meta:
        model = Salon
        fields = (
            'id', 'slug', 'name', 'address', 'latitude', 'longitude', 'coordinates',
            'phone', 'working_hours', 'description', 'logo', 'photos', 'position',
            'yclients_company_id',
        )


class SalonViewSet(viewsets.ReadOnlyModelViewSet):
    """Публичный список салонов — для страницы «Салоны» и меток на Яндекс.Картах."""
    queryset = Salon.objects.filter(is_active=True).prefetch_related('photos')
    serializer_class = SalonSerializer
    lookup_field = 'slug'
