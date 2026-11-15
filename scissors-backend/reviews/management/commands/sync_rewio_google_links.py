from django.core.management.base import BaseCommand

from reviews.client import RewioClient, RewioError
from salons.models import Salon


class Command(BaseCommand):
    help = 'Добавляет ссылки Google Maps к существующим объектам салонов в REWIO.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Применить изменения в REWIO.')
        parser.add_argument('--salon-id', type=int, help='Обработать один салон.')

    def handle(self, *args, **options):
        client = RewioClient()
        salons = Salon.objects.exclude(google_maps_url='').exclude(rewio_object_id='')
        if options['salon_id']:
            salons = salons.filter(pk=options['salon_id'])

        for salon in salons:
            try:
                obj = client.get_object(salon.rewio_object_id)
            except RewioError as exc:
                self.stderr.write(self.style.ERROR(f'{salon}: {exc}'))
                continue

            if any(link.get('source_id') == 2 for link in obj.get('links', [])):
                self.stdout.write(f'{salon}: Google Maps уже подключены.')
                continue

            if not options['apply']:
                self.stdout.write(f'{salon}: будет добавлена {salon.google_maps_url}')
                continue

            try:
                result = client.add_links(salon.rewio_object_id, [salon.google_maps_url])
            except RewioError as exc:
                self.stderr.write(self.style.ERROR(f'{salon}: {exc}'))
                continue

            link_results = result.get('link_results', [])
            if not link_results or any(item.get('error') for item in link_results):
                self.stderr.write(self.style.ERROR(f'{salon}: REWIO отклонил ссылку: {link_results or result}'))
                continue
            self.stdout.write(self.style.SUCCESS(f'{salon}: ссылка Google Maps добавлена.'))
