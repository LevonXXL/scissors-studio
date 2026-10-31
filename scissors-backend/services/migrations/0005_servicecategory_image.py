import django.db.models.deletion
import filer.fields.image
from django.conf import settings
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('services', '0004_serviceprice_servicesalon_alter_service_options_and_more'),
        migrations.swappable_dependency(settings.FILER_IMAGE_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='servicecategory',
            name='image',
            field=filer.fields.image.FilerImageField(blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL, related_name='+',
                to=settings.FILER_IMAGE_MODEL, verbose_name='Фотография категории'),
        ),
    ]
