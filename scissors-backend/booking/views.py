from django.db import transaction
from django.db.models import Q
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from client_auth.services import client_ip, count_attempt
from client_auth.models import VerifiedPhone
from masters.models import Master
from salons.models import Salon
from services.models import Service, ServiceStaffPrice

from .serializers import BookingRequestSerializer
from .models import Booking


class BookingRequestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = BookingRequestSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        count_attempt('booking-request:ip', client_ip(request), 10, 3600)
        with transaction.atomic():
            booking = serializer.save()
        return Response({
            'id': booking.pk,
            'status': booking.status,
            'detail': 'Заявка принята и ожидает подтверждения администратора.',
        }, status=status.HTTP_201_CREATED)


class MyBookingsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        period = request.query_params.get('period', 'future')
        if period not in ('future', 'past'):
            raise ValidationError({'period': 'Укажите future или past.'})
        phones = list(VerifiedPhone.objects.filter(user=request.user).values_list('phone', flat=True))
        owner = Q(client_user=request.user)
        if phones:
            variants = {
                value for phone in phones
                for value in (phone, phone.removeprefix('+'), phone.removeprefix('+7'))
            }
            owner |= Q(client_user__isnull=True, client_phone__in=variants)
        now = timezone.now()
        bookings = Booking.objects.filter(owner).select_related('salon', 'master').annotate(
            visit_datetime=Coalesce('start_datetime', 'requested_start'),
        )
        bookings = bookings.filter(visit_datetime__gte=now) if period == 'future' else bookings.filter(
            visit_datetime__lt=now,
        )
        bookings = bookings.order_by('visit_datetime' if period == 'future' else '-visit_datetime', '-created_at')
        paginator = PageNumberPagination()
        paginator.page_size = 20
        page = paginator.paginate_queryset(bookings, request, view=self)
        return paginator.get_paginated_response([{
            'id': booking.pk,
            'salon': booking.salon.name,
            'master': booking.master.name if booking.master else None,
            'services': booking.service_title,
            'status': booking.status,
            'requested_start': booking.requested_start,
            'requested_end': booking.requested_end,
            'start_datetime': booking.start_datetime,
            'end_datetime': booking.end_datetime,
        } for booking in page])


class BookingOptionsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        salon_id = request.query_params.get('salon', '')
        if not salon_id.isdecimal() or not Salon.objects.filter(pk=salon_id, is_active=True).exists():
            raise ValidationError({'salon': 'Выберите действующий салон.'})
        services = list(Service.objects.filter(
            salon_offers__salon_id=salon_id, salon_offers__is_active=True,
            category__is_active=True, is_active=True,
        ).distinct().select_related('category').order_by('category__title', 'title'))
        masters = list(Master.objects.filter(
            master_salons__salon_id=salon_id, is_active=True, is_system=False,
            is_booking_placeholder=False,
        ).distinct().order_by('name'))
        master_ids = {master.pk for master in masters}
        assignments = {}
        for service_id, master_id in ServiceStaffPrice.objects.filter(
            service_id__in=[service.pk for service in services], master_id__in=master_ids,
            salon_id=salon_id,
        ).values_list('service_id', 'master_id'):
            assignments.setdefault(service_id, []).append(master_id)
        available_master_ids = {master_id for ids in assignments.values() for master_id in ids}
        return Response({
            'services': [
                {'id': service.pk, 'title': service.title, 'category': service.category.title,
                 'master_ids': sorted(assignments.get(service.pk, []))}
                for service in services
            ],
            'masters': [
                {'id': master.pk, 'name': master.name, 'slug': master.slug}
                for master in masters if master.pk in available_master_ids
            ],
        })
