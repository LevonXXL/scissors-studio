from django.db import migrations


def copy_m2m_to_through(apps, schema_editor):
    Master = apps.get_model('masters', 'Master')
    MasterSalon = apps.get_model('masters', 'MasterSalon')
    for master in Master.objects.all():
        for salon in master.salons.all():
            MasterSalon.objects.get_or_create(master=master, salon=salon)


def reverse(apps, schema_editor):
    MasterSalon = apps.get_model('masters', 'MasterSalon')
    MasterSalon.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ('masters', '0004_add_user_id_and_mastersalon'),
    ]

    operations = [
        migrations.RunPython(copy_m2m_to_through, reverse),
    ]