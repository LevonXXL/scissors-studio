"""
Клиент к "управленческому" API YCLIENTS — данные о компании, сотрудниках,
категориях услуг и услугах. Это ДРУГОЙ набор эндпоинтов, чем
booking.services.YClientsClient (тот — анонимный Booking Widget API для
онлайн-записи, не требует полного доступа). Эти эндпоинты отдают куда
больше полей (финансовые настройки, скрытых сотрудников и т.п.) — то, что
видно в примерах ответов, которые вы прислали (salon-zelenograd.json,
staff.json, services.json, service_categories.json), и это доступно
только с полным User-токеном, не только Partner-токеном.

⚠️ Те же предупреждения, что и в booking/services.py: официальная
документация (developers.yclients.com) закрыта от автоматического
парсинга. Пути ниже (company/{id}, staff/{id}, service_categories/{id},
services/{id}) соответствуют структуре присланных вами примеров ответов,
но переставить их местами/уточнить при первом реальном вызове с боевым
токеном всё равно стоит.
"""

from __future__ import annotations

import requests
from django.conf import settings


class YClientsDataError(Exception):
    pass


class YClientsDataClient:
    BASE_URL = 'https://api.yclients.com/api/v1'

    def __init__(self, partner_token: str | None = None, user_token: str | None = None, timeout: int = 20):
        self.partner_token = partner_token or settings.YCLIENTS_PARTNER_TOKEN
        self.user_token = user_token or settings.YCLIENTS_USER_TOKEN
        self.timeout = timeout
        if not self.user_token:
            raise YClientsDataError(
                'YCLIENTS_USER_TOKEN не задан — управленческий API (в отличие от '
                'анонимного booking-widget) требует полной авторизации.'
            )

    def _headers(self) -> dict:
        return {
            'Authorization': f'Bearer {self.partner_token}, User {self.user_token}',
            'Accept': 'application/vnd.api.v2+json',
            'Content-Type': 'application/json',
        }

    def _get(self, path: str, **params) -> dict:
        url = f'{self.BASE_URL}/{path.lstrip("/")}'
        try:
            response = requests.get(url, headers=self._headers(), params=params, timeout=self.timeout)
        except requests.RequestException as exc:
            raise YClientsDataError(f'Сетевая ошибка при обращении к YCLIENTS: {exc}') from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise YClientsDataError(f'YCLIENTS вернул не-JSON ответ (код {response.status_code})') from exc

        if not data.get('success', True):
            errors = data.get('meta', {}).get('message') or data.get('errors')
            raise YClientsDataError(f'YCLIENTS API вернул ошибку: {errors}')

        return data

    def get_company(self, company_id: str) -> dict:
        """Данные филиала: название, адрес, координаты, режим работы, фото, логотип, описание."""
        return self._get(f'company/{company_id}')['data']

    def get_staff(self, company_id: str) -> list[dict]:
        """Полный список сотрудников филиала, включая скрытых/уволенных (см. поля fired/hidden)."""
        return self._get(f'staff/{company_id}')['data']

    def get_service_categories(self, company_id: str) -> list[dict]:
        """Категории услуг филиала."""
        return self._get(f'service_categories/{company_id}')['data']

    def get_services(self, company_id: str) -> list[dict]:
        """Услуги филиала — каждая с вложенным списком staff[], где могут быть
        переопределения цены/длительности для конкретного мастера."""
        return self._get(f'services/{company_id}')['data']
