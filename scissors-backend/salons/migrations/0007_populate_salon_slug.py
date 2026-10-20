from django.core.exceptions import ValidationError
from django.core.validators import validate_slug
from django.db import migrations


def populate_slugs(apps, schema_editor):
    from core_utils.slugify_ru import slugify_ru

    Salon = apps.get_model('salons', 'Salon')
    db_alias = schema_editor.connection.alias
    salons = list(Salon.objects.using(db_alias).order_by('pk').only('pk', 'name', 'slug'))
    used = set()
    preserved_ids = set()

    # Reserve existing valid values first, including those on later rows.
    # For duplicate values the oldest row keeps its slug.
    for salon in salons:
        slug = salon.slug or ''
        if not slug or len(slug) > 255:
            continue
        try:
            validate_slug(slug)
        except ValidationError:
            continue
        if slug.casefold() not in used:
            used.add(slug.casefold())
            preserved_ids.add(salon.pk)

    for salon in salons:
        if salon.pk in preserved_ids:
            continue

        base = slugify_ru(salon.name or '')[:240] or f'salon-{salon.pk}'
        slug = base
        suffix_number = 2
        while slug.casefold() in used:
            suffix = f'-{suffix_number}'
            slug = f'{base[:255 - len(suffix)]}{suffix}'
            suffix_number += 1

        salon.slug = slug
        salon.save(using=db_alias, update_fields=['slug'])
        used.add(slug.casefold())


class Migration(migrations.Migration):
    dependencies = [
        ('salons', '0006_salon_page_salon_slug'),
    ]

    operations = [
        migrations.RunPython(populate_slugs, migrations.RunPython.noop),
    ]
