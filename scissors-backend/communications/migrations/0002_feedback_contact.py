from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('communications', '0001_initial')]

    operations = [
        migrations.AlterField(
            model_name='feedbackrequest',
            name='phone',
            field=models.CharField(max_length=254, verbose_name='Телефон или email'),
        ),
    ]
