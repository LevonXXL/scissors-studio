from django.db import migrations
from django.db.models import Q


ORIGINAL_TITLE = (
    'Акупунктура тела — расслабление и снятие мышечного напряжения | '
    'воздействие тонкими иглами на зоны напряжения'
)
ORIGINAL_DESCRIPTION = (
    'Эстетическая процедура с использованием тонких игл для локальной работы с зонами '
    'мышечного напряжения. Помогает расслабить напряжённые участки тела, уменьшить '
    'ощущение зажатости и вернуть чувство лёгкости и комфорта.'
)
PAGE_PATH = (
    'uslugi/cosmetology/akupunktura-tela-rasslablenie-i-snyatie-myshechnogo-'
    'napryazheniya-vozdeystvie-tonkimi-iglami-na-zony-napryazheniya'
)
DRAFT_DESCRIPTION = (
    'Акупунктура тела предполагает введение тонких игл через кожу. Возможность проведения '
    'процедуры определяется после оценки противопоказаний и подтверждения условий её оказания '
    'и квалификации исполнителя.'
)
DRAFT_CONTENT = (
    '<h2>О процедуре</h2>'
    '<p>Акупунктура тела предполагает введение тонких игл через кожу. Это инвазивная '
    'процедура, а не разновидность обычного массажа. Результат индивидуален.</p>'
    '<h2>Перед проведением</h2>'
    '<p>До оказания услуги необходимо подтвердить условия её проведения и квалификацию '
    'исполнителя, оценить противопоказания и обсудить с клиентом возможные риски. '
    'До завершения этой проверки услуга не публикуется и запись на неё недоступна.</p>'
)
DRAFT_META_DESCRIPTION = (
    'Акупунктура тела — процедура с введением тонких игл через кожу. Публикация и запись '
    'приостановлены до проверки условий оказания, квалификации исполнителя и противопоказаний.'
)


def hold_acupuncture(apps, schema_editor):
    Service = apps.get_model('services', 'Service')
    ServiceSalon = apps.get_model('services', 'ServiceSalon')
    Page = apps.get_model('pages', 'Page')

    services = Service.objects.filter(category__code='cosmetology').filter(
        Q(title=ORIGINAL_TITLE) | Q(page__url_path=PAGE_PATH)
    ).distinct()
    page_ids = set(Page.objects.filter(url_path=PAGE_PATH).values_list('pk', flat=True))
    for service in services:
        updates = {'is_active': False}
        if service.description == ORIGINAL_DESCRIPTION:
            updates['description'] = DRAFT_DESCRIPTION
        Service.objects.filter(pk=service.pk).update(**updates)
        ServiceSalon.objects.filter(service_id=service.pk).update(is_active=False)
        if service.page_id:
            page_ids.add(service.page_id)

    for page in Page.objects.filter(pk__in=page_ids):
        updates = {'is_published': False}
        if page.title == ORIGINAL_TITLE:
            updates['title'] = 'Акупунктура тела'
        if not page.content.strip():
            updates['content'] = DRAFT_CONTENT
        if not page.meta_description.strip():
            updates['meta_description'] = DRAFT_META_DESCRIPTION
        Page.objects.filter(pk=page.pk).update(**updates)


class Migration(migrations.Migration):
    dependencies = [
        ('services', '0005_servicecategory_image'),
        ('pages', '0004_pagepicture_filer'),
    ]

    operations = [migrations.RunPython(hold_acupuncture, migrations.RunPython.noop)]
