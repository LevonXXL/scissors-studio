from rest_framework import serializers, viewsets

from core_utils.drf_fields import FilerImageUrlField

from salons.models import Salon

from .models import Master, MasterSalon


class SalonBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Salon
        fields = ('id', 'name')


class MasterSalonSerializer(serializers.ModelSerializer):
    """Привязка мастера к салону с per-salon yclients_staff_id для букинга."""
    id = serializers.IntegerField(source='salon.id', read_only=True)
    name = serializers.CharField(source='salon.name', read_only=True)
    yclients_staff_id = serializers.CharField(read_only=True)

    class Meta:
        model = MasterSalon
        fields = ('id', 'name', 'yclients_staff_id', 'yclients_booking_url')


class MasterSerializer(serializers.ModelSerializer):
    salon_details = MasterSalonSerializer(source='master_salons', many=True, read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    price_level_display = serializers.CharField(source='get_price_level_display', read_only=True)
    photo = FilerImageUrlField(read_only=True)

    class Meta:
        model = Master
        fields = (
            'id', 'slug', 'name', 'price_level_display',
            'photo', 'bio', 'salon_details', 'status_display'
        )


class MasterViewSet(viewsets.ReadOnlyModelViewSet):
    """Публичный список мастеров-партнёров, с фильтром по салону: ?salon=<id>"""
    queryset = Master.objects.filter(
        is_active=True,
        yclients_user_id__isnull=False,
        is_booking_placeholder=False,
    ).prefetch_related('master_salons__salon')
    serializer_class = MasterSerializer
    lookup_field = 'slug'

    def get_queryset(self):
        qs = super().get_queryset()
        salon_id = self.request.query_params.get('salon')
        if salon_id:
            qs = qs.filter(salons__id=salon_id)
        return qs
