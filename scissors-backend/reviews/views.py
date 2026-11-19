from rest_framework import viewsets
from rest_framework.permissions import AllowAny

from core_utils.public_cache import cached_public_response
from .models import Review
from .serializers import ReviewSerializer, HomeReviewSerializer


def _review_cache_key(request, allowed_params):
    """Keep cache cardinality bounded to supported first-page public filters."""
    if request.query_params.get('page', '1') != '1':
        return None
    # Salon pages have few requests and many possible IDs; leave them uncached.
    if request.query_params.get('salon'):
        return None

    params = []
    for name in allowed_params:
        values = request.query_params.getlist(name)
        if len(values) > 1:
            return None
        value = values[0] if values else ''
        if value and not value.isdigit():
            return None
        if name == 'limit' and value and not 1 <= int(value) <= 50:
            return None
        if name == 'source' and value and int(value) not in {1, 2, 3, 4, 5, 99}:
            return None
        if name == 'rating' and value and int(value) not in {1, 2, 3, 4, 5}:
            return None
        if name == 'with_images' and value and value != '1':
            return None
        if value:
            params.append(f'{name}={value}')
    return f'{request.scheme}://{request.get_host()}{request.path}?{"&".join(params)}'


class ReviewViewSet(viewsets.ReadOnlyModelViewSet):
    """Все отзывы, с фильтром по салону, площадке (source) и рейтингу."""
    queryset = Review.objects.filter(is_published=True).select_related('salon')
    serializer_class = ReviewSerializer

    def list(self, request, *args, **kwargs):
        key = _review_cache_key(request, ('salon', 'source', 'rating', 'with_images'))
        if key is None:
            return super().list(request, *args, **kwargs)
        return cached_public_response(
            'reviews', key, request,
            lambda: super(ReviewViewSet, self).list(request, *args, **kwargs),
            timeout=15 * 60,
        )

    def get_queryset(self):
        qs = super().get_queryset()
        salon_id = self.request.query_params.get('salon')
        if salon_id:
            qs = qs.filter(salon_id=salon_id)
        source = self.request.query_params.get('source')
        if source:
            qs = qs.filter(source=source)
        rating = self.request.query_params.get('rating')
        if rating:
            qs = qs.filter(rating=rating)
        if self.request.query_params.get('with_images') == '1':
            qs = qs.filter(has_images=True).exclude(images=[])
        return qs


class HomeReviewViewSet(viewsets.ReadOnlyModelViewSet):
    """Отзывы для главной страницы — упрощённый формат.

    Возвращает только отзывы с текстом, фото и рейтингом >= 4, сначала свежие.
    Фронтенд HomePage показывает их в карусели.
    """
    permission_classes = [AllowAny]
    serializer_class = HomeReviewSerializer
    pagination_class = None  # Все за раз — для карусели на главной

    def list(self, request, *args, **kwargs):
        key = _review_cache_key(request, ('limit',))
        if key is None:
            return super().list(request, *args, **kwargs)
        return cached_public_response(
            'reviews', key, request,
            lambda: super(HomeReviewViewSet, self).list(request, *args, **kwargs),
            timeout=15 * 60,
        )

    def get_queryset(self):
        qs = (
            Review.objects
            .filter(is_published=True, rating__gte=4, text__gt='', has_images=True)
            .exclude(images=[])
            .select_related('salon')
            .order_by('-review_date')
        )
        limit = self.request.query_params.get('limit')
        if limit:
            try:
                qs = qs[:int(limit)]
            except (ValueError, TypeError):
                pass
        return qs
