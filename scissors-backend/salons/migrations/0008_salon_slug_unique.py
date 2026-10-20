from django.db import migrations, models
from django.db.models import Count


def validate_slugs(apps, schema_editor):
    Salon = apps.get_model('salons', 'Salon')
    salons = Salon.objects.using(schema_editor.connection.alias)
    if salons.filter(slug='').exists() or salons.filter(slug__isnull=True).exists():
        raise RuntimeError('Нельзя создать уникальный индекс: у салонов остались пустые slug.')
    if salons.values('slug').annotate(total=Count('pk')).filter(total__gt=1).exists():
        raise RuntimeError('Нельзя создать уникальный индекс: у салонов есть повторяющиеся slug.')


class Migration(migrations.Migration):
    dependencies = [
        ('salons', '0007_populate_salon_slug'),
    ]

    operations = [
        migrations.RunPython(validate_slugs, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='salon',
            name='slug',
            field=models.SlugField(blank=True, db_index=False, max_length=255, unique=True, verbose_name='Адрес (slug)'),
        ),
    ]
