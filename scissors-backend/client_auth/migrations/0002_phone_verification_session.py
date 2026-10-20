from datetime import timedelta

from django.db import migrations, models
import django.db.models.deletion


def attach_legacy_codes(apps, schema_editor):
    database = schema_editor.connection.alias
    Code = apps.get_model('client_auth', 'PhoneCode')
    Session = apps.get_model('client_auth', 'PhoneVerificationSession')
    for code in Code.objects.using(database).all().iterator():
        session = Session.objects.using(database).create(
            phone=code.phone,
            started_at=code.requested_at,
            expires_at=code.requested_at + timedelta(minutes=30),
            last_requested_at=code.requested_at,
            attempts=code.attempts,
            completed_at=code.consumed_at,
        )
        code.session_id = session.pk
        code.save(using=database, update_fields=['session'])


class Migration(migrations.Migration):
    dependencies = [('client_auth', '0001_initial')]

    operations = [
        migrations.CreateModel(
            name='PhoneVerificationSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('phone', models.CharField(max_length=12, unique=True)),
                ('started_at', models.DateTimeField()),
                ('expires_at', models.DateTimeField()),
                ('last_requested_at', models.DateTimeField()),
                ('attempts', models.PositiveSmallIntegerField(default=0)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
            ],
        ),
        migrations.AlterField(
            model_name='phonecode',
            name='phone',
            field=models.CharField(max_length=12),
        ),
        migrations.AddField(
            model_name='phonecode',
            name='session',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='codes', to='client_auth.phoneverificationsession'),
        ),
        migrations.RunPython(attach_legacy_codes),
        migrations.AlterField(
            model_name='phonecode',
            name='session',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='codes', to='client_auth.phoneverificationsession'),
        ),
        migrations.RemoveField(model_name='phonecode', name='attempts'),
    ]
