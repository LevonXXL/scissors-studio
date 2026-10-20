from django.db import models
from filer.fields.image import FilerImageField


class SyncedImage(models.Model):
    """
    Кэш «эта картинка с таким URL уже скачана и лежит в filer как вот этот
    Image» — без него каждый прогон синхронизации заново тянул бы из
    YCLIENTS одни и те же фото салонов/мастеров/услуг по HTTP.

    Не привязана к конкретной модели (Salon/Master/Service) специально —
    один и тот же файл в YCLIENTS теоретически может быть переиспользован
    в нескольких местах, а кэш работает по URL независимо от того, где на
    сайте картинка используется.
    """

    source_url = models.URLField('Исходный URL в YCLIENTS', max_length=500, unique=True)
    image = FilerImageField(verbose_name='Файл в medialib', on_delete=models.CASCADE, related_name='+')
    downloaded_at = models.DateTimeField('Скачано', auto_now_add=True)

    class Meta:
        verbose_name = 'Синхронизированное изображение'
        verbose_name_plural = 'Синхронизированные изображения'

    def __str__(self):
        return self.source_url
