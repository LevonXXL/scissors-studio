"""Safely merge one legacy Master duplicate into an identified Master."""

from django.core.management.base import BaseCommand, CommandError

from sync.master_dedup import UnsafeMasterMerge, reconcile_master_duplicate


class Command(BaseCommand):
    help = 'Проверить и объединить один старый дубль мастера с записью, имеющей YCLIENTS user_id.'

    def add_arguments(self, parser):
        parser.add_argument('--canonical-id', type=int, required=True, help='ID мастера с корректным YCLIENTS user_id.')
        parser.add_argument('--duplicate-id', type=int, required=True, help='ID старой записи с пустыми YCLIENTS ID.')
        parser.add_argument('--apply', action='store_true', help='Применить проверенное объединение; без флага — только просмотр.')

    def handle(self, *args, **options):
        try:
            summary = reconcile_master_duplicate(
                options['canonical_id'], options['duplicate_id'], apply=options['apply'],
            )
        except UnsafeMasterMerge as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            f'Основная запись {summary["canonical_id"]}; дубль {summary["duplicate_id"]}. '
            f'Привязок: {summary["links"]}, пересекающихся цен: {summary["overlapping_prices"]} '
            f'(различаются: {summary["conflicting_prices"]}), '
            f'переносимых цен: {summary["moving_prices"]}, бронирований: {summary["bookings"]}.'
        )
        if options['apply']:
            page_result = ('страница перенесена основной записи.' if summary['transferred_page']
                           else 'отдельная страница дубля сохранена без публикации.')
            self.stdout.write(self.style.SUCCESS(f'Дубль объединён; {page_result}'))
        else:
            self.stdout.write('Проверка завершена без изменений. Для применения добавьте --apply.')
