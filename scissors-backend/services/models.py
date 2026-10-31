from django.db import models
from django.core.exceptions import ValidationError
from filer.fields.image import FilerImageField

from masters.models import Master
from pages.models import Page, PagePicture
from salons.models import Salon


class ServiceCategory(models.Model):
    title = models.CharField('Название', max_length=255)
    code = models.SlugField('Ключ каталога', max_length=100, unique=True, null=True, blank=True)
    image = FilerImageField(verbose_name='Фотография категории', null=True, blank=True,
                            on_delete=models.SET_NULL, related_name='+')
    image_path = models.CharField('Путь к фотографии', max_length=500, blank=True)
    weight = models.IntegerField('Порядок', default=0)
    is_active = models.BooleanField('Показывать', default=True)
    page = models.OneToOneField(Page, verbose_name='Страница', null=True, blank=True, on_delete=models.SET_NULL, related_name='service_category')

    class Meta:
        ordering = ('weight', 'id')
        verbose_name = 'Категория услуг'
        verbose_name_plural = 'Категории услуг'

    def __str__(self):
        return self.title


class Service(models.Model):
    category = models.ForeignKey(ServiceCategory, verbose_name='Категория', related_name='services', on_delete=models.CASCADE)
    page = models.OneToOneField(Page, verbose_name='Страница', null=True, blank=True, on_delete=models.SET_NULL, related_name='service')
    title = models.CharField('Название', max_length=1024)
    code = models.SlugField('Ключ каталога', max_length=255, unique=True, null=True, blank=True)
    price_code = models.CharField(
        'Код в едином прайсе', max_length=64, unique=True, null=True, blank=True,
        help_text='Стабильный код из столбца R. Не меняет адрес страницы услуги.',
    )
    price_internal_category = models.CharField(
        'Внутренняя категория прайса', max_length=32, blank=True,
        help_text='Учётная категория из столбца U; не определяет раздел на сайте.',
    )
    description = models.TextField('Описание', blank=True)
    group_title = models.CharField('Раздел', max_length=255, blank=True)
    subgroup_title = models.CharField('Подгруппа', max_length=255, blank=True)
    conditions = models.TextField('Условия и доплаты', blank=True)
    duration_seconds = models.PositiveIntegerField('Длительность, сек', null=True, blank=True)
    image = FilerImageField(verbose_name='Изображение', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    is_active = models.BooleanField('Показывать', default=True)
    weight = models.IntegerField('Порядок', default=0)
    yclients_service_id = models.CharField('Прежний ID YCLIENTS', max_length=32, null=True, blank=True, unique=True)
    last_synced_at = models.DateTimeField('Последняя синхронизация', null=True, blank=True, editable=False)

    class Meta:
        ordering = ('category', 'weight', 'id')
        verbose_name = 'Услуга'
        verbose_name_plural = 'Услуги'

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        self.price_code = self.price_code or None
        update_fields = kwargs.get('update_fields')
        super().save(*args, **kwargs)
        if (self.page_id and self.image_id and
                (update_fields is None or {'page', 'image'} & set(update_fields))):
            if not PagePicture.objects.filter(page_id=self.page_id, image_id=self.image_id).exists():
                PagePicture.objects.create(page_id=self.page_id, image_id=self.image_id,
                                           alt=self.title[:255])

    @property
    def duration_display(self):
        return f'{self.duration_seconds // 60} минут' if self.duration_seconds else ''


class ServiceSalon(models.Model):
    service = models.ForeignKey(Service, related_name='salon_offers', on_delete=models.CASCADE)
    salon = models.ForeignKey(Salon, related_name='service_offers', on_delete=models.CASCADE)
    is_active = models.BooleanField('Доступна', default=True)
    position = models.IntegerField('Порядок в салоне', default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=('service', 'salon'), name='unique_service_salon')]
        verbose_name = 'Услуга в салоне'
        verbose_name_plural = 'Услуги в салонах'

    def __str__(self):
        return f'{self.service} — {self.salon}'

    def clean(self):
        super().clean()
        if not self.service_id or not self.salon_id:
            return
        salon = self.salon
        is_red_gate = ('krasnye-vorota' in (salon.slug or '') or
                       'красные ворота' in salon.name.casefold())
        if is_red_gate and self.service.category.code not in ('hair', 'forman'):
            raise ValidationError('В салоне «Красные Ворота» доступен только парикмахерский зал.')


class ServicePrice(models.Model):
    salon_service = models.ForeignKey(ServiceSalon, related_name='prices', on_delete=models.CASCADE)
    level = models.CharField('Уровень (пусто для единой цены)', max_length=32, blank=True)
    amount = models.DecimalField('Цена, ₽', max_digits=10, decimal_places=2)

    class Meta:
        constraints = [models.UniqueConstraint(fields=('salon_service', 'level'), name='unique_service_salon_level')]
        verbose_name = 'Цена услуги'
        verbose_name_plural = 'Цены услуг'

    def clean(self):
        super().clean()
        if self.amount is None:
            raise ValidationError({'amount': 'Укажите цену, включая 0, если он задан в Excel.'})


class ServiceStaffPrice(models.Model):
    """Explicit service assignment and optional individual override."""
    service = models.ForeignKey(Service, verbose_name='Услуга', related_name='staff_prices', on_delete=models.CASCADE)
    master = models.ForeignKey(Master, verbose_name='Мастер', related_name='service_prices', on_delete=models.CASCADE)
    salon = models.ForeignKey(Salon, verbose_name='Салон', null=True, blank=True, on_delete=models.CASCADE)
    price_min = models.DecimalField('Индивидуальная цена от', max_digits=10, decimal_places=2, null=True, blank=True)
    price_max = models.DecimalField('Индивидуальная цена до', max_digits=10, decimal_places=2, null=True, blank=True)
    duration_seconds = models.PositiveIntegerField('Индивидуальная длительность, сек', null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=('service', 'master', 'salon'), name='unique_service_master_salon')]
        verbose_name = 'Назначение услуги мастеру'
        verbose_name_plural = 'Назначения услуг мастерам'

    def clean(self):
        super().clean()
        if self._state.adding and not self.salon_id:
            raise ValidationError({'salon': 'Выберите салон для назначения услуги.'})
        if not self.service_id or not self.master_id or not self.salon_id:
            return
        if self.master.is_booking_placeholder:
            raise ValidationError('Технической записи нельзя назначать услуги как мастеру.')
        if not ServiceSalon.objects.filter(service_id=self.service_id, salon_id=self.salon_id,
                                           is_active=True).exists():
            raise ValidationError('Услуга не назначена выбранному салону.')
        if not self.master.master_salons.filter(salon_id=self.salon_id).exists():
            raise ValidationError('Мастер не работает в выбранном салоне.')
        if (self.master.name == 'Михаил Стець' and
                self.service.category.code not in ('hair', 'forman')):
            raise ValidationError('Михаил Стець не оказывает ногтевые и косметологические услуги.')
        level = self.master.price_level
        if level and self.price_min is None and self.price_max is None:
            levels = set(ServicePrice.objects.filter(
                salon_service__service_id=self.service_id,
                salon_service__salon_id=self.salon_id,
            ).values_list('level', flat=True))
            if '' not in levels and level not in levels:
                raise ValidationError('Для уровня мастера нет цены этой услуги в выбранном салоне.')

    def __str__(self):
        return f'{self.service} — {self.master}'
