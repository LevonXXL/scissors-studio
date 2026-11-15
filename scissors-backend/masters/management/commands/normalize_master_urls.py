"""Give the current master the unsuffixed URL left behind by old YCLIENTS duplicates."""

import re

from django.core.management.base import BaseCommand
from django.db import transaction

from core_utils.slugify_ru import slugify_ru
from masters.constants import TEST_MASTER_SLUG_PREFIX
from masters.models import Master
from pages.models import Page
from salons.models import Salon
from services.models import Service, ServiceCategory


SUFFIX = re.compile(r'-\d+$')


class Command(BaseCommand):
    help = 'Preview or normalize master slugs and their Page paths.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Apply changes (default: preview only).')

    def handle(self, *args, **options):
        changed = skipped = 0
        masters = (Master.objects.filter(page__isnull=False,
                                         is_system=False, is_booking_placeholder=False)
                   .exclude(slug__startswith=TEST_MASTER_SLUG_PREFIX)
                   .select_related('page').order_by('pk'))
        for master in masters:
            base = SUFFIX.sub('', master.slug)
            if base == master.slug or base != slugify_ru(master.name):
                continue
            page = master.page
            if page.parent_id is None or page.parent.url_path != 'team':
                self.stdout.write(f'SKIP {master.pk}: page is outside team')
                skipped += 1
                continue
            if Master.objects.filter(slug=base).exclude(pk=master.pk).exists():
                self.stdout.write(f'SKIP {master.pk}: master slug {base} is occupied')
                skipped += 1
                continue
            target = Page.objects.filter(url_path=f'team/{base}').exclude(pk=page.pk).first()
            if target and (target.get_children().exists() or
                           Master.objects.filter(page=target).exists()):
                # Keep any page that has a real owner or descendants untouched.
                self.stdout.write(f'SKIP {master.pk}: target page has an owner or children')
                skipped += 1
                continue
            if target:
                if (Salon.objects.filter(page=target).exists() or
                        Service.objects.filter(page=target).exists() or
                        ServiceCategory.objects.filter(page=target).exists()):
                    self.stdout.write(f'SKIP {master.pk}: target page belongs to another model')
                    skipped += 1
                    continue
            self.stdout.write(f'{master.pk}: {page.url_path} -> team/{base}' +
                              (f' (archive unowned Page {target.pk})' if target else ''))
            if options['apply']:
                with transaction.atomic():
                    if target:
                        target.url = f'legacy-{target.pk}-{base}'[:255]
                        target.is_published = False
                        target.save(update_fields=['url', 'is_published'])
                    master.slug = base
                    master.save(update_fields=['slug'])
                    page.url = base
                    page.save(update_fields=['url'])
            changed += 1
        self.stdout.write(f'{"Applied" if options["apply"] else "Would change"}: {changed}; skipped: {skipped}')
