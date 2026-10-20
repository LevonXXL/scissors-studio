# masters/migrations/0006_switch_m2m_to_through.py

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('masters', '0005_migrate_m2m_to_through'),
    ]

    operations = [
        # Удаляем старый M2M (без through) — Django удалит таблицу masters_master_salons
        migrations.RemoveField(
            model_name='master',
            name='salons',
        ),
        # Добавляем новый M2M с through= — таблица MasterSalon уже существует (создана в 0004)
        migrations.AddField(
            model_name='master',
            name='salons',
            field=models.ManyToManyField(
                blank=True,
                help_text='Один мастер может работать в нескольких салонах — цены на услуги в каждом '
                           'салоне задаются отдельно через ServiceStaffPrice (Service уже привязан '
                           'к конкретному салону через категорию), само наличие мастера в нескольких '
                           'салонах не влияет на расчёт цены.',
                related_name='masters',
                through='masters.MasterSalon',
                to='salons.salon',
                verbose_name='Салоны',
            ),
        ),
    ]