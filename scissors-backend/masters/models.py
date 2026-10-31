from django.db import models
from django.core.exceptions import ValidationError
from django.conf import settings
from filer.fields.image import FilerImageField

from pages.models import Page
from salons.models import Salon


class Master(models.Model):
    """
    Мастер-партнёр.

    Статус и подтверждённый уровень прайса хранятся отдельно от описания.
    """

    STATUS_SELF_EMPLOYED = 'self_employed'
    STATUS_IP = 'ip'
    STATUS_CHOICES = [
        (STATUS_SELF_EMPLOYED, 'Самозанятый'),
        (STATUS_IP, 'ИП'),
    ]

    salons = models.ManyToManyField(
        Salon, through='MasterSalon', verbose_name='Салоны', related_name='masters', blank=True,
        help_text='Один мастер может работать в нескольких салонах. Доступность услуги и цена '
                   'настраиваются отдельно для каждого салона; назначения услуг мастеру тоже привязаны к салону.'
    )

    name = models.CharField('Имя', max_length=255)
    page = models.OneToOneField(
        Page, verbose_name='Страница', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='master',
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, verbose_name='Учётная запись', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='master_profile',
    )
    PRICE_LEVEL_CHOICES = [
        ('universal', 'Универсал'), ('modeler', 'Модельер'),
        ('stylist', 'Стилист'), ('top_stylist', 'Топ-стилист'),
        ('art_director', 'Арт-директор'), ('nail_master', 'Мастер ногтевого сервиса'),
        ('top_nail_master', 'Топ-мастер ногтевого сервиса'),
    ]
    price_level = models.CharField(
        'Подтверждённый уровень прайса', max_length=32, choices=PRICE_LEVEL_CHOICES,
        blank=True, help_text='Устанавливается вручную; не выводится из данных YCLIENTS.',
    )
    is_booking_placeholder = models.BooleanField(
        'Техническая запись для бронирования', default=False,
        help_text='Лист ожидания или общая позиция без назначенного мастера. Не показывается как специалист и не получает уровень прайса.',
    )

    status = models.CharField(
        'Статус', max_length=32, choices=STATUS_CHOICES, default=STATUS_SELF_EMPLOYED,
        help_text='Обязательно к показу на карточке мастера — статус самостоятельного исполнителя услуги.'
    )
    inn = models.CharField('ИНН', max_length=20, blank=True)

    photo = FilerImageField(
        verbose_name='Фото', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+',
        help_text='Синхронизируется из поля avatar/avatar_big в YCLIENTS (avatar_big — крупная версия).'
    )
    bio = models.TextField('О мастере', blank=True, help_text='Поле information из YCLIENTS.')

    slug = models.SlugField('Адрес карточки', max_length=255, unique=True, blank=True)

    is_system = models.BooleanField(
        'Системная позиция', default=False,
        help_text='Служебная позиция без привязки к конкретному человеку — '
                   'YCLIENTS сам назначает реального свободного мастера при '
                   'записи (например "Бровист"). Не показывать на сайте как '
                   'отдельного партнёра.'
    )

    yclients_user_id = models.CharField(
        'user_id в YCLIENTS', max_length=32, null=True, blank=True, unique=True,
        help_text='Стабильный идентификатор человека — по нему дедуплицируется '
                   'один и тот же мастер в разных салонах. У системных позиций '
                   '(is_system=True) его нет, поле остаётся NULL.'
    )
    yclients_staff_id = models.CharField(
        'Последний известный id связи мастер-салон', max_length=32, blank=True,
        help_text='id связи "сотрудник-салон" в YCLIENTS. НЕ уникален глобально '
                   '(общий счётчик на аккаунт), и у одного мастера в разных '
                   'салонах разные значения — только справочно, не как ключ поиска.'
    )

    last_synced_at = models.DateTimeField('Последняя синхронизация', null=True, blank=True, editable=False)

    is_active = models.BooleanField(
        'Работает сейчас', default=True,
        help_text='Выключите, если мастер больше не работает в пространстве — карточка скроется с сайта.'
    )
    position = models.PositiveIntegerField('Порядок отображения', default=0)

    class Meta:
        verbose_name = 'Мастер-партнёр'
        verbose_name_plural = 'Мастера-партнёры'
        ordering = ('position', 'id')

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if self.is_booking_placeholder and self.price_level:
            raise ValidationError({'price_level': 'Техническая запись не имеет уровня прайса.'})

    def save(self, *args, **kwargs):
        if not self.slug:
            from core_utils.slugify_ru import slugify_ru
            base_slug = slugify_ru(self.name) or 'master'
            slug = base_slug
            i = 1
            while Master.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                i += 1
                slug = f'{base_slug}-{i}'
            self.slug = slug
        super().save(*args, **kwargs)


class MasterSalon(models.Model):
    """Промежуточная таблица Master ↔ Salon.

    Хранит yclients_staff_id — идентификатор привязки мастера к конкретному
    салону в YCLIENTS. У одного мастера разные staff_id в разных салонах.
    Также хранит прямую ссылку записи к мастеру именно в этом салоне.
    """
    master = models.ForeignKey(Master, on_delete=models.CASCADE, related_name='master_salons')
    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name='master_salons')
    yclients_staff_id = models.CharField(
        'YCLIENTS staff ID', max_length=32, blank=True, null=True, unique=True,
        help_text='Идентификатор привязки мастера к этому салону. '
                  'Используется для ссылок на запись в YCLIENTS.',
    )
    yclients_booking_url = models.URLField(
        'Ссылка на запись в YCLIENTS', max_length=500, blank=True, default='',
        help_text='Прямая форма записи к этому мастеру в данном салоне. Не обновляется синхронизацией.',
    )

    class Meta:
        verbose_name = 'Привязка мастера к салону'
        verbose_name_plural = 'Привязки мастеров к салонам'
        unique_together = ('master', 'salon')

    def __str__(self):
        return f'{self.master} — {self.salon}'
