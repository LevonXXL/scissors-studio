from django.shortcuts import get_object_or_404
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core_utils.drf_fields import FilerImageUrlField
from pages.serializers import PageDetailSerializer

from .models import Salon, SalonPhoto


class SalonPhotoSerializer(serializers.ModelSerializer):
    image = FilerImageUrlField(read_only=True)

    class Meta:
        model = SalonPhoto
        fields = ('id', 'image', 'position')


class SalonSerializer(serializers.ModelSerializer):
    coordinates = serializers.ReadOnlyField()
    logo = FilerImageUrlField(read_only=True)
    photos = SalonPhotoSerializer(many=True, read_only=True)
    page = serializers.SerializerMethodField()

    def get_page(self, obj):
        page = obj.page
        if page is None or not page.is_published or page.url_path != f'salons/{obj.slug}':
            return None
        return PageDetailSerializer(page, context=self.context).data

    class Meta:
        model = Salon
        fields = (
            'id', 'slug', 'page', 'name', 'address', 'latitude', 'longitude', 'coordinates',
            'phone', 'working_hours', 'description', 'logo', 'photos', 'position',
        )


class SalonViewSet(viewsets.ReadOnlyModelViewSet):
    """Публичный список салонов — для страницы «Салоны» и меток на Яндекс.Картах."""
    queryset = Salon.objects.filter(is_active=True).select_related('page').prefetch_related('photos', 'page__pictures')
    serializer_class = SalonSerializer

    @action(detail=False, methods=['get'], url_path=r'by-slug/(?P<slug>[^/.]+)')
    def by_slug(self, request, slug=None):
        salon = get_object_or_404(self.get_queryset(), slug=slug)
        return Response(self.get_serializer(salon).data)
