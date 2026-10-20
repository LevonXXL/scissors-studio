from django.db import models

from salons.models import Salon


class Review(models.Model):
    """Отзыв, синхронизированный из Rewio API.

    Rewio агрегирует отзывы с площадок (Яндекс.Карты, 2ГИС, Zoon и др.)
    для каждого объекта (салона). Один салон = один объект Rewio.
    """

    SOURCE_YANDEX = 1
    SOURCE_2GIS = 2
    SOURCE_ZOON = 3
    SOURCE_GOOGLE = 4
    SOURCE_FLAMP = 5
    SOURCE_OTHER = 99

    SOURCE_CHOICES = [
        (SOURCE_YANDEX, 'Яндекс.Карты'),
        (SOURCE_2GIS, '2ГИС'),
        (SOURCE_ZOON, 'Zoon'),
        (SOURCE_GOOGLE, 'Google'),
        (SOURCE_FLAMP, 'Flamp'),
        (SOURCE_OTHER, 'Другое'),
    ]

    salon = models.ForeignKey(
        Salon, verbose_name='Салон', related_name='reviews',
        on_delete=models.CASCADE, db_index=True,
    )

    # --- Данные из Rewio ---
    rewio_review_id = models.PositiveIntegerField(
        'ID отзыва в Rewio', unique=True,
        help_text='Уникальный идентификатор отзыва в Rewio API.',
    )
    rewio_link_id = models.PositiveIntegerField(
        'ID ссылки (площадки) в Rewio', null=True, blank=True,
        help_text='ID привязки к конкретной площадке внутри объекта Rewio.',
    )
    source = models.PositiveIntegerField(
        'Площадка', choices=SOURCE_CHOICES, default=SOURCE_OTHER, db_index=True,
        help_text='Площадка, с которой собран отзыв.',
    )
    author = models.CharField('Автор', max_length=255, blank=True, default='')
    text = models.TextField('Текст отзыва', blank=True, default='')
    rating = models.PositiveSmallIntegerField(
        'Рейтинг', null=True, blank=True,
        help_text='Оценка от 1 до 5.',
    )
    review_date = models.DateTimeField('Дата отзыва', db_index=True)
    review_url = models.URLField('Ссылка на отзыв', max_length=1000, blank=True, default='')

    # --- Ответ заведения ---
    reply_text = models.TextField('Ответ заведения', blank=True, default='')
    reply_date = models.DateTimeField('Дата ответа', null=True, blank=True)

    # --- Медиа ---
    has_images = models.BooleanField('Есть фото', default=False)
    images = models.JSONField(
        'Ссылки на фото', blank=True, default=list,
        help_text='JSON-массив объектов {"preview": ..., "image": ...} из Rewio.',
    )
    has_videos = models.BooleanField('Есть видео', default=False)
    videos = models.JSONField(
        'Ссылки на видео', blank=True, default=list,
        help_text='JSON-массив видео из Rewio (если поддерживается).',
    )

    # --- Модерация ---
    is_approved = models.BooleanField(
        'Проверен и одобрен к показу', default=False, db_index=True,
        help_text='Пока не отмечено — отзыв нигде на сайте не показывается. '
                   'Публичный API отдаёт только одобренные отзывы.',
    )

    # --- Системные ---
    created_at = models.DateTimeField('Добавлено в БД', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)

    class Meta:
        verbose_name = 'Отзыв'
        verbose_name_plural = 'Отзывы'
        ordering = ('-review_date', '-id')
        constraints = [
            models.UniqueConstraint(
                fields=['salon', 'rewio_review_id'],
                name='unique_review_per_salon',
            ),
        ]

    def __str__(self):
        return f'{self.author or "Аноним"} — {self.review_date:%d.%m.%Y} ({self.get_source_display()})'
