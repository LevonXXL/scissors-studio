import django.db.models.deletion
import filer.fields.image
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('pages', '0003_uslugi_root'),
        migrations.swappable_dependency(settings.FILER_IMAGE_MODEL),
    ]

    operations = [
        migrations.RenameField(
            model_name='pagepicture',
            old_name='image',
            new_name='legacy_image',
        ),
        migrations.AlterField(
            model_name='pagepicture',
            name='legacy_image',
            field=models.ImageField(blank=True, upload_to='pages/pictures/', verbose_name='Прежнее изображение'),
        ),
        migrations.AddField(
            model_name='pagepicture',
            name='image',
            field=filer.fields.image.FilerImageField(blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL, related_name='+',
                to=settings.FILER_IMAGE_MODEL, verbose_name='Изображение в Filer'),
        ),
    ]
