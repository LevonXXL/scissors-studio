from django.core.management.base import BaseCommand, CommandError

from salons.models import Salon
from sync.client import YClientsDataError
from sync.sync_service import sync_salon_full


class Command(BaseCommand):
    help = 'Синхронизирует салоны, мастеров, категории и услуги с YCLIENTS.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--salon-id', type=int, default=None,
            help='ID конкретного салона (наш, не yclients_company_id). Без флага — синхронизируются все салоны с заполненным yclients_company_id.',
        )

    def handle(self, *args, **options):
        salon_id = options.get('salon_id')

        if salon_id:
            try:
                salons = [Salon.objects.get(pk=salon_id)]
            except Salon.DoesNotExist as exc:
                raise CommandError(f'Салон с id={salon_id} не найден.') from exc
        else:
            salons = list(Salon.objects.exclude(yclients_company_id='').exclude(yclients_company_id__isnull=True))

        if not salons:
            self.stdout.write(self.style.WARNING(
                'Нет салонов с заполненным yclients_company_id — синхронизировать нечего.'
            ))
            return

        for salon in salons:
            self.stdout.write(f'Синхронизирую «{salon}» (company_id={salon.yclients_company_id})...')
            try:
                sync_salon_full(salon)
            except YClientsDataError as exc:
                self.stderr.write(self.style.ERROR(f'  Ошибка синхронизации «{salon}»: {exc}'))
                continue
            self.stdout.write(self.style.SUCCESS(f'  Готово: {salon}'))

        self.stdout.write(self.style.SUCCESS('Синхронизация завершена.'))
