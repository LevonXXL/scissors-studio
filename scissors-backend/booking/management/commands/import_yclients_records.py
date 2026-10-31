"""Import YCLIENTS calendar records for local salons into the existing Booking table."""

from datetime import datetime, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from django.utils import timezone

from booking.models import Booking
from client_auth.services import normalize_phone
from masters.models import MasterSalon
from salons.models import Salon
from services.models import Service
from sync.client import YClientsDataClient, YClientsDataError
from sync.management.commands.inspect_yclients_records import get_records, numeric_id, parse_date


ATTENDANCE_STATUS = {
    -1: Booking.STATUS_NO_SHOW,
    0: Booking.STATUS_CONFIRMED,
    1: Booking.STATUS_COMPLETED,
    2: Booking.STATUS_CONFIRMED,
}


class RecordImportError(Exception):
    """A record lacks a required calendar field; its ID is safe to report."""


def prepare_record(record, salon, staff_by_id, services_by_id):
    record_id = numeric_id(record.get('id'), 'разбор записи', 200)
    if record.get('company_id') is not None and str(record['company_id']) != str(salon.yclients_company_id):
        raise RecordImportError('ID филиала в записи не совпадает с выбранным салоном.')

    raw_datetime = record.get('datetime')
    if not isinstance(raw_datetime, str):
        raise RecordImportError('Нет даты и времени визита.')
    try:
        start = datetime.fromisoformat(raw_datetime.replace('Z', '+00:00'))
    except ValueError as exc:
        raise RecordImportError('Некорректная дата и время визита.') from exc
    if timezone.is_naive(start):
        raise RecordImportError('Время визита без часового пояса.')

    duration = record.get('seance_length') or record.get('length')
    if isinstance(duration, bool) or not isinstance(duration, (int, str)) or not str(duration).isdigit() or int(duration) <= 0:
        raise RecordImportError('Нет положительной длительности визита.')
    end = start + timedelta(seconds=int(duration))

    staff_id = record.get('staff_id')
    if isinstance(staff_id, bool) or not isinstance(staff_id, (int, str)):
        raise RecordImportError('Не указан ID специалиста.')
    master = staff_by_id.get(str(staff_id))
    if master is None:
        raise RecordImportError('Специалист не найден среди привязок выбранного салона.')

    attendance = record.get('attendance')
    if isinstance(attendance, bool) or not isinstance(attendance, (int, str)) or not str(attendance).lstrip('-').isdigit():
        raise RecordImportError('Неизвестный статус посещения.')
    attendance = int(attendance)
    if attendance not in ATTENDANCE_STATUS:
        raise RecordImportError('Неизвестный статус посещения.')
    deleted = record.get('deleted', False)
    if not isinstance(deleted, bool):
        raise RecordImportError('Некорректный признак удаления.')

    services = record.get('services', [])
    if not isinstance(services, list):
        raise RecordImportError('Некорректный список услуг.')
    titles = []
    for service in services:
        if not isinstance(service, dict):
            raise RecordImportError('Некорректная услуга в записи.')
        title = service.get('title') or services_by_id.get(str(service.get('id')), '')
        if title and not isinstance(title, str):
            raise RecordImportError('Некорректное название услуги.')
        if title:
            titles.append((str(service.get('id') or ''), title))

    client = record.get('client') or {}
    if not isinstance(client, dict):
        raise RecordImportError('Некорректные данные клиента.')
    client_name = client.get('display_name') or client.get('name') or ''
    client_phone = client.get('phone') or ''
    if not isinstance(client_name, str) or len(client_name) > 255:
        raise RecordImportError('Некорректное имя клиента.')
    if not isinstance(client_phone, str) or len(client_phone) > 32:
        raise RecordImportError('Некорректный телефон клиента.')
    if client_phone:
        try:
            client_phone = normalize_phone(client_phone)
        except ValidationError:
            pass  # Preserve foreign or non-mobile numbers instead of inventing a replacement.

    return record_id, {
        'salon': salon,
        'master': master,
        'service_title': ', '.join(title for _, title in sorted(titles)),
        'client_name': client_name,
        'client_phone': client_phone,
        'start_datetime': start,
        'end_datetime': end,
        'status': Booking.STATUS_CANCELLED if deleted else ATTENDANCE_STATUS[attendance],
        'yclients_attendance': attendance,
    }


def changed_fields(booking, values):
    return [name for name, value in values.items() if getattr(booking, name) != value]


