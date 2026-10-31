from django.db import migrations
from django.utils.html import format_html


def remove_copied_bio(apps, schema_editor):
    Master = apps.get_model('masters', 'Master')
    Page = apps.get_model('pages', 'Page')
    db = schema_editor.connection.alias

    for master in Master.objects.using(db).exclude(page_id__isnull=True).exclude(bio='').iterator():
        copied_content = format_html('<p>{}</p>', master.bio)
        Page.objects.using(db).filter(pk=master.page_id, content=copied_content).update(content='')


class Migration(migrations.Migration):
    dependencies = [
        ('masters', '0018_remove_master_category_remove_master_specialization_and_more'),
    ]

    operations = [
        migrations.RunPython(remove_copied_bio, migrations.RunPython.noop),
    ]
