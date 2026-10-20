from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name='FeedbackRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='Имя')),
                ('phone', models.CharField(max_length=12, verbose_name='Телефон')),
                ('message', models.TextField(verbose_name='Вопрос')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Создано')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='feedback_requests', to=settings.AUTH_USER_MODEL, verbose_name='Пользователь')),
            ],
            options={'verbose_name': 'Обращение', 'verbose_name_plural': 'Обращения', 'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='PushPreference',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('enabled', models.BooleanField(default=False, verbose_name='Получать push-сообщения')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='push_preference', to=settings.AUTH_USER_MODEL)),
            ],
            options={'verbose_name': 'Настройка push', 'verbose_name_plural': 'Настройки push'},
        ),
        migrations.CreateModel(
            name='PushSubscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('endpoint', models.URLField(max_length=2048, unique=True)),
                ('p256dh', models.CharField(max_length=512)),
                ('auth', models.CharField(max_length=256)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='push_subscriptions', to=settings.AUTH_USER_MODEL)),
            ],
            options={'verbose_name': 'Push-подписка', 'verbose_name_plural': 'Push-подписки'},
        ),
    ]
