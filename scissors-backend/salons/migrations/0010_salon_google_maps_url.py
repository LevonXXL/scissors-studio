from django.db import migrations, models


MOSCOW_YANDEX_URL = 'https://yandex.com.ge/maps/org/scissors_studio/93145938050'
MOSCOW_GOOGLE_URL = (
    'https://www.google.com/maps/place/Scissors+Studio/'
    '@55.7660926,37.647992,17z/data=!4m8!3m7!1s0x46b54ba65639511b:'
    '0xb02ea548000c8bdf!8m2!3d55.7660926!4d37.647992!9m1!1b1!16s%2Fg%2F11ghp2d7_p'
    '?entry=ttu&g_ep=EgoyMDI2MTExMC4wIKXMDSoASAFQAw%3D%3D'
)


def set_moscow_google_url(apps, schema_editor):
    Salon = apps.get_model('salons', 'Salon')
    Salon.objects.using(schema_editor.connection.alias).filter(
        yandex_maps_url=MOSCOW_YANDEX_URL, google_maps_url='',
    ).update(google_maps_url=MOSCOW_GOOGLE_URL)


class Migration(migrations.Migration):
    dependencies = [('salons', '0009_salon_yclients_booking_url')]

    operations = [
        migrations.AddField(
            model_name='salon',
            name='google_maps_url',
            field=models.URLField(
                'Google Maps', max_length=500, blank=True, default='',
                help_text='Прямая ссылка на карточку салона в Google Maps для REWIO.',
            ),
        ),
        migrations.RunPython(set_moscow_google_url, migrations.RunPython.noop),
    ]
