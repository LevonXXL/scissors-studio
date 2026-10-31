from django.db import migrations, models


# YCLIENTS user_id относится к человеку и не меняется между салонами.
# У Инны Горбатко в доступной БД user_id отсутствует, поэтому используем
# подтверждённый ID её связи с Красными Воротами.
BOOKING_URLS = (
    ('3077305', '128411', 'https://n1022915.yclients.ru'),  # Марина Колчанова
    ('3190311', '128411', 'https://n1022916.yclients.ru'),  # Ирина Блудова
    ('12503645', '128411', 'https://n1022925.yclients.ru'),  # Полина Рекрут
    ('763752', '128411', 'https://n1022952.yclients.ru'),  # Михаил Стець
    ('12510870', '38297', 'https://n2080140.yclients.ru'),  # Анна Вренева
    ('12928546', '38297', 'https://n2080161.yclients.ru'),  # Мария Ким
    ('12503645', '38297', 'https://n2080125.yclients.ru'),  # Полина Рекрут
    ('2969659', '38297', 'https://n2080116.yclients.ru'),  # Светлана Миронова
    ('3105352', '38297', 'https://n2080107.yclients.ru'),  # Оксана Рысовец
    ('763752', '38297', 'https://n2077170.yclients.ru'),  # Михаил Стець
)


def set_booking_urls(apps, schema_editor):
    MasterSalon = apps.get_model('masters', 'MasterSalon')
    links = MasterSalon.objects.using(schema_editor.connection.alias)
    for user_id, company_id, url in BOOKING_URLS:
        matching = links.filter(
            master__yclients_user_id=user_id,
            salon__yclients_company_id=company_id,
        )
        if matching.count() == 1:
            matching.filter(yclients_booking_url='').update(yclients_booking_url=url)

    inna = links.filter(
        yclients_staff_id='2763219',
        salon__yclients_company_id='128411',
        master__name='Горбатко Инна',
    )
    if inna.count() == 1:
        inna.filter(yclients_booking_url='').update(
            yclients_booking_url='https://n1022923.yclients.ru',
        )


class Migration(migrations.Migration):
    dependencies = [
        ('masters', '0014_maria_top_nail_master'),
        ('salons', '0009_salon_yclients_booking_url'),
    ]

    operations = [
        migrations.AddField(
            model_name='mastersalon',
            name='yclients_booking_url',
            field=models.URLField(
                'Ссылка на запись в YCLIENTS', max_length=500, blank=True, default='',
                help_text='Прямая форма записи к этому мастеру в данном салоне. Не обновляется синхронизацией.',
            ),
        ),
        migrations.RunPython(set_booking_urls, migrations.RunPython.noop),
    ]
