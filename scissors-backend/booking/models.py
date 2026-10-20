from django.db import models

from masters.models import Master
from salons.models import Salon


class Booking(models.Model):
    """
    Локальная копия записи из YCLIENTS.

    Зачем своя таблица, а не просто дёргать YCLIENTS по расписанию:
    1. Напоминания за 24ч и 1ч — периодическая задача (Celery Beat), которая
       должна быстро находить «кому пора напомнить» без похода во внешний
       API на каждый тик. Обычный индекс по `start_datetime` в своей БД —
       быстро и надёжно; дёргать YCLIENTS раз в 5 минут за списком всех
       записей всех салонов — медленно, лишняя нагрузка и точка отказа.
    2. Пуш нужно отправить один раз — локальные флаги `reminder_24h_sent` /
       `reminder_1h_sent` дают идемпотентность без внешнего состояния.
    3. Собственная история записей клиента внутри приложения (для профиля,
       для будущей аналитики) не зависит от доступности YCLIENTS API.

    Статус синхронизируется с YCLIENTS двумя путями: сразу при создании
    записи (мы сами её создали через book_record) и через вебхуки YCLIENTS
    при изменении/отмене записи администратором или клиентом по телефону —
    без вебхука отменённая по телефону запись останется в статусе
    confirmed и напоминание всё равно уйдёт, поэтому вебхук обязателен,
    а не опционален.
    """

    STATUS_CONFIRMED = 'confirmed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_COMPLETED = 'completed'
    STATUS_CHOICES = [
        (STATUS_CONFIRMED, 'Подтверждена'),
        (STATUS_CANCELLED, 'Отменена'),
        (STATUS_COMPLETED, 'Завершена'),
    ]

    salon = models.ForeignKey(Salon, verbose_name='Салон', on_delete=models.PROTECT, related_name='bookings')
    master = models.ForeignKey(Master, verbose_name='Мастер', on_delete=models.PROTECT, related_name='bookings')

    # Что именно записали — денормализованный текст, а не FK на каталог
    # услуг: своего каталога Service пока нет, услуги живут в YCLIENTS.
    service_title = models.CharField('Услуга', max_length=255)

    client_name = models.CharField('Имя клиента', max_length=255)
    client_phone = models.CharField('Телефон клиента', max_length=32)
    # Для push нужен привязанный пользователь приложения, а не просто телефон —
    # без аккаунта/устройства некуда слать уведомление. Заполняется, когда
    # запись сделана авторизованным пользователем приложения (не по телефону
    # администратором и не гостем без регистрации).
    client_user = models.ForeignKey(
        'auth.User', verbose_name='Пользователь приложения',
        null=True, blank=True, on_delete=models.SET_NULL, related_name='bookings',
    )

    start_datetime = models.DateTimeField('Дата и время визита', db_index=True)

    status = models.CharField('Статус', max_length=16, choices=STATUS_CHOICES, default=STATUS_CONFIRMED)

    yclients_record_id = models.CharField('record_id в YCLIENTS', max_length=32, unique=True)
    yclients_record_hash = models.CharField(
        'record_hash в YCLIENTS', max_length=64, blank=True,
        help_text='Нужен для последующих обращений к записи в YCLIENTS API (отмена, статус).'
    )

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
        return f'{self.client_name} → {self.master} ({self.start_datetime:%d.%m.%Y %H:%M})'
