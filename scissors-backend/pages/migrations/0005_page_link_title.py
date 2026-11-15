from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('pages', '0004_pagepicture_filer')]

    operations = [
        migrations.AddField(
            model_name='page',
            name='link_title',
            field=models.CharField(
                blank=True, max_length=255,
                verbose_name='Короткое название для меню и хлебных крошек',
                help_text='Если не заполнено — используется Заголовок.',
            ),
        ),
        migrations.AlterField(
            model_name='page', name='meta_title',
            field=models.CharField(
                blank=True, max_length=255, verbose_name='Заголовок для <title>',
                help_text='Если не заполнено — используется Заголовок.',
            ),
        ),
    ]
