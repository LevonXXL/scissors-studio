"""
Разовая команда для очистки дублей мастеров после перехода на yclients_user_id.

Что делает:
1. Обращается к YCLIENTS API каждого салона, получает маппинг staff_id → user_id.
2. Обновляет поле yclients_user_id у существующих мастеров (только у "старшего"
   в каждой группе дубликатов, чтобы не violate unique constraint).
3. Находит дубликаты (несколько записей Master с одним yclients_user_id).
4. Для каждой группы дубликатов: оставляет запись с наименьшим id,
   переносит MasterSalon (с per-salon staff_id) и ServiceStaffPrice, удаляет лишние.

Использование:
    python manage.py dedup_masters
    python manage.py dedup_masters --dry-run
"""

from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count, Min

from masters.models import Master, MasterSalon
from salons.models import Salon
from services.models import ServiceStaffPrice
from sync.client import YClientsDataClient, YClientsDataError


class Command(BaseCommand):
    help = 'Подтягивает yclients_user_id из API и сливает дубликаты мастеров.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Показать что будет сделано, без реальных изменений.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN — изменения не будут применены'))

        # 1. Build staff_id → user_id mapping from YCLIENTS API
        staff_to_user: dict[str, str] = {}
        client = YClientsDataClient()

        salons = Salon.objects.exclude(yclients_company_id='').exclude(
            yclients_company_id__isnull=True,
        )

        for salon in salons:
            self.stdout.write(f'Запрашиваю staff для «{salon}» (company_id={salon.yclients_company_id})...')
            try:
                staff_list = client.get_staff(salon.yclients_company_id)
                for entry in staff_list:
                    staff_id = str(entry['id'])
                    user_id = str(entry['user_id']) if entry.get('user_id') else None
                    if user_id:
                        staff_to_user[staff_id] = user_id
            except YClientsDataError as exc:
                self.stderr.write(self.style.ERROR(f'  Ошибка: {exc}'))

        self.stdout.write(f'\nПолучен маппинг staff_id → user_id: {len(staff_to_user)} записей')

        # 2. Resolve target user_id for each master, keeping only the lowest id per group
        #    to avoid UniqueViolation on yclients_user_id.
        candidates = Master.objects.filter(
            yclients_user_id__isnull=True, yclients_staff_id__isnull=False,
        )

        # Group by target user_id → list of master ids
        user_id_to_master_ids: dict[str, list[int]] = defaultdict(list)
        master_to_user_id: dict[int, str] = {}

        for master in candidates:
            user_id = staff_to_user.get(master.yclients_staff_id)
            if user_id:
                user_id_to_master_ids[user_id].append(master.id)
                master_to_user_id[master.id] = user_id

        # Also collect masters that ALREADY have yclients_user_id set
        already_set = Master.objects.filter(yclients_user_id__isnull=False)
        for master in already_set:
            user_id_to_master_ids[master.yclients_user_id].append(master.id)

        # For each user_id group, only the master with lowest id gets the user_id
        updated = 0
        skipped_dup = 0
        for user_id, master_ids in user_id_to_master_ids.items():
            master_ids.sort()
            keeper_id = master_ids[0]

            # Check if keeper already has the correct user_id
            keeper = Master.objects.get(id=keeper_id)
            if keeper.yclients_user_id != user_id:
                if not dry_run:
                    keeper.yclients_user_id = user_id
                    keeper.save(update_fields=['yclients_user_id'])
                updated += 1
                self.stdout.write(
                    f'  {keeper.name} (id={keeper.id}): '
                    f'staff_id={keeper.yclients_staff_id} → user_id={user_id}'
                )
            else:
                self.stdout.write(
                    f'  {keeper.name} (id={keeper.id}): уже имеет user_id={user_id} (ok)'
                )

            if len(master_ids) > 1:
                dup_ids = master_ids[1:]
                skipped_dup += len(dup_ids)
                for did in dup_ids:
                    dup = Master.objects.get(id=did)
                    self.stdout.write(
                        f'    ↑ дубликат id={did} "{dup.name}" '
                        f'(staff_id={dup.yclients_staff_id}) — будет слит'
                    )

        self.stdout.write(f'\nОбновлено yclients_user_id: {updated} мастеров')
        self.stdout.write(f'Дубликатов к сливу: {skipped_dup}')

        # 3. Find and merge duplicates (masters sharing the same yclients_user_id)
        duplicate_user_ids = (
            Master.objects
            .filter(yclients_user_id__isnull=False)
            .values('yclients_user_id')
            .annotate(cnt=Count('id'))
            .filter(cnt__gt=1)
        )

        if not duplicate_user_ids:
            self.stdout.write(self.style.SUCCESS('\nДубликатов не найдено.'))
            return

        total_merged = 0
        for dup in duplicate_user_ids:
            user_id = dup['yclients_user_id']
            masters = list(
                Master.objects.filter(yclients_user_id=user_id).order_by('id')
            )
            keep = masters[0]
            rest = masters[1:]

            self.stdout.write(f'\nДубликаты для user_id={user_id} ({keep.name}):')

            if not dry_run:
                with transaction.atomic():
                    for m in rest:
                        self.stdout.write(f'  Сливаем id={m.id} "{m.name}" → id={keep.id}')

                        # Migrate MasterSalon entries (with per-salon yclients_staff_id)
                        for ms in MasterSalon.objects.filter(master=m):
                            MasterSalon.objects.update_or_create(
                                master=keep, salon=ms.salon,
                                defaults={'yclients_staff_id': ms.yclients_staff_id},
                            )

                        # Migrate ServiceStaffPrice
                        ServiceStaffPrice.objects.filter(master=m).update(master=keep)

                        # Delete duplicate
                        m.delete()

                total_merged += len(rest)
            else:
                for m in rest:
                    self.stdout.write(f'  [dry-run] Сливаем id={m.id} "{m.name}" → id={keep.id}')
                total_merged += len(rest)

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f'\nDRY RUN: было бы слито {total_merged} дубликатов. '
                'Запустите без --dry-run для применения.'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'\nГотово: слито {total_merged} дубликатов.'
            ))
            self.stdout.write('Теперь запустите sync_yclients для обновления данных и заполнения through-таблицы.')
