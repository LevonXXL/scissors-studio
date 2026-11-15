"""Authenticated webhook entry points for the staff bots."""

import hmac
import json
import logging

import requests
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .bot import (download_max_photo, download_telegram_photo, handle_message,
                  send_message)
from .models import MasterMessengerAccount, ProcessedMessengerUpdate


logger = logging.getLogger(__name__)


def _process(platform, update_id, user_id, text, photo, caption, downloader):
    if not update_id or not user_id:
        return JsonResponse({'ok': True})
    update, created = ProcessedMessengerUpdate.objects.get_or_create(
        platform=platform, update_id=str(update_id))
    if not created:
        return JsonResponse({'ok': True})
    logger.info('Получено обновление бота %s: update_id=%s', platform, update_id)
    try:
        reply = handle_message(platform, str(user_id), text, photo, caption, downloader)
    except (ValueError, requests.RequestException) as exc:
        reply = str(exc) if isinstance(exc, ValueError) else 'Не удалось получить фотографию. Попробуйте ещё раз.'
    except Exception:
        update.delete()
        logger.exception('Не удалось обработать сообщение бота %s', platform)
        return JsonResponse({'ok': False}, status=500)
    try:
        send_message(platform, str(user_id), reply, source_text=text)
    except (requests.RequestException, ValueError) as exc:
        status_code = getattr(getattr(exc, 'response', None), 'status_code', None)
        error_code = getattr(exc, 'error_code', None)
        logger.warning('Не удалось отправить ответ бота %s: update_id=%s, тип=%s, HTTP=%s, API=%s',
                       platform, update_id, type(exc).__name__, status_code, error_code)
    else:
        logger.info('Ответ бота %s отправлен: update_id=%s', platform, update_id)
    return JsonResponse({'ok': True})


@csrf_exempt
@require_POST
def telegram_webhook(request):
    secret = settings.TELEGRAM_WEBHOOK_SECRET
    if not settings.TELEGRAM_BOT_TOKEN or not secret:
        return JsonResponse({'ok': False}, status=503)
    if not hmac.compare_digest(request.headers.get('X-Telegram-Bot-Api-Secret-Token', ''), secret):
        return JsonResponse({'ok': False}, status=403)
    try:
        update = json.loads(request.body)
    except (ValueError, TypeError):
        return JsonResponse({'ok': False}, status=400)
    if not isinstance(update, dict):
        return JsonResponse({'ok': False}, status=400)
    message = update.get('message') or {}
    if message.get('chat', {}).get('type') != 'private':
        return JsonResponse({'ok': True})
    photos = message.get('photo') or []
    photo = max(photos, key=lambda item: item.get('file_size', 0)).get('file_id') if photos else None
    return _process(MasterMessengerAccount.PLATFORM_TELEGRAM, update.get('update_id'),
                    message.get('from', {}).get('id'), message.get('text') or '', photo,
                    message.get('caption') or '', download_telegram_photo)


@csrf_exempt
@require_POST
def max_webhook(request):
    secret = settings.MAX_WEBHOOK_SECRET
    if not settings.MAX_BOT_TOKEN or not secret:
        return JsonResponse({'ok': False}, status=503)
    if not hmac.compare_digest(request.headers.get('X-Max-Bot-Api-Secret', ''), secret):
        return JsonResponse({'ok': False}, status=403)
    try:
        update = json.loads(request.body)
    except (ValueError, TypeError):
        return JsonResponse({'ok': False}, status=400)
    if not isinstance(update, dict):
        return JsonResponse({'ok': False}, status=400)
    if update.get('update_type') != 'message_created':
        return JsonResponse({'ok': True})
    message = update.get('message') or {}
    if message.get('recipient', {}).get('chat_type') != 'dialog':
        return JsonResponse({'ok': True})
    body = message.get('body') or {}
    attachment = next((item for item in body.get('attachments') or []
                       if item.get('type') == 'image' and item.get('payload', {}).get('url')), None)
    photo = attachment['payload']['url'] if attachment else None
    return _process(MasterMessengerAccount.PLATFORM_MAX, body.get('mid'),
                    message.get('sender', {}).get('user_id'), body.get('text') or '', photo,
                    body.get('text') or '', download_max_photo)
