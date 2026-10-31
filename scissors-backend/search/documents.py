"""Public Scissors Studio records represented in one Manticore table."""

import html
import re
from html.parser import HTMLParser

from masters.models import Master
from pages.models import Page
from salons.models import Salon
from services.models import Service, ServiceCategory


KIND_CODES = {'page': 1, 'master': 2, 'salon': 3, 'category': 4, 'service': 5}
REDIRECT_PATHS = {'services', 'price-list', 'price-list_zelenograd', 'policy', 'moscow', 'zelenograd'}


class _PlainTextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skipped_tag = None

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.skipped_tag = tag

    def handle_endtag(self, tag):
        if tag == self.skipped_tag:
            self.skipped_tag = None

    def handle_data(self, data):
        if self.skipped_tag is None:
            self.parts.append(data)


def document_id(kind, pk):
    """Collision-free type prefix plus a 56-bit database primary key."""
    if kind not in KIND_CODES or not 0 < pk < 2**56:
        raise ValueError(f'Недопустимый тип или ID документа: {kind}:{pk}')
    return (KIND_CODES[kind] << 56) | pk


def plain_text(value):
    parser = _PlainTextParser()
    parser.feed(str(value or ''))
    return re.sub(r'\s+', ' ', html.unescape(' '.join(parser.parts))).strip()


def public_url(path):
    return '/' + (path or '').strip('/')


def public_sources():
    """The same visibility rules as public pages, catalogues and team cards."""
    return {
        'page': (Page.objects.filter(
            is_published=True, service__isnull=True, service_category__isnull=True,
            master__isnull=True, salon__isnull=True,
        ).exclude(url_path__in=REDIRECT_PATHS).order_by('pk')),
        'master': (Master.objects.filter(
            is_active=True, is_system=False, is_booking_placeholder=False,
            yclients_user_id__isnull=False, page__is_published=True,
            master_salons__salon__is_active=True,
        ).exclude(yclients_user_id='').select_related('page').distinct().order_by('pk')),
        'salon': (Salon.objects.filter(is_active=True).exclude(slug='')
                  .select_related('page').order_by('pk')),
        'category': (ServiceCategory.objects.filter(
            is_active=True, page__is_published=True, services__is_active=True,
            services__page__is_published=True,
            services__salon_offers__is_active=True,
            services__salon_offers__salon__is_active=True,
        ).select_related('page').distinct().order_by('pk')),
        'service': (Service.objects.filter(
            is_active=True, category__is_active=True, page__is_published=True,
            salon_offers__is_active=True, salon_offers__salon__is_active=True,
        ).select_related('page', 'category').distinct().order_by('pk')),
    }


def as_document(kind, obj, generation):
    page = getattr(obj, 'page', None) if kind != 'page' else obj

    if kind == 'page':
        title = obj.title
        content = plain_text(obj.content)
        terms = [obj.meta_title, obj.meta_description]
        url = public_url(obj.url_path)
    elif kind == 'master':
        title = obj.name
        content = plain_text(' '.join((obj.bio, page.content if page else '')))
        terms = [obj.get_price_level_display(),
                 page.meta_description if page else '']
        url = public_url(page.url_path)
    elif kind == 'salon':
        title = obj.name
        content = plain_text(' '.join((obj.address, obj.description, page.content if page else '')))
        terms = [obj.working_hours, page.meta_description if page else '']
        url = f'/salons/{obj.slug}'
    elif kind == 'category':
        title = obj.title
        content = plain_text(page.content)
        terms = [page.meta_description]
        url = public_url(page.url_path)
    elif kind == 'service':
        title = obj.title
        content = plain_text(' '.join((obj.description, obj.conditions, page.content)))
        terms = [obj.category.title, obj.group_title, obj.subgroup_title,
                 page.meta_description]
        url = public_url(page.url_path)
    else:
        raise ValueError(f'Неизвестный тип документа: {kind}')

    return {
        'id': document_id(kind, obj.pk),
        'title': plain_text(title),
        'content': content,
        'search_text': plain_text(' '.join((title, content, *terms))),
        'type': kind,
        'url': url,
        'project': 'scissors',
        'generation': generation,
    }
