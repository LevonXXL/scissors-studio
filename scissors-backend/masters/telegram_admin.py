"""Superuser-only Telegram webhook setup in Django admin."""

import requests
from django.conf import settings
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .telegram_api import set_telegram_webhook


@require_http_methods(['GET', 'POST'])
def telegram_webhook_settings(request):
    if not request.user.is_superuser:
        raise PermissionDenied

    if request.method == 'POST':
        try:
            set_telegram_webhook()
        except (ValueError, requests.RequestException):
            messages.error(request, 'Не удалось зарегистрировать webhook. Проверьте настройки и доступность прокси.')
        else:
            messages.success(request, 'Telegram webhook зарегистрирован.')
        return redirect(reverse('admin-telegram-webhook-settings'))

    return render(request, 'masters/admin_telegram_webhook.html', {
        **admin.site.each_context(request),
        'title': 'Telegram webhook',
        'webhook_url': settings.TELEGRAM_WEBHOOK_URL,
        'token_configured': bool(settings.TELEGRAM_BOT_TOKEN),
        'secret_configured': bool(settings.TELEGRAM_WEBHOOK_SECRET),
        'proxy_configured': bool(settings.TELEGRAM_PROXY_URL),
    })
