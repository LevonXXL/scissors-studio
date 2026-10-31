from django.db import migrations, models
from django.db.models import Q


def remove_missing_prices(apps, schema_editor):
    ServicePrice = apps.get_model('services', 'ServicePrice')
    ServicePrice.objects.filter(~Q(status='amount') | Q(amount__isnull=True)).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('services', '0008_brow_price_levels'),
    ]

    operations = [
        migrations.RunPython(remove_missing_prices, migrations.RunPython.noop),
        migrations.RemoveField(model_name='serviceprice', name='status'),
        migrations.AlterField(
            model_name='serviceprice', name='amount',
            field=models.DecimalField('Цена, ₽', max_digits=10, decimal_places=2),
        ),
    ]
