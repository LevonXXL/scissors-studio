"""
Тонкий клиент к Booking API YCLIENTS.

⚠️ ВАЖНО ПЕРЕД ИСПОЛЬЗОВАНИЕМ В ПРОДЕ:
Официальная документация (developers.yclients.com) рендерится через JS и
закрыта от автоматического парсинга, поэтому пути эндпоинтов ниже собраны
по нескольким неофициальным враппера (Python/PHP) и подтверждённому формату
авторизации. Формат авторизации подтверждён:

    Authorization: Bearer <partner_token>, User <user_token>

Partner-токен выдаётся после регистрации в маркетплейсе интеграций YCLIENTS
(developers.yclients.com), User-токен — отдельно, методом auth, для действий
от имени конкретного пользователя аккаунта YCLIENTS.

ПЕРЕД ПОДКЛЮЧЕНИЕМ РЕАЛЬНЫХ ДАННЫХ: зайти в актуальную документацию с уже
полученным partner-токеном и свериться, что пути ниже (book_services,
book_staff, book_dates, book_times, book_record) и структура ответов не
изменились — для анонимного бронирования (без входа клиента) может
хватать только Bearer partner_token, без User-токена, но это тоже стоит
перепроверить по факту получения доступа.
"""

from __future__ import annotations

import requests
from django.conf import settings


class YClientsError(Exception):
    """Ошибка при обращении к YCLIENTS API — сетевая или бизнес-логическая (errors в ответе)."""


class YClientsClient:
    BASE_URL = 'https://api.yclients.com/api/v1'

    def __init__(self, partner_token: str | None = None, user_token: str | None = None, timeout: int = 15):
        self.partner_token = partner_token or settings.YCLIENTS_PARTNER_TOKEN
        self.user_token = user_token or getattr(settings, 'YCLIENTS_USER_TOKEN', '')
        self.timeout = timeout

    def _headers(self) -> dict:
        auth = f'Bearer {self.partner_token}'
        if self.user_token:
            auth += f', User {self.user_token}'
        return {
            'Authorization': auth,
            'Accept': 'application/vnd.api.v2+json',
            'Content-Type': 'application/json',
        }

    def _request(self, method: str, path: str, **kwargs) -> dict:
        url = f'{self.BASE_URL}/{path.lstrip("/")}'
        try:
            response = requests.request(method, url, headers=self._headers(), timeout=self.timeout, **kwargs)
        except requests.RequestException as exc:
            raise YClientsError(f'Сетевая ошибка при обращении к YCLIENTS: {exc}') from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise YClientsError(f'YCLIENTS вернул не-JSON ответ (код {response.status_code})') from exc

        if not data.get('success', True):
            errors = data.get('meta', {}).get('message') or data.get('errors')
            raise YClientsError(f'YCLIENTS API вернул ошибку: {errors}')

        return data

    # --- Публичные методы, нужные для бронирования без редиректа на YCLIENTS ---

    def get_services(self, company_id: str, staff_id: str | None = None) -> list[dict]:
        """Список услуг филиала (опционально — только у конкретного мастера).

        ⚠️ У разных версий этого эндпоинта в сторонних враппербиблиотеках
        встречались два разных формата ответа: `data` как плоский список,
        и `data` как словарь с вложенным ключом `services`. Обрабатываем
        оба, но при первом реальном вызове с боевым токеном стоит
        залогировать сырой ответ и свериться, какой формат актуален сейчас.
        """
        params = {'staff_id': staff_id} if staff_id else {}
        data = self._request('GET', f'book_services/{company_id}', params=params)
        payload = data.get('data', [])
        if isinstance(payload, dict):
            return payload.get('services', [])
        return payload

    def get_staff(self, company_id: str, service_ids: list[str] | None = None) -> list[dict]:
        """Список мастеров, оказывающих указанные услуги в этом филиале."""
        params = {}
        if service_ids:
            params['service_ids[]'] = service_ids
        data = self._request('GET', f'book_staff/{company_id}', params=params)
        return data.get('data', [])

    def get_available_dates(self, company_id: str, staff_id: str, service_ids: list[str]) -> list[str]:
        """Даты, на которые у мастера есть свободные слоты для этих услуг."""
        params = {'staff_id': staff_id, 'service_ids[]': service_ids}
        data = self._request('GET', f'book_dates/{company_id}', params=params)
        payload = data.get('data', [])
        if isinstance(payload, dict):
            return payload.get('booking_dates', [])
        return payload

    def get_available_times(self, company_id: str, staff_id: str, date: str) -> list[dict]:
        """Свободные тайм-слоты мастера на конкретную дату (YYYY-MM-DD)."""
        data = self._request('GET', f'book_times/{company_id}/{staff_id}', params={'date': date})
        return data.get('data', [])

    def create_booking(
        self, company_id: str, *, fullname: str, phone: str,
        staff_id: str, service_ids: list[str], start_datetime_iso: str,
        email: str = '', comment: str = '',
    ) -> dict:
        """
        Создаёт запись. Возвращает YCLIENTS record_id/record_hash — их
        обязательно сохранить в своей модели Booking, они нужны для
        последующей отмены/проверки статуса записи.
        """
        payload = {
            'phone': phone,
            'fullname': fullname,
            'email': email,
            'appointments': [{
                'id': 1,
                'services': [int(sid) for sid in service_ids],
                'staff_id': int(staff_id),
                'datetime': start_datetime_iso,
                'comment': comment,
            }],
        }
        data = self._request('POST', f'book_record/{company_id}', json=payload)
        records = data.get('data', [])
        if not records:
            raise YClientsError('YCLIENTS не вернул данные о созданной записи.')
        return records[0]  # {'id': ..., 'record_id': ..., 'record_hash': ...}
