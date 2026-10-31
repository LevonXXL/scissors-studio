from django.db import models

from masters.models import Master
from salons.models import Salon


class Booking(models.Model):
    """Local visit or unconfirmed request; YCLIENTS IDs exist only on imported visits."""

    STATUS_PENDING = 'pending'
    STATUS_CONFIRMED = 'confirmed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_COMPLETED = 'completed'
    STATUS_NO_SHOW = 'no_show'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Ожидает подтверждения'),
        (STATUS_CONFIRMED, 'Подтверждена'),
        (STATUS_CANCELLED, 'Отменена'),
        (STATUS_COMPLETED, 'Завершена'),
        (STATUS_NO_SHOW, 'Клиент не пришёл'),
    ]

    salon = models.ForeignKey(Salon, verbose_name='Салон', on_delete=models.PROTECT, related_name='bookings')
    master = models.ForeignKey(
        Master, verbose_name='Мастер', null=True, blank=True,
        on_delete=models.PROTECT, related_name='bookings',
    )
    services = models.ManyToManyField('services.Service', verbose_name='Выбранные услуги', blank=True)

    # Snapshot text also covers imported records without Service relations.
    service_title = models.TextField('Услуга', blank=True)

    client_name = models.CharField('Имя клиента', max_length=255, blank=True)
    client_phone = models.CharField('Телефон клиента', max_length=32, blank=True)
    # Для push нужен привязанный пользователь приложения, а не просто телефон —
    # без аккаунта/устройства некуда слать уведомление. Заполняется, когда
    # запись сделана авторизованным пользователем приложения (не по телефону
    # администратором и не гостем без регистрации).
    client_user = models.ForeignKey(
        'auth.User', verbose_name='Пользователь приложения',
        null=True, blank=True, on_delete=models.SET_NULL, related_name='bookings',
    )

    requested_start = models.DateTimeField('Удобное время: начало', null=True, blank=True)
    requested_end = models.DateTimeField('Удобное время: окончание', null=True, blank=True)
    comment = models.TextField('Комментарий клиента', blank=True)
    start_datetime = models.DateTimeField('Дата и время визита', null=True, blank=True, db_index=True)
    end_datetime = models.DateTimeField('Окончание визита', null=True, blank=True)

    status = models.CharField('Статус', max_length=16, choices=STATUS_CHOICES, default=STATUS_CONFIRMED)

    yclients_record_id = models.CharField(
        'record_id в YCLIENTS', max_length=32, unique=True, null=True, blank=True,
    )
    yclients_record_hash = models.CharField(
        'record_hash в YCLIENTS', max_length=64, blank=True,
        help_text='Нужен для последующих обращений к записи в YCLIENTS API (отмена, статус).'
    )
    yclients_attendance = models.SmallIntegerField('Статус посещения в YCLIENTS', null=True, blank=True)

    reminder_24h_sent = models.BooleanField('Напоминание за сутки отправлено', default=False)
    reminder_1h_sent = models.BooleanField('Напоминание за час отправлено', default=False)

    created_at = models.DateTimeField('Создана', auto_now_add=True)

    class Meta:
        verbose_name = 'Запись'
        verbose_name_plural = 'Записи'
        ordering = ('-start_datetime',)
        indexes = [
            models.Index(fields=['status', 'start_datetime']),
        ]

    def __str__(self):
        when = self.start_datetime or self.requested_start
        return f'{self.client_name or "Клиент"} → {self.master or "любой мастер"} ({when:%d.%m.%Y %H:%M})' if when else f'Заявка #{self.pk}'
