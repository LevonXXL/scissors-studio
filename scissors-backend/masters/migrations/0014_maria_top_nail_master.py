from django.db import migrations


def set_confirmed_top_nail_master(apps, schema_editor):
    Master = apps.get_model('masters', 'Master')
    Master.objects.filter(
        name='Мария Ким', master_salons__salon__name__icontains='Зеленоград',
        is_booking_placeholder=False,
    ).update(price_level='top_nail_master')


class Migration(migrations.Migration):
    dependencies = [('masters', '0013_salon_help_text')]
    operations = [migrations.RunPython(set_confirmed_top_nail_master, migrations.RunPython.noop)]
