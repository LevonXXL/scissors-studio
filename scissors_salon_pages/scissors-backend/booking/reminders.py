"""
Логика напоминаний за 24ч и 1ч до визита.

Специально вынесена в чистые функции, не завязанные на Celery — так их
можно протестировать обычным Django TestCase без поднятия воркера и
брокера. Обёртка в Celery-задачу — в tasks.py, она тонкая и вызывает
только эти функции.
"""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from .models import Booking

REMINDER_24H = '24h'
REMINDER_1H = '1h'

# Ширина окна, в которое должна попасть задача Celery Beat, чтобы поймать
# нужные записи — задача рассчитана на запуск каждые 5 минут, окно с запасом.
WINDOW = timedelta(minutes=10)


def find_bookings_due_for_reminder(kind: str, now=None):
    """
    Возвращает queryset записей, которым пора отправить напоминание
    указанного типа (REMINDER_24H или REMINDER_1H) прямо сейчас.
    """
    now = now or timezone.now()
    offset = timedelta(hours=24) if kind == REMINDER_24H else timedelta(hours=1)
    flag_field = 'reminder_24h_sent' if kind == REMINDER_24H else 'reminder_1h_sent'

    target_time = now + offset
    window_start = target_time - WINDOW
    window_end = target_time

    return Booking.objects.filter(
        status=Booking.STATUS_CONFIRMED,
        start_datetime__gte=window_start,
        start_datetime__lte=window_end,
        **{flag_field: False},
    ).select_related('master', 'salon')


def mark_reminder_sent(booking: Booking, kind: str):
    flag_field = 'reminder_24h_sent' if kind == REMINDER_24H else 'reminder_1h_sent'
    setattr(booking, flag_field, True)
    booking.save(update_fields=[flag_field])


def build_reminder_text(booking: Booking, kind: str) -> str:
    when = 'завтра' if kind == REMINDER_24H else 'через час'
    return (
        f'Напоминаем: {when} у вас запись к мастеру {booking.master.name} '
        f'({booking.service_title}) в {booking.salon.name} '
        f'на {booking.start_datetime:%d.%m в %H:%M}.'
    )
