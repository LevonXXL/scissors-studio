"""Fill missing master price levels using current YCLIENTS staff positions."""

from collections import defaultdict

from django.core.management.base import BaseCommand, CommandError

from masters.models import Master, MasterSalon
from salons.models import Salon
from services.price_levels import LEVEL_LABELS
from sync.client import YClientsDataClient, YClientsDataError
from sync.identifiers import yclients_id
from sync.master_price_levels import inferred_price_level, is_founder


class Command(BaseCommand):
    help = ('Показывает возможное заполнение пустых уровней мастеров по должностям YCLIENTS. '
            'Изменения вносит только с --apply.')

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Сохранить однозначно определённые уровни.')

    def handle(self, *args, **options):
        salons = list(Salon.objects.exclude(yclients_company_id__isnull=True)
                      .exclude(yclients_company_id='').order_by('pk'))
        if not salons:
            self.stdout.write('Нет салонов с YCLIENTS company ID.')
            return

        try:
            client = YClientsDataClient()
            staff_by_salon = [(salon, client.get_staff(salon.yclients_company_id))
                              for salon in salons]
        except YClientsDataError as exc:
            raise CommandError(f'Не удалось получить сотрудников YCLIENTS: {exc}') from exc

        evidence = defaultdict(list)
        unmatched = 0
        for salon, staff_list in staff_by_salon:
            for entry in staff_list:
                staff_id = yclients_id(entry.get('id'))
                user_id = yclients_id(entry.get('user_id'))
                if not staff_id or not user_id:
                    continue
                by_user = Master.objects.filter(yclients_user_id=user_id).first()
                link = (MasterSalon.objects.select_related('master').filter(
                    salon=salon, yclients_staff_id=staff_id).first())
                by_link = link.master if link else None
                if by_user and by_link and by_user.pk != by_link.pk:
                    unmatched += 1
                    continue
                master = by_user or by_link
                if master is None or master.is_system or master.is_booking_placeholder:
                    unmatched += 1
                    continue
                if yclients_id(master.yclients_user_id) not in (None, user_id):
                    unmatched += 1
                    continue
                evidence[master.pk].append((salon.name, inferred_price_level(entry)))

        planned = 0
        applied = 0
        conflicting = 0
        existing = 0
        unknown = 0
        protected = 0
        for master in Master.objects.filter(pk__in=evidence).order_by('pk'):
            if is_founder(master):
                protected += 1
                continue
            if master.price_level:
                existing += 1
                continue
            levels = {level for _, level in evidence[master.pk] if level}
            if len(levels) > 1:
                conflicting += 1
                self.stdout.write(f'Пропуск #{master.pk} {master.name}: разные уровни по салонам.')
                continue
            if not levels:
                unknown += 1
                continue
            level = levels.pop()
            planned += 1
            self.stdout.write(f'#{master.pk} {master.name}: {LEVEL_LABELS[level]} ({level})')
            if options['apply']:
                # A concurrent edit in admin always wins over the backfill.
                applied += Master.objects.filter(pk=master.pk, price_level='').update(price_level=level)

        self.stdout.write(
            f'Кандидатов: {planned}; сохранено: {applied}; уже задано: {existing}; '
            f'конфликт: {conflicting}; нет точной должности: {unknown}; '
            f'Михаил Стець: {protected}; не сопоставлены по ID: {unmatched}.'
        )
        if not options['apply']:
            self.stdout.write('Проверочный режим. Для сохранения повторите с --apply.')
