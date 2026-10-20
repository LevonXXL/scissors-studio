from django.db import models
from filer.fields.image import FilerImageField

from pages.models import Page
from salons.models import Salon


class Master(models.Model):
    """
    Мастер-партнёр.

    Статус и категория — структурированные поля, не текст в описании:
    именно это требовалось показать в карточке мастера по итогам аудита
    (см. критические расхождения по /vacancy и картам мастеров).
    """

    STATUS_SELF_EMPLOYED = 'self_employed'
    STATUS_IP = 'ip'
    STATUS_CHOICES = [
        (STATUS_SELF_EMPLOYED, 'Самозанятый'),
        (STATUS_IP, 'ИП'),
    ]

    CATEGORY_UNIVERSAL = 'universal'
    CATEGORY_STYLIST = 'stylist'
    CATEGORY_ART_DIRECTOR = 'art_director'
    CATEGORY_CHOICES = [
        (CATEGORY_UNIVERSAL, 'Универсал / Модельер'),
        (CATEGORY_STYLIST, 'Стилист / Топ-стилист'),
        (CATEGORY_ART_DIRECTOR, 'Арт-директор'),
    ]

    salons = models.ManyToManyField(
        Salon, through='MasterSalon', verbose_name='Салоны', related_name='masters', blank=True,
        help_text='Один мастер может работать в нескольких салонах — цены на услуги в каждом '
                   'салоне задаются отдельно через ServiceStaffPrice (Service уже привязан '
                   'к конкретному салону через категорию), само наличие мастера в нескольких '
                   'салонах не влияет на расчёт цены.'
    )

    name = models.CharField('Имя', max_length=255)
    page = models.OneToOneField(
        Page, verbose_name='Страница', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='master',
    )
    specialization = models.CharField('Специализация', max_length=255, help_text='Например: "Стрижки, окрашивание"')
    category = models.CharField('Категория', max_length=32, choices=CATEGORY_CHOICES, default=CATEGORY_UNIVERSAL)

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
    Нужен для построения ссылок на букинг YCLIENTS (параметр master_id в URL).
    """
    master = models.ForeignKey(Master, on_delete=models.CASCADE, related_name='master_salons')
    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name='master_salons')
    yclients_staff_id = models.CharField(
        'YCLIENTS staff ID', max_length=32, blank=True, null=True, unique=True,
        help_text='Идентификатор привязки мастера к этому салону. '
                  'Используется для ссылок на запись в YCLIENTS.',
    )

    class Meta:
        verbose_name = 'Привязка мастера к салону'
        verbose_name_plural = 'Привязки мастеров к салонам'
        unique_together = ('master', 'salon')

    def __str__(self):
        return f'{self.master} — {self.salon}'
