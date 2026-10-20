import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('masters', '0009_master_is_system_master_yclients_staff_id_and_more'),
        ('pages', '0002_alter_page_url'),
    ]

    operations = [
        migrations.AddField(
            model_name='master',
            name='page',
            field=models.OneToOneField(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='master', to='pages.page', verbose_name='Страница',
            ),
        ),
    ]
