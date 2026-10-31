"""Read-only, privacy-conscious inspection of YCLIENTS records for local salons."""

import re
from datetime import date, datetime, timedelta

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from salons.models import Salon
from sync.client import YClientsDataClient, YClientsDataError


PAGE_SIZE = 200
MAX_PAGES = 100
DATE_PATTERN = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}\Z')
ID_PATTERN = re.compile(r'[0-9]+\Z')


def fail(stage, status, message):
    raise CommandError(f'Этап «{stage}»: HTTP {status if status is not None else "—"}. {message}')


def parse_date(value, name):
    if not DATE_PATTERN.fullmatch(value):
        fail('параметры', None, f'{name}: нужна дата в формате ГГГГ-ММ-ДД.')
    try:
        return date.fromisoformat(value)
    except ValueError:
        fail('параметры', None, f'{name}: некорректная календарная дата.')


def numeric_id(value, stage, status):
    if isinstance(value, bool) or not isinstance(value, (int, str)) or not ID_PATTERN.fullmatch(str(value)):
        fail(stage, status, 'YCLIENTS вернул недопустимый числовой ID.')
    return str(value)


def get_records_page(client, company_id, start_date, end_date, page):
    stage = f'получение записей, страница {page}'
    try:
        response = requests.get(
            f'{client.BASE_URL}/records/{company_id}',
            headers=client._headers(),
            params={
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'count': PAGE_SIZE,
                'page': page,
            },
            timeout=client.timeout,
            allow_redirects=False,
        )
    except requests.RequestException:
        fail(stage, None, 'Сетевая ошибка при обращении к YCLIENTS; проверьте соединение.')

    status = response.status_code
    if status in (401, 403):
        fail(stage, status, 'Доступ к записям запрещён. Проверьте права User-токена на просмотр записей этого филиала.')
    if not 200 <= status < 300:
        fail(stage, status, 'YCLIENTS отклонил запрос; проверьте филиал, период и права доступа.')
    try:
        payload = response.json()
    except ValueError:
        fail(stage, status, 'YCLIENTS вернул невалидный JSON.')
    if not isinstance(payload, dict) or payload.get('success', True) is not True:
        fail(stage, status, 'YCLIENTS сообщил об ошибке; проверьте параметры и права на просмотр записей.')
    if not isinstance(payload.get('data'), list):
        fail(stage, status, 'YCLIENTS вернул неожиданный формат списка записей.')
    meta = payload.get('meta')
    if meta is None:
        meta = {}
    if not isinstance(meta, dict):
        fail(stage, status, 'YCLIENTS вернул некорректные метаданные.')
    total = meta.get('total_count')
    if total is not None and (isinstance(total, bool) or not isinstance(total, int) or total < 0):
        fail(stage, status, 'YCLIENTS вернул некорректное количество записей.')
    return payload['data'], total, status


def get_records(client, company_id, start_date, end_date):
    records = []
    seen_ids = set()
    for page in range(1, MAX_PAGES + 1):
        batch, total, status = get_records_page(client, company_id, start_date, end_date, page)
        stage = f'разбор записей, страница {page}'
        if len(batch) > PAGE_SIZE:
            fail(stage, status, 'YCLIENTS вернул больше записей, чем запрошено.')
        for record in batch:
            if not isinstance(record, dict):
                fail(stage, status, 'YCLIENTS вернул запись неожиданного формата.')
            record_id = numeric_id(record.get('id'), stage, status)
            if record_id in seen_ids:
                fail(stage, status, 'YCLIENTS повторил ID записи; список может быть неполным.')
            seen_ids.add(record_id)
            records.append(record)
        if total is not None:
            if len(records) > total:
                fail(stage, status, 'Количество записей превышает значение в метаданных YCLIENTS.')
            if len(records) == total:
                return records
            if not batch:
                fail(stage, status, 'Пустая страница до конца списка YCLIENTS.')
        elif len(batch) < PAGE_SIZE:
            return records
    fail('постраничное чтение', None, f'Достигнут предел {MAX_PAGES} страниц; список не выведен как полный.')


def display_datetime(record):
    value = record.get('datetime') or record.get('date')
    if value is None:
        return '—'
    if not isinstance(value, str):
        fail('разбор записи', 200, 'YCLIENTS вернул неожиданный формат даты визита.')
    try:
        if DATE_PATTERN.fullmatch(value):
            return f'{value} (время не указано)'
        return datetime.fromisoformat(value.replace('Z', '+00:00')).isoformat(sep=' ', timespec='minutes')
    except ValueError:
        fail('разбор записи', 200, 'YCLIENTS вернул некорректную дату визита.')


