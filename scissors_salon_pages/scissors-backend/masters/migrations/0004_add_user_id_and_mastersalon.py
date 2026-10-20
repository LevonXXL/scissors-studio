from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('masters', '0003_alter_master_options_remove_master_salon_and_more'),
        ('salons', '__first__'),
    ]

    operations = [
        migrations.AddField(
            model_name='master',
            name='yclients_user_id',
            field=models.CharField(blank=True, max_length=50, null=True, unique=True,
                verbose_name='YCLIENTS user ID',
                help_text='Кросс-салонный идентификатор сотрудника в YCLIENTS.'),
        ),
        migrations.AlterField(
            model_name='master',
            name='yclients_staff_id',
            field=models.CharField(blank=True, max_length=32, null=True, unique=True,
                verbose_name='YCLIENTS staff ID (legacy)',
                help_text='Per-salon staff_id теперь хранится в through-таблице MasterSalon.'),
        ),
        migrations.CreateModel(
            name='MasterSalon',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('yclients_staff_id', models.CharField(blank=True, max_length=32, null=True, unique=True,
                    verbose_name='YCLIENTS staff ID',
                    help_text='Идентификатор привязки мастера к этому салону.')),
                ('master', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='master_salons', to='masters.master')),
                ('salon', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='master_salons', to='salons.salon')),
            ],
            options={
                'verbose_name': 'Привязка мастера к салону',
                'verbose_name_plural': 'Привязки мастеров к салонам',
                'unique_together': {('master', 'salon')},
            },
        ),
    ]