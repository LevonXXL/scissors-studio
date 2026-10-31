from django.db import migrations, models


def migrate_brow_prices(apps, schema_editor):
    Category = apps.get_model('services', 'ServiceCategory')
    ServicePrice = apps.get_model('services', 'ServicePrice')
    Category.objects.filter(code='browlashes').update(pricing_kind='brow')
    old_prices = ServicePrice.objects.filter(
        salon_service__service__category__code='browlashes', level='',
    )
    for price in old_prices:
        if ServicePrice.objects.filter(salon_service_id=price.salon_service_id,
                                       level='modeler').exists():
            price.delete()
        else:
            price.level = 'modeler'
            price.save(update_fields=['level'])


class Migration(migrations.Migration):
    dependencies = [
        ('services', '0007_service_price_code'),
    ]

    operations = [
        migrations.AlterField(
            model_name='servicecategory',
            name='pricing_kind',
            field=models.CharField(
                'Тип прайса', max_length=16, default='fixed',
                choices=[('hair', 'Парикмахерский зал'), ('nails', 'Ногтевой сервис'),
                         ('brow', 'Брови и ресницы'), ('fixed', 'Одна цена')],
            ),
        ),
        migrations.RunPython(migrate_brow_prices, migrations.RunPython.noop),
    ]
