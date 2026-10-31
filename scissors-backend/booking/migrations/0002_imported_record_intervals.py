from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('booking', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='booking',
            name='end_datetime',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Окончание визита'),
        ),
        migrations.AddField(
            model_name='booking',
            name='yclients_attendance',
            field=models.SmallIntegerField(blank=True, null=True, verbose_name='Статус посещения в YCLIENTS'),
        ),
        migrations.AlterField(
            model_name='booking',
            name='client_name',
            field=models.CharField(blank=True, max_length=255, verbose_name='Имя клиента'),
        ),
        migrations.AlterField(
            model_name='booking',
            name='client_phone',
            field=models.CharField(blank=True, max_length=32, verbose_name='Телефон клиента'),
        ),
        migrations.AlterField(
            model_name='booking',
            name='service_title',
            field=models.TextField(blank=True, verbose_name='Услуга'),
        ),
        migrations.AlterField(
            model_name='booking',
            name='status',
            field=models.CharField(
                choices=[
                    ('confirmed', 'Подтверждена'),
                    ('cancelled', 'Отменена'),
                    ('completed', 'Завершена'),
                    ('no_show', 'Клиент не пришёл'),
                ],
                default='confirmed', max_length=16, verbose_name='Статус',
            ),
        ),
    ]