class Command(BaseCommand):
    help = 'Импортирует записи YCLIENTS всех локальных салонов; без --apply только предварительный просмотр.'

    def add_arguments(self, parser):
        parser.add_argument('--from-date', help='Начало периода включительно, ГГГГ-ММ-ДД; по умолчанию сегодня.')
        parser.add_argument('--to-date', help='Конец периода включительно, ГГГГ-ММ-ДД; по умолчанию через 6 дней.')
        parser.add_argument('--apply', action='store_true', help='Записать изменения в локальную БД.')

    def handle(self, *args, **options):
        today = timezone.localdate()
        start_date = parse_date(options['from_date'], '--from-date') if options['from_date'] else today
        end_date = parse_date(options['to_date'], '--to-date') if options['to_date'] else start_date + timedelta(days=6)
        if end_date < start_date:
            raise CommandError('--to-date не может быть раньше --from-date.')
        salons = list(Salon.objects.order_by('pk'))
        if not salons:
            raise CommandError('В локальной БД нет салонов.')
        if not settings.YCLIENTS_PARTNER_TOKEN or not settings.YCLIENTS_USER_TOKEN:
            raise CommandError('Не настроен доступ к YCLIENTS.')
        try:
            client = YClientsDataClient()
        except YClientsDataError as exc:
            raise CommandError('Не удалось подготовить клиент YCLIENTS.') from exc

        self.stdout.write(
            f'Филиалов из БД: {len(salons)}; период {start_date} — {end_date}; '
            f'режим: {"ЗАПИСЬ В БД" if options["apply"] else "ПРЕДВАРИТЕЛЬНЫЙ ПРОСМОТР (БД не меняется)"}.'
        )
        totals = {'created': 0, 'updated': 0, 'unchanged': 0, 'skipped': 0}
        failed_branches = 0
        for salon in salons:
            try:
                counts = self.import_salon(salon, client, start_date, end_date, options['apply'])
            except CommandError as exc:
                failed_branches += 1
                self.stdout.write(f'Салон #{salon.pk}: {exc} Перехожу к следующему салону.')
                self.stdout.flush()
                continue
            except Exception as exc:
                failed_branches += 1
                self.stdout.write(
                    f'Салон #{salon.pk}: ошибка обработки ({type(exc).__name__}). '
                    'Перехожу к следующему салону.'
                )
                self.stdout.flush()
                continue
            for name in totals:
                totals[name] += counts[name]

        self.stdout.write(
            f'Итого по {len(salons)} салонам: создано {totals["created"]}, '
            f'обновлено {totals["updated"]}, без изменений {totals["unchanged"]}, '
            f'пропущено записей {totals["skipped"]}, салонов с ошибкой {failed_branches}.'
        )
        self.stdout.flush()
        if failed_branches or totals['skipped']:
            raise CommandError('Не все записи обработаны; причины указаны выше.')

    def import_salon(self, salon, client, start_date, end_date, apply):
        company_id = str(salon.yclients_company_id or '')
        if not company_id.isdigit():
            raise CommandError('У салона нет корректного yclients_company_id.')
        records = get_records(client, company_id, start_date, end_date)
        staff_by_id = {
            str(link.yclients_staff_id): link.master
            for link in MasterSalon.objects.filter(salon=salon).select_related('master')
            if link.yclients_staff_id
        }
        services_by_id = dict(
            Service.objects.filter(salon_offers__salon=salon).exclude(yclients_service_id__isnull=True).values_list('yclients_service_id', 'title')
        )
        existing_by_id = {
            booking.yclients_record_id: booking
            for booking in Booking.objects.filter(yclients_record_id__in=[str(record['id']) for record in records])
        }

        self.stdout.write(
            f'Салон #{salon.pk} ({salon.name}), company_id={company_id}; '
            f'период {start_date} — {end_date}; получено {len(records)} записей.'
        )
        counts = {'created': 0, 'updated': 0, 'unchanged': 0, 'skipped': 0}
        for record in records:
            record_id = str(record['id'])
            try:
                record_id, values = prepare_record(record, salon, staff_by_id, services_by_id)
                existing = existing_by_id.get(record_id)
                if existing and existing.salon_id != salon.pk:
                    raise RecordImportError('ID записи уже принадлежит другому салону в локальной БД.')
                if existing:
                    fields = changed_fields(existing, values)
                    if not fields:
                        counts['unchanged'] += 1
                        continue
                    action = 'updated'
                else:
                    action = 'created'

                if apply:
                    with transaction.atomic():
                        locked = Booking.objects.select_for_update().filter(yclients_record_id=record_id).first()
                        if locked and locked.salon_id != salon.pk:
                            raise RecordImportError('ID записи уже принадлежит другому салону в локальной БД.')
                        if locked:
                            fields = changed_fields(locked, values)
                            for field in fields:
                                setattr(locked, field, values[field])
                            if fields:
                                locked.save(update_fields=fields)
                                action = 'updated'
                            else:
                                action = 'unchanged'
                        else:
                            Booking.objects.create(yclients_record_id=record_id, **values)
                counts[action] += 1
            except (RecordImportError, CommandError) as exc:
                counts['skipped'] += 1
                self.stdout.write(f'  id={record_id}: пропущена: {exc}')
            except DatabaseError as exc:
                counts['skipped'] += 1
                self.stdout.write(f'  id={record_id}: ошибка БД ({type(exc).__name__}); запись пропущена.')
            except Exception as exc:
                counts['skipped'] += 1
                self.stdout.write(f'  id={record_id}: ошибка обработки ({type(exc).__name__}); запись пропущена.')

        self.stdout.write(
            f'Салон #{salon.pk}: создано {counts["created"]}, обновлено {counts["updated"]}, '
            f'без изменений {counts["unchanged"]}, пропущено {counts["skipped"]}.'
        )
        self.stdout.flush()
        return counts
