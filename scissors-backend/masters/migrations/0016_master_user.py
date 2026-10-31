import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('masters', '0015_mastersalon_yclients_booking_url'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='master',
            name='user',
            field=models.OneToOneField(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='master_profile', to=settings.AUTH_USER_MODEL,
                verbose_name='Учётная запись',
            ),
        ),
    ]
