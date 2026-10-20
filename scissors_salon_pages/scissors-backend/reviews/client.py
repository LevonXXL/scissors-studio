from __future__ import annotations

import requests
from django.conf import settings


class RewioError(Exception):
    pass


# Маппинг source_id из Rewio → наши константы из models.SOURCE_*
SOURCE_ID_MAP = {
    1: 1,   # Яндекс.Карты
    2: 2,   # 2ГИС
    3: 3,   # Zoon
    4: 4,   # Google
    5: 5,   # Flamp
}


class RewioClient:
    """Клиент к Rewio API v3.

    Документация: https://api.rewio.ru/v3
    Использует API-ключ из настройки REWIO_API_KEY.
    """

    BASE_URL = 'https://api.rewio.ru/v3'

    def __init__(self, api_key: str | None = None, timeout: int = 30):
        self.api_key = api_key or getattr(settings, 'REWIO_API_KEY', '')
        self.timeout = timeout
        if not self.api_key:
            raise RewioError('REWIO_API_KEY не задан в .env / settings.')

    def _headers(self) -> dict:
        return {'X-API-Key': self.api_key}

    def _request(self, method: str, path: str, **kwargs) -> dict:
        url = f'{self.BASE_URL}/{path.lstrip("/")}'
        kwargs.setdefault('headers', self._headers())
        kwargs.setdefault('timeout', self.timeout)
        try:
            resp = requests.request(method, url, **kwargs)
        except requests.RequestException as exc:
            raise RewioError(f'Сетевая ошибка Rewio: {exc}') from exc

        try:
            data = resp.json()
        except ValueError as exc:
            raise RewioError(f'Rewio вернул не-JSON (код {resp.status_code})') from exc

        if resp.status_code >= 400:
            msg = data.get('error') or data.get('message') or resp.text
            raise RewioError(f'Rewio API ошибка {resp.status_code}: {msg}')

        return data

    # ------------------------------------------------------------------
    # Объекты (1 салон = 1 объект)
    # ------------------------------------------------------------------

    def create_object(self, name: str, links: list[str]) -> dict:
        """Создать объект в Rewio. Возвращает полный ответ с id и link_results."""
        payload = {
            'name': name,
            'links': [{'url': url} for url in links],
        }
        return self._request('POST', 'objects', json=payload)

    # ------------------------------------------------------------------
    # Отзывы
    # ------------------------------------------------------------------

    def get_reviews(
        self,
        object_id: str | int,
        limit: int = 100,
        offset: int = 0,
    ) -> dict:
        """Получить отзывы объекта. Возвращает {"data": [...], "total": N, ...}."""
        return self._request('GET', 'reviews', params={
            'object_id': object_id,
            'limit': limit,
            'offset': offset,
        })
