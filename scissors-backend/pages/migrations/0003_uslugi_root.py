from django.db import migrations
from django.db.models import Max


def root_page(apps, schema_editor):
    Page = apps.get_model('pages', 'Page')
    if not Page.objects.filter(url_path='uslugi').exists():
        tree_id = (Page.objects.aggregate(value=Max('tree_id'))['value'] or 0) + 1
        Page.objects.create(title='Услуги и цены', url='uslugi', url_path='uslugi',
                            content='', meta_title='Услуги и цены — Scissors Studio',
                            tree_id=tree_id, lft=1, rght=2, level=0)


class Migration(migrations.Migration):
    dependencies = [('pages', '0002_alter_page_url')]
    operations = [migrations.RunPython(root_page, migrations.RunPython.noop)]
