from django.core.management.base import BaseCommand, CommandError

from search.documents import KIND_CODES, public_sources
from search.manticore import ManticoreError, index_all, index_one


class Command(BaseCommand):
    help = 'Создать одну RT-таблицу и синхронизировать публичный поиск Scissors Studio'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Только посчитать публичные записи, не обращаясь к Manticore')
        parser.add_argument('--type', choices=KIND_CODES, help='Обновить или удалить один документ указанного типа')
        parser.add_argument('--id', type=int, help='ID записи PostgreSQL для --type')

    def handle(self, *args, **options):
        kind, pk = options['type'], options['id']
        if (kind is None) != (pk is None):
            raise CommandError('--type и --id необходимо указывать вместе.')
        if pk is not None and pk < 1:
            raise CommandError('--id должен быть положительным.')
        if options['dry_run']:
            if kind is not None:
                visible = public_sources()[kind].filter(pk=pk).exists()
                self.stdout.write(f'{kind}:{pk}: {"обновить" if visible else "удалить из индекса"}. Manticore не изменён.')
                return
            counts = {source: queryset.count() for source, queryset in public_sources().items()}
            for source, count in counts.items():
                self.stdout.write(f'{source}: {count}')
            self.stdout.write(f'Всего: {sum(counts.values())}. Manticore не изменён.')
            return

        try:
            if kind is not None:
                result = index_one(kind, pk)
                self.stdout.write(f'{kind}:{pk}: {result}')
            else:
                counts = index_all(self.stdout.write)
                self.stdout.write(self.style.SUCCESS(f'Проверено документов: {sum(counts.values())}'))
        except (ManticoreError, ValueError) as exc:
            raise CommandError(str(exc)) from exc
