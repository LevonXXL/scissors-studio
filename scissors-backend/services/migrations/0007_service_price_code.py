from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('services', '0006_hold_acupuncture_until_review'),
    ]

    operations = [
        migrations.AddField(
            model_name='service',
            name='price_code',
            field=models.CharField(
                'Код в едином прайсе', max_length=64, unique=True, null=True, blank=True,
                help_text='Стабильный код из столбца R. Не меняет адрес страницы услуги.',
            ),
        ),
        migrations.AddField(
            model_name='service',
            name='price_internal_category',
            field=models.CharField(
                'Внутренняя категория прайса', max_length=32, blank=True,
                help_text='Учётная категория из столбца U; не определяет раздел на сайте.',
            ),
        ),
    ]
