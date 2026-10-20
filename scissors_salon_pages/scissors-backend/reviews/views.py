from rest_framework import viewsets
from rest_framework.permissions import AllowAny

from .models import Review
from .serializers import ReviewSerializer, HomeReviewSerializer


class ReviewViewSet(viewsets.ReadOnlyModelViewSet):
    """Одобренные отзывы (is_approved=True) с фильтром по салону, площадке, рейтингу
    и наличию фото (?has_images=true). Неодобренные в публичный API не попадают никогда."""
    queryset = Review.objects.filter(is_approved=True).select_related('salon')
    serializer_class = ReviewSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get('has_images') in ('1', 'true', 'True'):
            qs = qs.filter(has_images=True)
        salon_id = self.request.query_params.get('salon')
        if salon_id:
            qs = qs.filter(salon_id=salon_id)
        source = self.request.query_params.get('source')
        if source:
            qs = qs.filter(source=source)
        rating = self.request.query_params.get('rating')
        if rating:
            qs = qs.filter(rating=rating)
        return qs


class HomeReviewViewSet(viewsets.ReadOnlyModelViewSet):
    """Отзывы для главной страницы — упрощённый формат.

    Возвращает только одобренные (is_approved) отзывы с фото, текстом и рейтингом >= 4, сначала свежие.
    Фронтенд HomePage показывает их в карусели.
    """
    permission_classes = [AllowAny]
    serializer_class = HomeReviewSerializer
    pagination_class = None  # Все за раз — для карусели на главной

    def get_queryset(self):
        qs = (
            Review.objects
            .filter(is_approved=True, has_images=True, rating__gte=4, text__gt='')
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
