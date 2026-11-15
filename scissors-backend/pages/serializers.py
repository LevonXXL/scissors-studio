from django.db.models import Q
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core_utils.drf_fields import FilerImageUrlField
from masters.models import Master
from masters.constants import TEST_MASTER_SLUG_PREFIX

from .models import Page, PagePicture


class PagePictureSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    def get_image(self, picture):
        url = picture.image_url
        request = self.context.get('request')
        return request.build_absolute_uri(url) if url and request else url

    class Meta:
        model = PagePicture
        fields = ('id', 'image', 'alt', 'position')


class PageListSerializer(serializers.ModelSerializer):
    """Компактная версия — для меню и списков (карточка страницы с кратким описанием)."""

    title_tag = serializers.ReadOnlyField()
    link_title = serializers.CharField(source='effective_link_title', read_only=True)

    class Meta:
        model = Page
        fields = ('id', 'title', 'link_title', 'title_tag', 'meta_description', 'url', 'url_path', 'parent', 'position')


class MasterPageSerializer(serializers.ModelSerializer):
    photo = FilerImageUrlField(read_only=True)
    service_work_photos = serializers.SerializerMethodField()

    def get_service_work_photos(self, master):
        request = self.context.get('request')
        return [
            {
                'id': photo.pk,
                'service_id': photo.service_id,
                'service_title': photo.service.title,
                'service_url_path': photo.service.page.url_path if photo.service.page_id else '',
                'image': request.build_absolute_uri(photo.image.url) if request else photo.image.url,
                'caption': photo.caption,
            }
            for photo in master.service_work_photos.all()
            if photo.image_id and photo.service.is_active and photo.service.category.is_active
        ]

    class Meta:
        model = Master
        fields = ('name', 'photo', 'bio', 'service_work_photos')


class PageDetailSerializer(serializers.ModelSerializer):
    """Полная версия — для рендера самой страницы."""

    title_tag = serializers.ReadOnlyField()
    link_title = serializers.CharField(source='effective_link_title', read_only=True)
    breadcrumbs = serializers.SerializerMethodField()
    pictures = PagePictureSerializer(many=True, read_only=True)
    master = serializers.SerializerMethodField()
    booking_target = serializers.SerializerMethodField()
    yclients_booking_links = serializers.SerializerMethodField()

    def get_breadcrumbs(self, page):
        return [
            {'link_title': node.effective_link_title, 'url_path': node.url_path}
            for node in page.get_ancestors(include_self=True)
            if node.url_path  # The frontend supplies the common home crumb.
        ]

    def get_master(self, page):
        master = getattr(page, 'master', None)
        return MasterPageSerializer(master, context=self.context).data if master else None

    def get_booking_target(self, page):
        service = getattr(page, 'service', None)
        if service and service.is_active and service.category.is_active:
            offer = service.salon_offers.filter(is_active=True, salon__is_active=True).select_related('salon').first()
            if offer:
                return {'salon': offer.salon.slug, 'service': service.pk}
        master = getattr(page, 'master', None)
        if (master and master.is_active and not master.is_system and
                not master.is_booking_placeholder and
                master.master_salons.filter(salon__is_active=True).exists()):
            return {'master': master.pk}
        return None

    def get_yclients_booking_links(self, page):
        master = getattr(page, 'master', None)
        if not master or not master.is_active or master.is_system or master.is_booking_placeholder:
            return []
        return [
            {
                'salon_id': link.salon_id,
                'salon_name': link.salon.name,
                'url': link.yclients_booking_url or link.salon.yclients_booking_url or
                       'https://n428078.yclients.ru',
            }
            for link in master.master_salons.filter(salon__is_active=True).select_related('salon').order_by('salon__position', 'salon_id')
        ]

    class Meta:
        model = Page
        fields = (
            'id', 'title', 'link_title', 'breadcrumbs', 'title_tag', 'content', 'meta_title', 'meta_description',
            'url', 'url_path', 'parent', 'pictures', 'master', 'booking_target', 'yclients_booking_links',
        )


class PageViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Публичное API страниц.

    - список (`GET /pages/`) — компактный, для построения меню/хлебных крошек;
    - детальная страница ищется не по числовому id, а по полному `url_path`
      (см. action `by-path`), потому что именно так на неё ссылается фронтенд
      при клиентской маршрутизации по произвольной вложенности разделов.
    """

    queryset = Page.objects.filter(is_published=True).exclude(
        Q(master__is_booking_placeholder=True) |
        Q(master__slug__startswith=TEST_MASTER_SLUG_PREFIX) |
        Q(url__startswith=TEST_MASTER_SLUG_PREFIX) |
        Q(service_category__is_active=False) |
        Q(service__is_active=False) |
        Q(service__category__is_active=False)
    )

    def get_serializer_class(self):
        if self.action == 'list':
            return PageListSerializer
        return PageDetailSerializer

    @action(detail=False, methods=['get'], url_path=r'by-path(?:/(?P<url_path>.+))?')
    def by_path(self, request, url_path=None):
        page = self.get_queryset().select_related('master__photo').prefetch_related(
            'pictures__image', 'master__service_work_photos__image',
            'master__service_work_photos__service__page',
            'master__service_work_photos__service__category',
        ).filter(
            url_path=(url_path or '').strip('/'),
        ).first()
        if page is None:
            return Response({'detail': 'Страница не найдена.'}, status=404)
        serializer = self.get_serializer(page)
        return Response(serializer.data)
