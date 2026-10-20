from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('pages', '0001_initial')]

    operations = [
        migrations.AlterField(
            model_name='page',
            name='url',
            field=models.SlugField(
                blank=True,
                help_text='Оставьте пустым только для главной; у вложенной страницы укажите один сегмент пути.',
                max_length=255,
                verbose_name='Адрес (slug)',
            ),
        ),
    ]
