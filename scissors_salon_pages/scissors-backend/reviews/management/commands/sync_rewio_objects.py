from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils.dateparse import parse_datetime

from reviews.client import RewioClient, RewioError
from salons.models import Salon


class Command(BaseCommand):
    help = (
        'Создаёт объекты в Rewio для салонов, у которых заполнены ссылки на площадки '
        'и ещё нет rewio_object_id. Один салон = один объект Rewio.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Показать что будет сделано, без реальных изменений.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN — изменения не будут применены'))

        client = RewioClient()

        # Салоны, у которых есть хотя бы одна ссылка и ещё нет rewio_object_id
        salons = Salon.objects.filter(rewio_object_id='').filter(
            Q(yandex_maps_url__gt='') |
            Q(twogis_url__gt='') |
            Q(zoon_url__gt='')
        )

        if not salons.exists():
            self.stdout.write(self.style.SUCCESS('Нет салонов для создания объектов в Rewio.'))
            return

        created = 0
        for salon in salons:
            links = [
                url for url in (
                    salon.yandex_maps_url,
                    salon.twogis_url,
                    salon.zoon_url,
                ) if url
            ]

            self.stdout.write(f'\nСалон «{salon}» ({len(links)} ссылок):')
            for link in links:
                self.stdout.write(f'  • {link}')

            if dry_run:
                self.stdout.write(self.style.WARNING('  [dry-run] Создание объекта пропущено.'))
                created += 1
                continue

            try:
                result = client.create_object(name=salon.name, links=links)
            except RewioError as exc:
                self.stderr.write(self.style.ERROR(f'  Ошибка: {exc}'))
                continue

            object_id = result.get('id')
            if not object_id:
                self.stderr.write(self.style.ERROR(f'  Rewio не вернул id объекта: {result}'))
                continue

            salon.rewio_object_id = str(object_id)
            salon.save(update_fields=['rewio_object_id'])
            created += 1

            self.stdout.write(self.style.SUCCESS(f'  ✓ Создан объект id={object_id}'))

            for lr in result.get('link_results', []):
                status = lr.get('error') or f"ok, link_id={lr.get('link_id')}"
                self.stdout.write(f'    {lr.get("url")} → {status}')

        self.stdout.write(f'\nИтого создано объектов: {created}')
