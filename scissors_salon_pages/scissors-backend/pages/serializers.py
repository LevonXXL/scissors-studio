from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Page, PagePicture


class PagePictureSerializer(serializers.ModelSerializer):
    class Meta:
        model = PagePicture
        fields = ('id', 'image', 'alt', 'position')


class PageListSerializer(serializers.ModelSerializer):
    """Компактная версия — для меню и списков (карточка страницы с кратким описанием)."""

    title_tag = serializers.ReadOnlyField()

    class Meta:
        model = Page
        fields = ('id', 'title', 'title_tag', 'meta_description', 'url', 'url_path', 'parent', 'position')


class PageDetailSerializer(serializers.ModelSerializer):
    """Полная версия — для рендера самой страницы."""

    title_tag = serializers.ReadOnlyField()
    pictures = PagePictureSerializer(many=True, read_only=True)

    class Meta:
        model = Page
        fields = (
            'id', 'title', 'title_tag', 'content', 'meta_title', 'meta_description',
            'url', 'url_path', 'parent', 'pictures',
        )


class PageViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Публичное API страниц.

    - список (`GET /pages/`) — компактный, для построения меню/хлебных крошек;
    - детальная страница ищется не по числовому id, а по полному `url_path`
      (см. action `by-path`), потому что именно так на неё ссылается фронтенд
      при клиентской маршрутизации по произвольной вложенности разделов.
    """

    queryset = Page.objects.filter(is_published=True)

    def get_serializer_class(self):
        if self.action == 'list':
            return PageListSerializer
        return PageDetailSerializer

    @action(detail=False, methods=['get'], url_path='by-path/(?P<url_path>.+)')
    def by_path(self, request, url_path=None):
        page = self.get_queryset().filter(url_path=url_path.strip('/')).first()
        if page is None:
            return Response({'detail': 'Страница не найдена.'}, status=404)
        serializer = self.get_serializer(page)
        return Response(serializer.data)
