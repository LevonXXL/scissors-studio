"""Server-side Telegram API access through the configured SOCKS proxy."""

import requests
from django.conf import settings


class TelegramAPIError(requests.RequestException):
    """A Bot API failure without a token-bearing URL in the exception text."""

    def __init__(self, error_code=None):
        super().__init__('Telegram Bot API returned an error')
        self.error_code = error_code


def telegram_request(method, *, file_path=None, **kwargs):
    token = settings.TELEGRAM_BOT_TOKEN
    proxy = settings.TELEGRAM_PROXY_URL
    if not token:
        raise ValueError('Не задан TELEGRAM_BOT_TOKEN.')
    if not proxy:
        raise ValueError('Не задан TELEGRAM_PROXY_URL.')
    if not proxy.startswith(('socks5://', 'socks5h://')):
        raise ValueError('TELEGRAM_PROXY_URL должен использовать SOCKS5.')

    if file_path is None:
        url = f'https://api.telegram.org/bot{token}/{method}'
    else:
        url = f'https://api.telegram.org/file/bot{token}/{file_path}'
    request = requests.get if file_path is not None else requests.post
    response = request(url, proxies={'http': proxy, 'https': proxy}, timeout=20, **kwargs)
    response.raise_for_status()
    if file_path is None:
        try:
            payload = response.json()
        except ValueError as exc:
            raise TelegramAPIError() from exc
        if not isinstance(payload, dict) or not payload.get('ok'):
            raise TelegramAPIError(payload.get('error_code') if isinstance(payload, dict) else None)
    return response


def set_telegram_webhook():
    url = settings.TELEGRAM_WEBHOOK_URL
    secret = settings.TELEGRAM_WEBHOOK_SECRET
    if not url.startswith('https://'):
        raise ValueError('TELEGRAM_WEBHOOK_URL должен начинаться с https://.')
    if not secret:
        raise ValueError('Не задан TELEGRAM_WEBHOOK_SECRET.')
    response = telegram_request('setWebhook', json={
        'url': url,
        'secret_token': secret,
        'allowed_updates': ['message'],
    })
    if not response.json().get('ok'):
        raise ValueError('Telegram отклонил настройку webhook.')
