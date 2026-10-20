from rest_framework import serializers, viewsets

from core_utils.drf_fields import FilerImageUrlField

from .models import Service, ServiceCategory, ServiceStaffPrice


class ServiceStaffPriceSerializer(serializers.ModelSerializer):
    master_slug = serializers.CharField(source='master.slug', read_only=True)
    master_name = serializers.CharField(source='master.name', read_only=True)

    class Meta:
        model = ServiceStaffPrice
        fields = ('master_slug', 'master_name', 'price_min', 'price_max', 'duration_seconds')


class ServiceSerializer(serializers.ModelSerializer):
    image = FilerImageUrlField(read_only=True)
    duration_display = serializers.ReadOnlyField()
    staff_prices = ServiceStaffPriceSerializer(many=True, read_only=True)

    class Meta:
        model = Service
        fields = (
            'id', 'title', 'description', 'price_min', 'price_max',
            'duration_seconds', 'duration_display', 'image', 'staff_prices', 'weight',
        )


class ServiceCategorySerializer(serializers.ModelSerializer):
    services = ServiceSerializer(many=True, read_only=True)
    salon_name = serializers.CharField(source='salon.name', read_only=True)

    class Meta:
        model = ServiceCategory
        fields = ('id', 'title', 'salon', 'salon_name', 'weight', 'is_chain', 'services')


class ServiceCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Категории услуг с вложенными услугами и ценами (в т.ч. переопределениями
    по мастерам). Фильтр по салону: ?salon=<id> — так фронтенд получает
    именно тот набор категорий/услуг, которые реально есть в выбранном
    салоне (см. ServicePage.vue: если категории нет для салона — сюда
    просто не попадёт запись с этим salon).
    """
    queryset = ServiceCategory.objects.filter(is_active=True).select_related('salon').prefetch_related(
        'services', 'services__staff_prices', 'services__staff_prices__master',
    )
    serializer_class = ServiceCategorySerializer

    def get_queryset(self):
        qs = super().get_queryset()
        salon_id = self.request.query_params.get('salon')
        if salon_id:
            qs = qs.filter(salon_id=salon_id)
        return qs
