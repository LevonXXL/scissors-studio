from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('reviews', '0002_alter_review_source'),
    ]

    operations = [
        migrations.AddField(
            model_name='review',
            name='is_published',
            field=models.BooleanField(db_index=True, default=True, verbose_name='Опубликован'),
        ),
    ]
