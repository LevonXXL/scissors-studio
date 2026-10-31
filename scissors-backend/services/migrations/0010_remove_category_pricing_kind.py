from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('services', '0009_price_rows_only_for_amounts'),
    ]

    operations = [
        migrations.RemoveField(model_name='servicecategory', name='pricing_kind'),
    ]
