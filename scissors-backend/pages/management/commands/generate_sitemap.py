"""Generate the public frontend sitemap from the current database."""

from pathlib import Path
from urllib.parse import quote, urlsplit
from xml.etree import ElementTree

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from masters.models import Master
from pages.models import Page
from salons.models import Salon
from services.models import Service, ServiceCategory


SITEMAP_NS = 'http://www.sitemaps.org/schemas/sitemap/0.9'
DEFAULT_OUTPUT = settings.BASE_DIR.parent / 'scissors-backend' / 'staticfiles' / 'sitemap.xml'


def public_paths():
    """Return canonical paths that the frontend can serve publicly."""
    excluded_page_ids = set(
        Salon.objects.filter(is_active=False, page__isnull=False).values_list('page_id', flat=True)
    )
    excluded_page_ids.update(
        Master.objects.filter(Q(is_active=False) | Q(yclients_user_id__isnull=True) |
                              Q(is_booking_placeholder=True))
        .filter(page__isnull=False).values_list('page_id', flat=True)
    )
    excluded_page_ids.update(
        ServiceCategory.objects.filter(is_active=False)
        .filter(page__isnull=False).values_list('page_id', flat=True)
    )
    excluded_page_ids.update(
        Service.objects.filter(
            Q(is_active=False) | Q(category__is_active=False)
        ).filter(page__isnull=False).values_list('page_id', flat=True)
    )

    # Home and price list have dedicated routes even if their Page records are absent.
    paths = {'', 'uslugi'}
    for page_id, path in Page.objects.filter(is_published=True).values_list('id', 'url_path'):
        if page_id not in excluded_page_ids and path not in {
            'login', 'policy', 'moscow', 'zelenograd', 'vacancy',
        } and not (path == 'services' or path.startswith('services/')):
            paths.add(path)

    # SalonPage is a dedicated route and remains available without a Page record.
    paths.update(
        f'salons/{slug}' for slug in Salon.objects.filter(is_active=True)
        .exclude(slug='').values_list('slug', flat=True)
    )
    return sorted(paths, key=lambda path: (path != '', path))


def sitemap_xml(base_url, paths):
    ElementTree.register_namespace('', SITEMAP_NS)
    root = ElementTree.Element(f'{{{SITEMAP_NS}}}urlset')
    for path in paths:
        url = ElementTree.SubElement(root, f'{{{SITEMAP_NS}}}url')
        location = ElementTree.SubElement(url, f'{{{SITEMAP_NS}}}loc')
        location.text = f'{base_url}/{quote(path, safe="/")}'
    ElementTree.indent(root, space='  ')
    return ElementTree.tostring(root, encoding='utf-8', xml_declaration=True)


class Command(BaseCommand):
    help = 'Создать sitemap.xml для публичных страниц frontend.'

    def add_arguments(self, parser):
        parser.add_argument('--base-url', default=settings.SITE_URL, help='Публичный адрес сайта.')
        parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT, help='Путь к sitemap.xml.')

    def handle(self, *args, **options):
        base_url = options['base_url'].rstrip('/')
        parsed = urlsplit(base_url)
        if parsed.scheme not in {'http', 'https'} or not parsed.netloc or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
            raise CommandError('--base-url должен быть абсолютным адресом корня сайта без пути.')

        output = options['output']
        if not output.parent.is_dir():
            raise CommandError(f'Каталог для sitemap.xml не найден: {output.parent}')

        paths = public_paths()
        output.write_bytes(sitemap_xml(base_url, paths))
        self.stdout.write(self.style.SUCCESS(f'Создан {output}: {len(paths)} адресов.'))
