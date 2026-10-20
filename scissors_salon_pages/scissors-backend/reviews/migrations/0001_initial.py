from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('salons', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Review',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rewio_review_id', models.PositiveIntegerField(help_text='Уникальный идентификатор отзыва в Rewio API.', unique=True, verbose_name='ID отзыва в Rewio')),
                ('rewio_link_id', models.PositiveIntegerField(blank=True, help_text='ID привязки к конкретной площадке внутри объекта Rewio.', null=True, verbose_name='ID ссылки (площадки) в Rewio')),
                ('source', models.PositiveIntegerField(choices=[(1, 'Яндекс.Карты'), (2, '2ГИС'), (3, 'Zoon'), (4, 'Google'), (5, 'Flamp'), (99, 'Другое')], db_index=True, default=99, verbose_name='Площадка')),
                ('author', models.CharField(blank=True, default='', max_length=255, verbose_name='Автор')),
                ('text', models.TextField(blank=True, default='', verbose_name='Текст отзыва')),
                ('rating', models.PositiveSmallIntegerField(blank=True, help_text='Оценка от 1 до 5.', null=True, verbose_name='Рейтинг')),
                ('review_date', models.DateTimeField(db_index=True, verbose_name='Дата отзыва')),
                ('review_url', models.URLField(blank=True, default='', max_length=1000, verbose_name='Ссылка на отзыв')),
                ('reply_text', models.TextField(blank=True, default='', verbose_name='Ответ заведения')),
                ('reply_date', models.DateTimeField(blank=True, null=True, verbose_name='Дата ответа')),
                ('has_images', models.BooleanField(default=False, verbose_name='Есть фото')),
                ('images', models.JSONField(blank=True, default=list, help_text='JSON-массив объектов {"preview": ..., "image": ...} из Rewio.', verbose_name='Ссылки на фото')),
                ('has_videos', models.BooleanField(default=False, verbose_name='Есть видео')),
                ('videos', models.JSONField(blank=True, default=list, help_text='JSON-массив видео из Rewio (если поддерживается).', verbose_name='Ссылки на видео')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Добавлено в БД')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Обновлено')),
                ('salon', models.ForeignKey(db_index=True, on_delete=django.db.models.deletion.CASCADE, related_name='reviews', to='salons.salon', verbose_name='Салон')),
            ],
            options={
                'verbose_name': 'Отзыв',
                'verbose_name_plural': 'Отзывы',
                'ordering': ('-review_date', '-id'),
            },
        ),
        migrations.AddConstraint(
            model_name='review',
            constraint=models.UniqueConstraint(fields=['salon', 'rewio_review_id'], name='unique_review_per_salon'),
        ),
    ]
