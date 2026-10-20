from django.db import migrations, models

HELP = (
    'Если не заполнено — генерируется транслитерацией из названия. '
    'Для Москвы/Зеленограда задайте вручную "moscow"/"zelenograd" — '
    'так называются страницы на фронтенде (транслитерация дала бы "moskva").'
)

# Города, у которых исторически сложившийся английский slug на фронтенде
# (простая транслитерация дала бы "moskva"). Определяем по подстроке в названии.
KNOWN_SLUGS = (('москва', 'moscow'), ('зеленоград', 'zelenograd'))


def fill_slugs(apps, schema_editor):
    """Заполняет slug у уже существующих салонов — иначе добавление unique-поля
    упало бы на дубликате пустой строки, если салонов больше одного."""
    from core_utils.slugify_ru import slugify_ru

    Salon = apps.get_model('salons', 'Salon')
    used = set()
    for salon in Salon.objects.order_by('id'):
        name = (salon.name or '').lower()
        base = next((slug for key, slug in KNOWN_SLUGS if key in name), None) \
            or slugify_ru(salon.name) or 'salon'
        slug, i = base, 1
        while slug in used:
            i += 1
            slug = f'{base}-{i}'
        used.add(slug)
        salon.slug = slug
        salon.save(update_fields=['slug'])


class Migration(migrations.Migration):

    dependencies = [
        ('salons', '0005_alter_salon_rewio_object_id'),
    ]

    operations = [
        # 1. Добавляем поле без unique — у существующих строк оно пока пустое.
        migrations.AddField(
            model_name='salon',
            name='slug',
            field=models.SlugField(blank=True, default='', max_length=255, verbose_name='Адрес (slug)'),
            preserve_default=False,
        ),
        # 2. Заполняем у существующих салонов.
        migrations.RunPython(fill_slugs, migrations.RunPython.noop),
        # 3. Теперь, когда значения уникальны, включаем unique.
        migrations.AlterField(
            model_name='salon',
            name='slug',
            field=models.SlugField(blank=True, help_text=HELP, max_length=255, unique=True, verbose_name='Адрес (slug)'),
        ),
    ]
