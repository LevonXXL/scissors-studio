"""Use the first Filer photo on a service page as the service catalogue photo."""

from django.core.management.base import BaseCommand
from django.db import transaction

from services.models import Service


class Command(BaseCommand):
    help = ('Привязать к услугам первое фото Filer с их страниц. '
            'Уже заданные изображения услуг не изменяются.')

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true',
                            help='Сохранить привязки; без флага только показать план.')

    def handle(self, *args, **options):
        services = Service.objects.filter(is_active=True, image__isnull=True,
                                           page__isnull=False).select_related('page').prefetch_related(
                                               'page__pictures').order_by('id')
        ready = 0
        without_photo = 0

        with transaction.atomic():
            for service in services:
                picture = next((item for item in service.page.pictures.all() if item.image_id), None)
                if picture is None:
                    without_photo += 1
                    continue

                ready += 1
                self.stdout.write(f'#{service.pk} {service.title}: Filer #{picture.image_id} '
                                  f'(страница #{service.page_id})')
                if options['apply']:
                    service.image_id = picture.image_id
                    service.save(update_fields=['image'])

        verb = 'Привязано' if options['apply'] else 'Готово к привязке'
        self.stdout.write(self.style.SUCCESS(
            f'{verb}: {ready}; без фото Filer на странице: {without_photo}.'
        ))
