from django.conf import settings
from django.db import models


class FeedbackRequest(models.Model):
    name = models.CharField('Имя', max_length=100)
    phone = models.CharField('Телефон или email', max_length=254)
    message = models.TextField('Вопрос')
    created_at = models.DateTimeField('Создано', auto_now_add=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='Пользователь',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='feedback_requests',
    )

    class Meta:
        verbose_name = 'Обращение'
        verbose_name_plural = 'Обращения'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} — {self.created_at:%d.%m.%Y %H:%M}'


class PushPreference(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='push_preference',
    )
    enabled = models.BooleanField('Получать push-сообщения', default=False)

    class Meta:
        verbose_name = 'Настройка push'
        verbose_name_plural = 'Настройки push'

    def __str__(self):
        return str(self.user)


class PushSubscription(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='push_subscriptions',
    )
    endpoint = models.URLField(max_length=2048, unique=True)
    p256dh = models.CharField(max_length=512)
    auth = models.CharField(max_length=256)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Push-подписка'
        verbose_name_plural = 'Push-подписки'

    def __str__(self):
        return f'Подписка #{self.pk}'
