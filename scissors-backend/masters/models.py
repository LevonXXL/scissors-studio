from django.db import models
from django.core.exceptions import ValidationError
from django.conf import settings
from django.db import transaction
from filer.fields.image import FilerImageField

from pages.models import Page
from salons.models import Salon
from services.price_levels import MASTER_PRICE_LEVEL_CHOICES


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
    PRICE_LEVEL_CHOICES = MASTER_PRICE_LEVEL_CHOICES
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
        creating = self._state.adding
        update_fields = kwargs.get('update_fields')
        if (creating or update_fields is None or 'price_level' in update_fields):
            if self.price_level and self.price_level not in dict(self.PRICE_LEVEL_CHOICES):
                raise ValidationError({'price_level': 'Уровень отсутствует в Excel-прайсе.'})
        if not self.slug:
            from core_utils.slugify_ru import slugify_ru
            base_slug = slugify_ru(self.name) or 'master'
            slug = base_slug
            i = 1
            while Master.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                i += 1
                slug = f'{base_slug}-{i}'
            self.slug = slug
        with transaction.atomic():
            super().save(*args, **kwargs)
            if creating and not self.page_id:
                self.ensure_page()

    def ensure_page(self):
        """Give every persisted master a page, without publishing test records."""
        if self.page_id:
            return self.page
        if not self.pk:
            raise ValueError('Сначала сохраните мастера.')

        from pages.admin_links import page_owners

        with transaction.atomic():
            current_page_id = (Master.objects.select_for_update().filter(pk=self.pk)
                               .values_list('page_id', flat=True).get())
            if current_page_id:
                self.page_id = current_page_id
                return Page.objects.get(pk=current_page_id)

            team = Page.objects.filter(url_path='team', parent__isnull=True).first()
            base_url = self.slug if team else f'master-draft-{self.pk}'
            url = base_url
            path = f'{team.url_path}/{url}' if team else url
            existing = Page.objects.filter(url_path=path).first()
            if existing and not page_owners(existing):
                page = existing
            else:
                suffix = 1
                while existing:
                    suffix += 1
                    url = f'{base_url}-{suffix}'
                    path = f'{team.url_path}/{url}' if team else url
                    existing = Page.objects.filter(url_path=path).first()
                page = Page.objects.create(
                    title=self.name, url=url, parent=team,
                    is_published=bool(
                        team and self.is_active and not self.is_system
                        and not self.is_booking_placeholder
                        and not self.slug.startswith('test-master-sandbox-')
                    ),
                )
            Master.objects.filter(pk=self.pk).update(page=page)
            self.page = page
            return page


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


class MasterServiceWorkPhoto(models.Model):
    """Пример работы мастера по конкретной услуге каталога."""

    master = models.ForeignKey(Master, on_delete=models.CASCADE, related_name='service_work_photos')
    service = models.ForeignKey('services.Service', on_delete=models.PROTECT,
                                related_name='master_work_photos')
    image = FilerImageField(verbose_name='Фотография', on_delete=models.PROTECT, related_name='+')
    caption = models.CharField('Подпись', max_length=255, blank=True)
    position = models.PositiveIntegerField('Порядок', default=0)
    created_at = models.DateTimeField('Добавлено', auto_now_add=True)

    class Meta:
        ordering = ('service__title', 'position', 'id')
        verbose_name = 'Пример работы мастера по услуге'
        verbose_name_plural = 'Примеры работ мастеров по услугам'

    def clean(self):
        super().clean()
        if self.master_id and self.service_id:
            from services.models import ServiceStaffPrice
            if not ServiceStaffPrice.objects.filter(master_id=self.master_id,
                                                    service_id=self.service_id).exists():
                raise ValidationError('Сначала назначьте услугу мастеру хотя бы в одном салоне.')

    def __str__(self):
        return f'{self.master} — {self.service}'


class MasterMessengerAccount(models.Model):
    PLATFORM_TELEGRAM = 'telegram'
    PLATFORM_MAX = 'max'
    PLATFORM_CHOICES = ((PLATFORM_TELEGRAM, 'Telegram'), (PLATFORM_MAX, 'MAX'))

    master = models.ForeignKey(Master, on_delete=models.CASCADE, related_name='messenger_accounts')
    platform = models.CharField(max_length=16, choices=PLATFORM_CHOICES)
    external_user_id = models.CharField(max_length=64)
    pending_action = models.CharField(max_length=32, blank=True)
    pending_service = models.ForeignKey('services.Service', null=True, blank=True,
                                        on_delete=models.SET_NULL, related_name='+')
    linked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=('platform', 'external_user_id'),
                                    name='unique_messenger_user'),
            models.UniqueConstraint(fields=('platform', 'master'),
                                    name='unique_master_messenger'),
        ]
        verbose_name = 'Мессенджер мастера'
        verbose_name_plural = 'Мессенджеры мастеров'


class MasterMessengerPairingCode(models.Model):
    master = models.ForeignKey(Master, on_delete=models.CASCADE, related_name='messenger_pairing_codes')
    digest = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Код подключения мессенджера'
        verbose_name_plural = 'Коды подключения мессенджера'


class ProcessedMessengerUpdate(models.Model):
    platform = models.CharField(max_length=16, choices=MasterMessengerAccount.PLATFORM_CHOICES)
    update_id = models.CharField(max_length=128)
    processed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=('platform', 'update_id'),
                                               name='unique_messenger_update')]
