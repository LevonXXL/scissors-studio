from datetime import timedelta

from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import serializers

from client_auth.models import VerifiedPhone
from client_auth.services import normalize_phone
from masters.models import Master, MasterSalon
from salons.models import Salon
from services.models import Service, ServiceStaffPrice

from .models import Booking


class BookingRequestSerializer(serializers.Serializer):
    salon = serializers.PrimaryKeyRelatedField(queryset=Salon.objects.filter(is_active=True))
    service_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), min_length=1, max_length=10)
    preferred_master = serializers.PrimaryKeyRelatedField(
        queryset=Master.objects.filter(is_active=True, is_system=False,
                                       is_booking_placeholder=False), required=False, allow_null=True,
    )
    requested_start = serializers.DateTimeField()
    requested_end = serializers.DateTimeField(required=False, allow_null=True)
    name = serializers.CharField(max_length=255, trim_whitespace=True)
    phone = serializers.CharField(max_length=32, required=False, allow_blank=True)
    comment = serializers.CharField(max_length=1000, required=False, allow_blank=True, trim_whitespace=True)

    def validate(self, attrs):
        salon = attrs['salon']
        service_ids = attrs['service_ids']
        if len(service_ids) != len(set(service_ids)):
            raise serializers.ValidationError({'service_ids': 'Услуги не должны повторяться.'})
        services = list(Service.objects.filter(
            id__in=service_ids, is_active=True, category__is_active=True,
            salon_offers__salon=salon, salon_offers__is_active=True,
        ).distinct())
        if len(services) != len(service_ids):
            raise serializers.ValidationError({'service_ids': 'Выберите действующие услуги этого салона.'})
        master = attrs.get('preferred_master')
        if master and not MasterSalon.objects.filter(master=master, salon=salon).exists():
            raise serializers.ValidationError({'preferred_master': 'Мастер не работает в выбранном салоне.'})
        if master and ServiceStaffPrice.objects.filter(master=master, salon=salon, service_id__in=service_ids).count() != len(service_ids):
            raise serializers.ValidationError({'preferred_master': 'Мастер не оказывает все выбранные услуги.'})
        start, end = attrs['requested_start'], attrs.get('requested_end')
        now = timezone.now()
        if start < now or start > now + timedelta(days=90) or (end and (end <= start or end - start > timedelta(days=14))):
            raise serializers.ValidationError({'requested_start': 'Укажите будущий диапазон не более 14 дней.'})

        request = self.context['request']
        verified_phones = (
            list(VerifiedPhone.objects.filter(user=request.user).order_by('pk').values_list('phone', flat=True))
            if request.user.is_authenticated else []
        )
        if verified_phones:
            requested_phone = attrs.get('phone', '')
            if len(verified_phones) > 1 and requested_phone:
                try:
                    requested_phone = normalize_phone(requested_phone)
                except DjangoValidationError as exc:
                    raise serializers.ValidationError({'phone': exc.messages}) from exc
                if requested_phone not in verified_phones:
                    raise serializers.ValidationError({'phone': 'Выберите подтверждённый номер из профиля.'})
            attrs['phone'] = requested_phone if len(verified_phones) > 1 and requested_phone else verified_phones[0]
        else:
            try:
                attrs['phone'] = normalize_phone(attrs.get('phone', ''))
            except DjangoValidationError as exc:
                raise serializers.ValidationError({'phone': exc.messages}) from exc
        attrs['services'] = services
        return attrs

    def create(self, validated_data):
        services = validated_data.pop('services')
        service_ids = validated_data.pop('service_ids')
        preferred_master = validated_data.pop('preferred_master', None)
        request = self.context['request']
        booking = Booking.objects.create(
            salon=validated_data['salon'],
            master=preferred_master,
            service_title=', '.join(service.title for service in sorted(services, key=lambda item: service_ids.index(item.pk))),
            client_name=validated_data['name'],
            client_phone=validated_data['phone'],
            client_user=request.user if request.user.is_authenticated else None,
            requested_start=validated_data['requested_start'],
            requested_end=validated_data.get('requested_end'),
            comment=validated_data.get('comment', ''),
            status=Booking.STATUS_PENDING,
        )
        booking.services.set(services)
        return booking
