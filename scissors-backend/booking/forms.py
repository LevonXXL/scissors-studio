from datetime import timedelta

from django import forms
from django.db.models import Q

from masters.models import MasterSalon

from .models import Booking


BLOCKING_STATUSES = (Booking.STATUS_CONFIRMED, Booking.STATUS_COMPLETED, Booking.STATUS_NO_SHOW)


class BookingAdminForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = '__all__'

    def clean(self):
        values = super().clean()
        if (self.instance.pk and self.instance.status == Booking.STATUS_PENDING and
                values.get('status') in (Booking.STATUS_COMPLETED, Booking.STATUS_NO_SHOW)):
            raise forms.ValidationError('Сначала подтвердите заявку, затем отмечайте результат визита.')
        if values.get('status') not in BLOCKING_STATUSES:
            return values
        if self.instance.pk and not {'status', 'salon', 'master', 'start_datetime', 'end_datetime'} & set(self.changed_data):
            return values

        salon = values.get('salon')
        master = values.get('master')
        start = values.get('start_datetime')
        end = values.get('end_datetime')
        if not salon or not master or not start or not end:
            raise forms.ValidationError('Для подтверждённой записи укажите салон, мастера, начало и окончание визита.')
        if end <= start:
            raise forms.ValidationError('Окончание визита должно быть позже начала.')
        if not MasterSalon.objects.filter(master=master, salon=salon).exists():
            raise forms.ValidationError('Мастер не привязан к выбранному салону.')
        conflicts = Booking.objects.filter(master=master, status__in=BLOCKING_STATUSES).exclude(pk=self.instance.pk)
        if conflicts.filter(start_datetime__lt=end).filter(
            Q(end_datetime__gt=start) |
            Q(end_datetime__isnull=True, start_datetime__gte=start - timedelta(days=1))
        ).exists():
            raise forms.ValidationError('У мастера уже есть запись в этот интервал, включая записи YCLIENTS.')
        return values
