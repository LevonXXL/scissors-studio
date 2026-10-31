from datetime import timedelta
from zoneinfo import ZoneInfo

from django.contrib import admin
from django.db import transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from unfold.admin import ModelAdmin

from .models import Booking
from .forms import BLOCKING_STATUSES, BookingAdminForm
from masters.models import Master, MasterSalon
from salons.models import Salon


CALENDAR_TIME_ZONE = ZoneInfo('Europe/Moscow')


@admin.register(Booking)
class BookingAdmin(ModelAdmin):
    form = BookingAdminForm
    change_list_template = 'booking/calendar.html'
    list_fullwidth = True
    list_display = (
        'client_name', 'master', 'salon', 'service_title', 'start_datetime', 'end_datetime',
        'status', 'reminder_24h_sent', 'reminder_1h_sent',
    )
    list_filter = ('status', 'salon', 'reminder_24h_sent', 'reminder_1h_sent')
    search_fields = ('client_name', 'client_phone', 'yclients_record_id')
    readonly_fields = ('yclients_record_id', 'yclients_record_hash', 'yclients_attendance', 'created_at')
    date_hierarchy = 'start_datetime'

    def get_urls(self):
        return [
            path(
                'calendar-events/',
                self.admin_site.admin_view(self.calendar_events),
                name='booking_booking_calendar_events',
            ),
        ] + super().get_urls()

    def changelist_view(self, request, extra_context=None):
        salons = list(
            Salon.objects.annotate(booking_count=Count('bookings'))
            .order_by('-booking_count', 'pk')
        )
        pending = Booking.objects.filter(status=Booking.STATUS_PENDING).select_related(
            'salon', 'master',
        ).order_by('created_at')
        calendar_masters = {str(salon.pk): [] for salon in salons}
        for link in MasterSalon.objects.filter(
            salon__in=salons, master__is_active=True,
            master__is_system=False, master__is_booking_placeholder=False,
        ).select_related('master').order_by('master__position', 'master__name', 'master_id'):
            calendar_masters[str(link.salon_id)].append({
                'id': link.master_id, 'name': link.master.name,
            })
        context = {
            'calendar_salons': salons,
            'calendar_masters': calendar_masters,
            'calendar_events_url': reverse('admin:booking_booking_calendar_events'),
            'calendar_can_add': self.has_add_permission(request),
            'pending_bookings': [
                booking for booking in pending
                if self.has_view_or_change_permission(request, booking)
            ],
        }
        context.update(extra_context or {})
        return super().changelist_view(request, extra_context=context)

    def calendar_events(self, request):
        if not self.has_view_or_change_permission(request):
            return JsonResponse({'error': 'Нет доступа к записям.'}, status=403)
        start = parse_datetime(request.GET.get('start', ''))
        end = parse_datetime(request.GET.get('end', ''))
        if not start or not end:
            return JsonResponse({'error': 'Некорректный диапазон дат.'}, status=400)
        # FullCalendar without a named-time-zone plugin sends Moscow dates without an offset.
        if timezone.is_naive(start):
            start = timezone.make_aware(start, CALENDAR_TIME_ZONE)
        if timezone.is_naive(end):
            end = timezone.make_aware(end, CALENDAR_TIME_ZONE)
        if end <= start or end - start > timedelta(days=62):
            return JsonResponse({'error': 'Диапазон календаря должен быть не больше 62 дней.'}, status=400)
        salon_id = request.GET.get('salon', '')
        if salon_id and not salon_id.isdecimal():
            return JsonResponse({'error': 'Некорректный ID салона.'}, status=400)

        queryset = self.get_queryset(request).exclude(status=Booking.STATUS_PENDING).filter(start_datetime__lt=end).filter(
            Q(end_datetime__gt=start) | Q(end_datetime__isnull=True, start_datetime__gte=start)
        ).select_related('salon', 'master')
        if salon_id:
            queryset = queryset.filter(salon_id=salon_id)

        events = []
        for booking in queryset:
            if not self.has_view_or_change_permission(request, booking):
                continue
            title = f'{booking.master.name if booking.master else "Мастер не указан"} · {booking.client_name or booking.service_title or "Занято"}'
            if booking.end_datetime is None:
                title += ' (окончание не указано)'
            events.append({
                'id': booking.pk,
                'title': title,
                'start': timezone.localtime(booking.start_datetime, CALENDAR_TIME_ZONE).isoformat(),
                'end': (
                    timezone.localtime(booking.end_datetime, CALENDAR_TIME_ZONE).isoformat()
                    if booking.end_datetime else None
                ),
                'url': reverse('admin:booking_booking_change', args=(booking.pk,)),
                'classNames': [f'booking-status-{booking.status}'],
                'extendedProps': {
                    'salon': booking.salon.name,
                    'master_id': booking.master_id,
                    'master_name': booking.master.name if booking.master else '',
                    'client_name': booking.client_name,
                    'status': booking.get_status_display(),
                    'service': booking.service_title,
                },
            })
        return JsonResponse(events, safe=False)

    def render_change_form(self, request, context, *args, **kwargs):
        response = super().render_change_form(request, context, *args, **kwargs)
        if request.GET.get('calendar_modal') == '1':
            response.template_name = 'booking/calendar_change_form.html'
        return response

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        if request.method == 'POST' and request.POST.get('status') in BLOCKING_STATUSES:
            master_id = request.POST.get('master', '')
            if master_id.isdecimal():
                # Serialize confirmations for one master across concurrent admin requests.
                with transaction.atomic():
                    Master.objects.select_for_update().filter(pk=master_id).exists()
                    response = super().changeform_view(request, object_id, form_url, extra_context)
            else:
                response = super().changeform_view(request, object_id, form_url, extra_context)
        else:
            response = super().changeform_view(request, object_id, form_url, extra_context)
        if request.GET.get('calendar_modal') == '1':
            response['X-Frame-Options'] = 'SAMEORIGIN'
        return response

    def response_change(self, request, obj):
        if request.GET.get('calendar_modal') == '1':
            return TemplateResponse(request, 'booking/calendar_saved.html')
        return super().response_change(request, obj)

    def response_add(self, request, obj, post_url_continue=None):
        if request.GET.get('calendar_modal') == '1':
            return TemplateResponse(request, 'booking/calendar_saved.html')
        return super().response_add(request, obj, post_url_continue)
