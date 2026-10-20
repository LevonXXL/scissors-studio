from django.db import models
from filer.fields.image import FilerImageField

from masters.models import Master
from salons.models import Salon


class ServiceCategory(models.Model):
    """
    Категория услуг (например «Стрижки», «Косметология»).

    В YCLIENTS категории приходят per-салон (эндпоинт /service_categories/{company_id}),
    поэтому FK на Salon, а не общий справочник — даже если у двух салонов
    категория называется одинаково, это две разные записи YCLIENTS
    (это и даёт механизм "категории может не быть в конкретном салоне",
    который уже реализован на фронтенде).
    """

    salon = models.ForeignKey(Salon, verbose_name='Салон', related_name='service_categories', on_delete=models.CASCADE)
    title = models.CharField('Название', max_length=255)
    weight = models.IntegerField('Вес (порядок)', default=0, help_text='Из поля weight в YCLIENTS — выше вес, выше в списке.')
    is_chain = models.BooleanField('Общая для сети', default=False, help_text='Поле is_chain из YCLIENTS.')
    is_active = models.BooleanField('Показывать на сайте', default=True)

    yclients_category_id = models.CharField('ID категории в YCLIENTS', max_length=32)
    last_synced_at = models.DateTimeField('Последняя синхронизация', null=True, blank=True, editable=False)

    class Meta:
        verbose_name = 'Категория услуг'
        verbose_name_plural = 'Категории услуг'
        ordering = ('salon', '-weight', 'title')
        unique_together = ('salon', 'yclients_category_id')

    def __str__(self):
        return f'{self.title} ({self.salon})'


class Service(models.Model):
    """Услуга внутри категории. Цена по умолчанию — price_min/price_max из
    YCLIENTS, но у конкретных мастеров может быть переопределена — см.
    ServiceStaffPrice (так фронтенд показывает «Универсал / Топ-стилист /
    Арт-директор» — это переопределения цены per-мастер, не отдельные поля)."""

    category = models.ForeignKey(ServiceCategory, verbose_name='Категория', related_name='services', on_delete=models.CASCADE)

    title = models.CharField('Название', max_length=1024)
    description = models.TextField('Описание', blank=True, help_text='Поле comment из YCLIENTS, если заполнено.')

    price_min = models.DecimalField('Цена от', max_digits=10, decimal_places=2, default=0)
    price_max = models.DecimalField('Цена до', max_digits=10, decimal_places=2, default=0)
    duration_seconds = models.PositiveIntegerField('Длительность, сек', null=True, blank=True, help_text='Поле duration/seance_length из YCLIENTS.')

    image = FilerImageField(
        verbose_name='Изображение', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+',
        help_text='Из поля image_group в YCLIENTS, если для услуги загружено фото.'
    )

    is_active = models.BooleanField('Показывать на сайте', default=True, help_text='Из поля active в YCLIENTS.')
    weight = models.IntegerField('Вес (порядок)', default=0)

    yclients_service_id = models.CharField('ID услуги в YCLIENTS', max_length=32, unique=True)
    last_synced_at = models.DateTimeField('Последняя синхронизация', null=True, blank=True, editable=False)

    class Meta:
        verbose_name = 'Услуга'
        verbose_name_plural = 'Услуги'
        ordering = ('category', '-weight', 'title')

    def __str__(self):
        return self.title

    @property
    def duration_display(self) -> str:
        if not self.duration_seconds:
            return ''
        minutes = self.duration_seconds // 60
        return f'{minutes} минут'


class ServiceStaffPrice(models.Model):
    """
    Переопределение цены/длительности услуги для конкретного мастера —
    ровно то, что в YCLIENTS лежит во вложенном списке services[].staff[]
    (поля price.min/price.max и seance_length там же — цена приходит
    диапазоном {min, max}, не одним числом, даже когда min == max).
    Если для мастера нет записи здесь — используется общая
    price_min/price_max/duration_seconds услуги.
    """

    service = models.ForeignKey(Service, verbose_name='Услуга', related_name='staff_prices', on_delete=models.CASCADE)
    master = models.ForeignKey(Master, verbose_name='Мастер', related_name='service_prices', on_delete=models.CASCADE)

    price_min = models.DecimalField('Цена от', max_digits=10, decimal_places=2, null=True, blank=True)
    price_max = models.DecimalField('Цена до', max_digits=10, decimal_places=2, null=True, blank=True)
    duration_seconds = models.PositiveIntegerField('Длительность, сек', null=True, blank=True)

    class Meta:
        verbose_name = 'Цена услуги у мастера'
        verbose_name_plural = 'Цены услуг у мастеров'
        unique_together = ('service', 'master')

    def __str__(self):
        return f'{self.service} — {self.master}'
