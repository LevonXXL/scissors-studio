"""Create catalogue Page links without touching edited Page content or URLs."""
from django.db import transaction

from core_utils.slugify_ru import slugify_ru
from pages.models import Page

INTRO = {
    'hair': 'Услуги для волос от мастеров-парикмахеров.',
    'nails': 'Маникюр, педикюр и уход для ногтей.',
    'browlashes': 'Услуги для бровей и ресниц.',
    'cosmetology': 'Уход за лицом и телом.',
    'epilation': 'Удаление волос: воск и лазер.',
    'forman': 'Парикмахерские услуги для мужчин.',
}


@transaction.atomic
def ensure_catalog_pages(categories, services=None):
    selected_ids = {service.pk for service in services} if services is not None else None
    root = Page.objects.filter(url_path='uslugi').first()
    if root is None:
        root = Page.objects.create(title='Услуги и цены', url='uslugi', content='')
    for category in categories:
        if category.page_id:
            page = category.page
            if page.parent_id != root.pk:
                page.parent = root
                page.save(update_fields=['parent'])
        else:
            slug = category.code or slugify_ru(category.title)[:90]
            page = Page.objects.filter(parent=root, url=slug).first()
            if page and hasattr(page, 'service_category'):
                raise ValueError(f'Адрес категории {slug} занят.')
            if not page:
                page = Page.objects.create(parent=root, url=slug, title=category.title,
                                           meta_description=INTRO.get(category.code, ''))
            category.page = page
            category.save(update_fields=['page'])
        service_rows = category.services.filter(is_active=True)
        if selected_ids is not None:
            service_rows = service_rows.filter(pk__in=selected_ids)
        for service in service_rows:
            if service.page_id:
                if service.page.parent_id != page.pk:
                    service.page.parent = page
                    service.page.save(update_fields=['parent'])
                continue
            base = slugify_ru(service.title)[:190] or 'service'
            slug = base
            suffix = 2
            candidate = Page.objects.filter(parent=page, url=slug).first()
            while candidate and hasattr(candidate, 'service'):
                slug = f'{base[:180]}-{suffix}'
                suffix += 1
                candidate = Page.objects.filter(parent=page, url=slug).first()
            service.page = candidate or Page.objects.create(parent=page, url=slug,
                                                            title=service.title[:255])
            service.save(update_fields=['page'])
