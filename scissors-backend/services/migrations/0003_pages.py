import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('services', '0002_alter_service_title'),
        ('pages', '0002_alter_page_url'),
    ]

    operations = [
        migrations.AddField(
            model_name='servicecategory',
            name='page',
            field=models.OneToOneField(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='service_category', to='pages.page', verbose_name='Страница',
            ),
        ),
        migrations.AddField(
            model_name='service',
            name='page',
            field=models.OneToOneField(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='service', to='pages.page', verbose_name='Страница',
            ),
        ),
    ]
