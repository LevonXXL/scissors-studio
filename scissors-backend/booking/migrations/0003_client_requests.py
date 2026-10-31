import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('booking', '0002_imported_record_intervals'),
        ('services', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='booking', name='requested_start',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Удобное время: начало'),
        ),
        migrations.AddField(
            model_name='booking', name='requested_end',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Удобное время: окончание'),
        ),
        migrations.AddField(
            model_name='booking', name='comment',
            field=models.TextField(blank=True, verbose_name='Комментарий клиента'),
        ),
        migrations.AddField(
            model_name='booking', name='services',
            field=models.ManyToManyField(blank=True, to='services.service', verbose_name='Выбранные услуги'),
        ),
        migrations.AlterField(
            model_name='booking', name='master',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='bookings', to='masters.master', verbose_name='Мастер'),
        ),
        migrations.AlterField(
            model_name='booking', name='start_datetime',
            field=models.DateTimeField(blank=True, db_index=True, null=True, verbose_name='Дата и время визита'),
        ),
        migrations.AlterField(
            model_name='booking', name='yclients_record_id',
            field=models.CharField(blank=True, max_length=32, null=True, unique=True, verbose_name='record_id в YCLIENTS'),
        ),
        migrations.AlterField(
            model_name='booking', name='status',
            field=models.CharField(choices=[('pending', 'Ожидает подтверждения'), ('confirmed', 'Подтверждена'), ('cancelled', 'Отменена'), ('completed', 'Завершена'), ('no_show', 'Клиент не пришёл')], default='confirmed', max_length=16, verbose_name='Статус'),
        ),
    ]
