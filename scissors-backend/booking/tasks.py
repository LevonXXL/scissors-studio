"""
Celery-обвязка вокруг reminders.py. В этом наборе файлов Celery намеренно
не настраивается целиком (нужен брокер — Redis, воркер, Beat-расписание) —
это отдельный шаг инфраструктуры. Здесь только сама задача, чтобы дальше
просто подключить её в CELERY_BEAT_SCHEDULE:

    CELERY_BEAT_SCHEDULE = {
        'send-booking-reminders': {
            'task': 'booking.tasks.send_booking_reminders',
            'schedule': 300.0,  # каждые 5 минут
        },
    }
"""

from celery import shared_task

from . import reminders
from .push import send_push_to_user  # см. TODO в push.py — заглушка под FCM/Capacitor


@shared_task
def send_booking_reminders():
    sent_counts = {reminders.REMINDER_24H: 0, reminders.REMINDER_1H: 0}

    for kind in (reminders.REMINDER_24H, reminders.REMINDER_1H):
        for booking in reminders.find_bookings_due_for_reminder(kind):
            if booking.client_user:
                send_push_to_user(
                    user=booking.client_user,
                    text=reminders.build_reminder_text(booking, kind),
                )
            reminders.mark_reminder_sent(booking, kind)
            sent_counts[kind] += 1

    return sent_counts
