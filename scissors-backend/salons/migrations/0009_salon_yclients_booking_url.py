from django.db import migrations, models


BOOKING_URLS = {
    '38297': 'https://n20037.yclients.ru',
    '128411': 'https://n117909.yclients.ru',
}


def set_booking_urls(apps, schema_editor):
    Salon = apps.get_model('salons', 'Salon')
    salons = Salon.objects.using(schema_editor.connection.alias)
    for company_id, url in BOOKING_URLS.items():
        salons.filter(yclients_company_id=company_id, yclients_booking_url='').update(
            yclients_booking_url=url,
        )


class Migration(migrations.Migration):
    dependencies = [('salons', '0008_salon_slug_unique')]

    operations = [
        migrations.AddField(
            model_name='salon',
            name='yclients_booking_url',
            field=models.URLField(
                'Ссылка на запись в YCLIENTS', max_length=500, blank=True, default='',
                help_text='Ссылка на форму записи именно этого салона. Не обновляется синхронизацией.',
            ),
        ),
        migrations.RunPython(set_booking_urls, migrations.RunPython.noop),
    ]
