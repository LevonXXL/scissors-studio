from django.db import models
from filer.fields.image import FilerImageField

from core_utils.slugify_ru import slugify_ru
from pages.models import Page


class Salon(models.Model):
    """
    Салон (сейчас их 2 — Москва и Зеленоград, но код не завязан на это число:
    структура рассчитана на произвольное количество филиалов).

    Для Яндекс.Карт храним и адрес (для отображения клиенту и для
    schema.org/LocalBusiness), и координаты (для самой отметки на карте).
    Геокодировать адрес в координаты на лету на фронтенде — лишний внешний
    запрос и риск, что Яндекс не распознает адрес однозначно; проще один раз
    вбить координаты в админке (их легко взять, кликнув по нужной точке на
    yandex.ru/maps правой кнопкой — «Что здесь» покажет координаты), либо
    получить их автоматически при синхронизации — YCLIENTS отдаёт
    coordinate_lat/coordinate_lon прямо в ответе /company/{id}.
    """

    name = models.CharField('Название', max_length=255, help_text='Например: "Москва, Красные ворота"')
    slug = models.SlugField('Адрес (slug)', max_length=255, unique=True, blank=True, db_index=False)
    page = models.OneToOneField(
        Page, verbose_name='Страница', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='salon',
    )

    address = models.CharField('Адрес', max_length=500)

    latitude = models.DecimalField(
        'Широта', max_digits=9, decimal_places=6,
        help_text='Например: 55.766960. Точность до 6 знаков достаточна для показа на карте здания.'
    )
    longitude = models.DecimalField(
        'Долгота', max_digits=9, decimal_places=6,
        help_text='Например: 37.652200'
    )

    phone = models.CharField('Телефон', max_length=32, blank=True)
    working_hours = models.CharField(
        'Режим работы', max_length=255, blank=True,
        help_text='Например: "Ежедневно 10:00 — 22:00". Заполняется из поля schedule при синхронизации.'
    )
    description = models.TextField(
        'Описание', blank=True,
        help_text='HTML-описание салона из YCLIENTS (поле description) — используется как есть, без редактирования.'
    )

    logo = FilerImageField(
        verbose_name='Логотип', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+',
        help_text='Синхронизируется из поля logo в YCLIENTS.'
    )

    is_active = models.BooleanField('Активен', default=True, help_text='Скрыть салон с сайта, не удаляя данные')
    position = models.PositiveIntegerField('Порядок отображения', default=0)

    yclients_company_id = models.CharField(
        'ID филиала в YCLIENTS', max_length=32, blank=True, unique=True, null=True,
        help_text='company_id конкретного филиала в YCLIENTS — салоны Москва и Зеленоград это разные company_id.'
    )
    yclients_booking_url = models.URLField(
        'Ссылка на запись в YCLIENTS', max_length=500, blank=True, default='',
        help_text='Ссылка на форму записи именно этого салона. Не обновляется синхронизацией.',
    )

    # Добавить в класс Salon (после yclients_company_id и last_synced_at)

    # --- Ссылки на площадки отзывов (для Rewio) ---

    yandex_maps_url = models.URLField(
        'Яндекс.Карты', max_length=500, blank=True, default='',
        help_text='Прямая ссылка на карточку салона в Яндекс.Картах, '
                  'например: https://yandex.ru/maps/org/scissors/...'
    )

    twogis_url = models.URLField(
        '2ГИС', max_length=500, blank=True, default='',
        help_text='Прямая ссылка на карточку салона в 2ГИС, '
                  'например: https://2gis.ru/moscow/firm/...'
    )

    zoon_url = models.URLField(
        'Zoon', max_length=500, blank=True, default='',
        help_text='Прямая ссылка на карточку салона в Zoon, '
                  'например: https://zoon.ru/msk/...'
    )

    # --- ID объекта в Rewio (заполняется командой sync_rewio_objects) ---

    rewio_object_id = models.CharField(
        'ID объекта в Rewio', max_length=64, blank=True, default='',
        # editable=False,
        help_text='Заполняется автоматически при создании объекта в Rewio через management-команду.'
    )

    last_synced_at = models.DateTimeField('Последняя синхронизация', null=True, blank=True, editable=False)

    class Meta:
        verbose_name = 'Салон'
        verbose_name_plural = 'Салоны'
        ordering = ('position', 'id')

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify_ru(self.name)[:240] or 'salon'
            slug = base
            suffix = 2
            while Salon.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base}-{suffix}'
                suffix += 1
            self.slug = slug
            if kwargs.get('update_fields') is not None:
                kwargs['update_fields'] = set(kwargs['update_fields']) | {'slug'}
        super().save(*args, **kwargs)

    @property
    def coordinates(self):
        """Удобный доступ к паре координат, например для сериализации в [lat, lon]."""
        return [float(self.latitude), float(self.longitude)]


class SalonPhoto(models.Model):
    """Фотогалерея салона — синхронизируется из поля photos в YCLIENTS
    (там просто список путей на assets.yclients.com, здесь — уже скачанные
    и заведённые в filer файлы, с превью "на лету" через easy-thumbnails)."""

    salon = models.ForeignKey(Salon, verbose_name='Салон', related_name='photos', on_delete=models.CASCADE)
    image = FilerImageField(verbose_name='Фото', on_delete=models.CASCADE, related_name='+')
    position = models.PositiveIntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'Фото салона'
        verbose_name_plural = 'Фото салона'
        ordering = ('position', 'id')

    def __str__(self):
        return f'Фото салона «{self.salon}»'
