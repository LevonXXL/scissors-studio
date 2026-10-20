from django.contrib import admin

from .models import Booking


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        'client_name', 'master', 'salon', 'service_title', 'start_datetime',
        'status', 'reminder_24h_sent', 'reminder_1h_sent',
    )
    list_filter = ('status', 'salon', 'reminder_24h_sent', 'reminder_1h_sent')
    search_fields = ('client_name', 'client_phone', 'yclients_record_id')
    readonly_fields = ('yclients_record_id', 'yclients_record_hash', 'created_at')
    date_hierarchy = 'start_datetime'
