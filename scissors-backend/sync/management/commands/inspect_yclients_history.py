"""Read-only inspection of a client's YCLIENTS records across configured salons."""

import requests
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from client_auth.services import normalize_phone
from salons.models import Salon
from sync.client import YClientsDataClient, YClientsDataError


PAGE_SIZE = 200


def get_page(client, resource, company_id, **params):
    url = f'{client.BASE_URL}/{resource}/{company_id}'
    try:
        response = requests.get(
            url, headers=client._headers(), params=params, timeout=client.timeout,
            allow_redirects=False,
        )
    except requests.RequestException as exc:
        raise CommandError('Не удалось связаться с YCLIENTS; запрос прерван.') from exc

    if not 200 <= response.status_code < 300:
        body = response.text
        for token in (client.partner_token, client.user_token):
            if token:
                body = body.replace(token, '[REDACTED]')
        raise CommandError(
            f'YCLIENTS отклонил GET {resource}: HTTP {response.status_code}. '
            f'Тело ответа: {body}'
        )
    try:
        payload = response.json()
    except ValueError as exc:
        raise CommandError(f'YCLIENTS вернул некорректный JSON для {resource}.') from exc
    if not isinstance(payload, dict) or payload.get('success', True) is not True:
        raise CommandError(f'YCLIENTS вернул ошибку или некорректный ответ для {resource}.')
    if not isinstance(payload.get('data'), list):
        raise CommandError(f'YCLIENTS вернул неожиданный формат списка {resource}.')
    return payload


def get_all_pages(client, resource, company_id, *, start_page=0, **params):
    items = []
    seen_ids = set()
    page = start_page
    while True:
        payload = get_page(client, resource, company_id, **params, count=PAGE_SIZE, page=page)
        batch = payload['data']
        meta = payload.get('meta')
        if meta is not None and not isinstance(meta, dict):
            raise CommandError(f'YCLIENTS вернул некорректные метаданные {resource}.')
        total = (meta or {}).get('total_count')
        if total is not None and (not isinstance(total, int) or isinstance(total, bool) or total < 0):
            raise CommandError(f'YCLIENTS вернул некорректное количество {resource}.')

        for item in batch:
            if not isinstance(item, dict) or not isinstance(item.get('id'), (int, str)) or not str(item['id']).isdigit():
                raise CommandError(f'YCLIENTS вернул запись {resource} без допустимого ID.')
            item_id = str(item['id'])
            if item_id in seen_ids:
                raise CommandError(f'YCLIENTS повторил страницу {resource}; история может быть неполной.')
            seen_ids.add(item_id)
            items.append(item)

        if total is not None:
            if len(items) >= total:
                if len(items) != total:
                    raise CommandError(f'Количество {resource} не совпадает с метаданными YCLIENTS.')
                break
            if not batch:
                raise CommandError(f'YCLIENTS вернул пустую страницу до конца списка {resource}.')
        elif len(batch) < PAGE_SIZE:
            break
        page += 1
    return items


class Command(BaseCommand):
    help = 'Только чтение: показывает карточку клиента и историю записей YCLIENTS.'

    def add_arguments(self, parser):
        parser.add_argument('--phone', required=True, help='Телефон клиента, например 79991234567.')

    def handle(self, *args, **options):
        try:
            phone = normalize_phone(options['phone'])[1:]
        except ValidationError as exc:
            raise CommandError('Укажите корректный российский мобильный номер.') from exc

        if not settings.YCLIENTS_PARTNER_TOKEN or not settings.YCLIENTS_USER_TOKEN:
            raise CommandError('Для чтения YCLIENTS нужны YCLIENTS_PARTNER_TOKEN и YCLIENTS_USER_TOKEN.')
        try:
            client = YClientsDataClient()
        except YClientsDataError as exc:
            raise CommandError('Не удалось подготовить клиент YCLIENTS.') from exc

        company_ids = list(
            Salon.objects.exclude(yclients_company_id__isnull=True)
            .exclude(yclients_company_id='')
            .order_by('pk').values_list('yclients_company_id', flat=True)
        )
        if not company_ids:
            raise CommandError('Нет салонов с заполненным yclients_company_id.')

        cards = []
        for company_id in company_ids:
            if not company_id.isdecimal():
                raise CommandError('У салона указан некорректный yclients_company_id.')
            for card in get_all_pages(client, 'clients', company_id, phone=phone):
                card_phone = ''.join(ch for ch in str(card.get('phone', '')) if ch.isdigit())
                if card_phone.startswith('8') and len(card_phone) == 11:
                    card_phone = '7' + card_phone[1:]
                elif card_phone.startswith('9') and len(card_phone) == 10:
                    card_phone = '7' + card_phone
                if card_phone != phone:
                    raise CommandError('YCLIENTS вернул карточку с другим телефоном; поиск прерван.')
                cards.append((company_id, card['id']))

        self.stdout.write(f'Найдено карточек: {len(cards)}')
        for company_id, card_id in cards:
            self.stdout.write(f'  company_id={company_id}, client_id={card_id}')
        if len(cards) != 1:
            if len(cards) > 1:
                self.stdout.write('Найдено несколько карточек; история не запрашивалась.')
            return

        company_id, client_id = cards[0]
        records = get_all_pages(
            client, 'records', company_id, client_id=client_id, start_page=0,
        )
        for record in records:
            record_client = record.get('client')
            linked_id = record.get('client_id')
            if linked_id is None and isinstance(record_client, dict):
                linked_id = record_client.get('id')
            if str(linked_id) != str(client_id):
                raise CommandError('YCLIENTS вернул запись без подтверждённой связи с найденной карточкой.')
        self.stdout.write(f'Получено записей: {len(records)}')
        for record in records:
            services = record.get('services', [])
            if not isinstance(services, list) or any(not isinstance(service, dict) for service in services):
                raise CommandError('YCLIENTS вернул неожиданный формат услуг в записи.')
            service_ids = [service.get('id') for service in services]
            date = record.get('datetime') or record.get('date') or '—'
            status = record.get('attendance', record.get('visit_attendance', '—'))
            self.stdout.write(
                f"  id={record['id']}, дата={date}, статус={status}, "
                f"staff_id={record.get('staff_id', '—')}, услуги={service_ids}"
            )