def display_record(record, company_id):
    stage = 'разбор записи'
    record_id = numeric_id(record.get('id'), stage, 200)
    staff_id = record.get('staff_id')
    if staff_id is None and isinstance(record.get('staff'), dict):
        staff_id = record['staff'].get('id')
    staff = 'не назначен' if staff_id in (None, 0, '0', '') else numeric_id(staff_id, stage, 200)

    services = record.get('services', [])
    if not isinstance(services, list):
        fail(stage, 200, 'YCLIENTS вернул неожиданный формат услуг.')
    service_ids = []
    for service in services:
        service_id = service.get('id') if isinstance(service, dict) else service
        service_ids.append(numeric_id(service_id, stage, 200))

    attendance = record.get('attendance', record.get('visit_attendance'))
    if attendance is not None and (isinstance(attendance, bool) or not str(attendance).lstrip('-').isdigit()):
        fail(stage, 200, 'YCLIENTS вернул неожиданный формат статуса визита.')
    duration = record.get('seance_length')
    if duration is None:
        duration = record.get('length')
    if duration is not None and (isinstance(duration, bool) or not str(duration).isdigit()):
        fail(stage, 200, 'YCLIENTS вернул неожиданную длительность записи.')
    deleted = record.get('deleted')
    if deleted is not None and deleted not in (True, False, 0, 1):
        fail(stage, 200, 'YCLIENTS вернул неожиданный признак удаления.')

    return (
        f'id={record_id}; филиал={company_id}; дата={display_datetime(record)}; '
        f'статус визита={attendance if attendance is not None else "—"}; '
        f'удалена={"да" if deleted else "нет" if deleted is not None else "—"}; '
        f'специалист={staff}; услуги={", ".join(service_ids) if service_ids else "нет"}; '
        f'длительность={str(duration) + " с" if duration is not None else "—"}'
    )


class Command(BaseCommand):
    help = 'Только чтение: показывает записи YCLIENTS за период для всех филиалов из БД.'

    def add_arguments(self, parser):
        parser.add_argument('--from-date', help='Начало периода включительно, ГГГГ-ММ-ДД; по умолчанию сегодня.')
        parser.add_argument('--to-date', help='Конец периода включительно, ГГГГ-ММ-ДД; по умолчанию через 6 дней.')

    def handle(self, *args, **options):
        today = timezone.localdate()
        start_date = parse_date(options['from_date'], '--from-date') if options['from_date'] else today
        end_date = parse_date(options['to_date'], '--to-date') if options['to_date'] else start_date + timedelta(days=6)
        if end_date < start_date:
            fail('параметры', None, '--to-date не может быть раньше --from-date.')
        salons = list(
            Salon.objects.exclude(yclients_company_id__isnull=True)
            .exclude(yclients_company_id='')
            .order_by('pk')
        )
        if not salons:
            fail('выбор филиалов', None, 'В БД нет филиалов с yclients_company_id.')
        if not settings.YCLIENTS_PARTNER_TOKEN or not settings.YCLIENTS_USER_TOKEN:
            fail('авторизация', None, 'Нужны существующие настройки YCLIENTS_PARTNER_TOKEN и YCLIENTS_USER_TOKEN.')
        try:
            client = YClientsDataClient()
        except YClientsDataError:
            fail('авторизация', None, 'Не удалось подготовить клиент YCLIENTS; проверьте настройки доступа.')

        self.stdout.write(
            f'Только чтение YCLIENTS: филиалов из БД — {len(salons)}; '
            f'период {start_date} — {end_date} включительно; page=1, count={PAGE_SIZE}.'
        )
        self.stdout.flush()
        total_records = 0
        failed_branches = 0
        for salon in salons:
            company_id = str(salon.yclients_company_id)
            try:
                if not ID_PATTERN.fullmatch(company_id):
                    fail('выбор филиала', None, 'Некорректный yclients_company_id в локальной БД.')
                records = get_records(client, company_id, start_date, end_date)
                lines = [display_record(record, company_id) for record in records]
            except CommandError as exc:
                failed_branches += 1
                self.stdout.write(f'Филиал #{salon.pk}: {exc} Перехожу к следующему филиалу.')
                self.stdout.flush()
                continue
            except Exception as exc:
                failed_branches += 1
                self.stdout.write(
                    f'Филиал #{salon.pk}: непредвиденная ошибка обработки ({type(exc).__name__}). '
                    'Перехожу к следующему филиалу.'
                )
                self.stdout.flush()
                continue

            self.stdout.write(f'Филиал #{salon.pk} ({salon.name}), company_id={company_id}: {len(lines)} записей.')
            for line in lines:
                self.stdout.write(f'  {line}')
            total_records += len(lines)
            self.stdout.flush()

        self.stdout.write(
            f'Проверено филиалов: {len(salons)}; с ошибками: {failed_branches}. '
            f'Всего записей из доступных филиалов: {total_records}.'
        )
        if failed_branches:
            raise CommandError(f'Не удалось прочитать записи {failed_branches} из {len(salons)} филиалов.')
