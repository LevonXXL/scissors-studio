"""Shared staff-bot workflow for Telegram and MAX private chats."""

import hashlib
import io
import ipaddress
import logging
import secrets
import socket
from datetime import timedelta
from urllib.parse import quote, urlparse

import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone
from django.utils.html import escape, strip_tags
from filer.models import Image as FilerImage
from PIL import Image, UnidentifiedImageError

from pages.models import PagePicture
from services.models import Service, ServiceStaffPrice

from .models import (MasterMessengerAccount, MasterMessengerPairingCode,
                     MasterServiceWorkPhoto)
from .telegram_api import telegram_request


logger = logging.getLogger(__name__)
MAX_IMAGE_BYTES = 10_000_000
LINK_BUTTON_TEXT = 'Подключить профиль'


def pairing_digest(code):
    return hashlib.sha256(code.encode('utf-8')).hexdigest()


def create_pairing_code(master, *, validity=timedelta(minutes=15)):
    code = secrets.token_urlsafe(18)
    MasterMessengerPairingCode.objects.filter(master=master, used_at__isnull=True).delete()
    MasterMessengerPairingCode.objects.create(
        master=master, digest=pairing_digest(code),
        expires_at=timezone.now() + validity,
    )
    return code


def _download(url, headers=None):
    response = requests.get(url, headers=headers, timeout=20, stream=True, allow_redirects=False)
    response.raise_for_status()
    if response.is_redirect:
        raise ValueError('Мессенджер вернул перенаправление вместо фотографии.')
    data = bytearray()
    for chunk in response.iter_content(65536):
        data.extend(chunk)
        if len(data) > MAX_IMAGE_BYTES:
            raise ValueError('Фотография должна быть не больше 10 МБ.')
    return bytes(data)


def download_telegram_photo(file_id):
    response = telegram_request('getFile', json={'file_id': file_id})
    payload = response.json()
    if not payload.get('ok'):
        raise ValueError('Telegram не отдал фотографию.')
    path = payload.get('result', {}).get('file_path', '')
    if not path or path.startswith('/') or '..' in path.split('/'):
        raise ValueError('Telegram вернул неверный путь фотографии.')
    response = telegram_request('', file_path=quote(path, safe='/'),
                                stream=True, allow_redirects=False)
    try:
        if response.is_redirect:
            raise ValueError('Telegram вернул перенаправление вместо фотографии.')
        data = bytearray()
        for chunk in response.iter_content(65536):
            data.extend(chunk)
            if len(data) > MAX_IMAGE_BYTES:
                raise ValueError('Фотография должна быть не больше 10 МБ.')
        return bytes(data)
    finally:
        response.close()


def download_max_photo(url):
    parsed = urlparse(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('MAX вернул неверную ссылку на фотографию.')
    # The MAX image URL is supplied by its webhook, but still must not reach private networks.
    try:
        addresses = {ipaddress.ip_address(info[4][0])
                     for info in socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)}
    except (OSError, ValueError) as exc:
        raise ValueError('Не удалось проверить адрес фотографии MAX.') from exc
    if not addresses or any(not address.is_global for address in addresses):
        raise ValueError('Недопустимый адрес фотографии MAX.')
    return _download(url)


def validated_image(data):
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise ValueError('Фотография должна быть не больше 10 МБ.')
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.width * image.height > 40_000_000:
                raise ValueError('Фотография слишком большого разрешения.')
            image.verify()
            format_name = image.format
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError('Файл не является поддерживаемым изображением.') from exc
    extension = {'JPEG': 'jpg', 'PNG': 'png', 'WEBP': 'webp', 'GIF': 'gif'}.get(format_name)
    if not extension:
        raise ValueError('Поддерживаются JPEG, PNG, WEBP и GIF.')
    return ContentFile(data, name=f'work-{secrets.token_hex(8)}.{extension}')


def _save_photo(master, action, service_id, data, caption):
    file = validated_image(data)
    with transaction.atomic():
        if action == 'work_photo':
            service = Service.objects.filter(pk=service_id, is_active=True).first()
            if not service or not ServiceStaffPrice.objects.filter(master=master, service=service).exists():
                raise ValueError('Эта услуга больше не назначена вам.')
        elif action == 'gallery_photo' and not master.page_id:
            raise ValueError('У профиля пока нет страницы для общей галереи.')
        image = FilerImage.objects.create(
            original_filename=file.name, name=f'{master.name}: работа'[:255], file=file,
            owner=master.user,
        )
        if action == 'profile_photo':
            master.photo = image
            master.save(update_fields=['photo'])
            return 'Фото профиля обновлено.'
        if action == 'gallery_photo':
            position = (PagePicture.objects.filter(page_id=master.page_id)
                        .aggregate(value=Max('position'))['value'] or 0) + 1
            PagePicture.objects.create(page_id=master.page_id, image=image,
                                       alt=caption or f'Работа мастера {master.name}',
                                       position=position)
            return 'Фото добавлено в общую галерею.'
        photo = MasterServiceWorkPhoto(master=master, service=service, image=image,
                                       caption=caption[:255])
        photo.full_clean()
        photo.save()
        return f'Фото добавлено к услуге «{service.title}».'


def _link_account(platform, external_user_id, code):
    if not code:
        return 'Откройте свою карточку в админке, получите код и отправьте /link КОД.'
    with transaction.atomic():
        pairing = (MasterMessengerPairingCode.objects.select_for_update()
                   .filter(digest=pairing_digest(code), used_at__isnull=True,
                           expires_at__gt=timezone.now()).select_related('master').first())
        if pairing is None:
            return 'Код недействителен или истёк. Получите новый в админке.'
        if MasterMessengerAccount.objects.filter(platform=platform, master=pairing.master).exists():
            return 'У этого мастера уже подключён аккаунт в данном мессенджере.'
        if MasterMessengerAccount.objects.filter(platform=platform,
                                                 external_user_id=external_user_id).exists():
            return 'Этот аккаунт уже подключён к другому мастеру.'
        try:
            MasterMessengerAccount.objects.create(
                platform=platform, master=pairing.master, external_user_id=external_user_id)
        except IntegrityError:
            return 'Аккаунт уже подключён. Проверьте профиль в админке.'
        pairing.used_at = timezone.now()
        pairing.save(update_fields=['used_at'])
    return f'Готово, подключён профиль «{pairing.master.name}». Отправьте /help.'


def handle_message(platform, external_user_id, text='', photo=None, caption='', download=None):
    """Return a plain text reply; all edits are scoped to the paired master."""
    text = (text or '').strip()
    command, _, argument = text.partition(' ')
    account = (MasterMessengerAccount.objects.select_related('master', 'pending_service')
               .filter(platform=platform, external_user_id=external_user_id).first())
    if command in ('/link', '/start'):
        if command == '/start' and not argument:
            if account:
                return ('Профиль подключён. Откройте мини-приложение кнопкой ниже.'
                        if platform == MasterMessengerAccount.PLATFORM_TELEGRAM
                        else 'Профиль подключён. Отправьте /help.')
            return 'Бот мастеров Scissors Studio. Для подключения отправьте /link КОД из своей карточки в админке.'
        return _link_account(platform, external_user_id, argument.strip())

    if account is None:
        if platform == MasterMessengerAccount.PLATFORM_TELEGRAM and text == LINK_BUTTON_TEXT:
            return 'Введите код подключения из карточки мастера ответом на это сообщение.'
        if platform == MasterMessengerAccount.PLATFORM_TELEGRAM and text and not text.startswith('/'):
            return _link_account(platform, external_user_id, text)
        return 'Сначала подключите профиль: отправьте /link КОД из админки.'
    master = account.master
    if command == '/help':
        return ('Команды: /profile — посмотреть профиль; /bio — изменить описание; '
                '/photo — фото профиля; /gallery — фото в общую галерею; '
                '/services — список назначенных услуг; /work ID — фото работы по услуге; '
                '/cancel — отменить ожидание.')
    if command == '/profile':
        return f'{master.name}\nОписание: {strip_tags(master.bio)[:1500] or "не заполнено"}'
    if command == '/services':
        services = (Service.objects.filter(staff_prices__master=master, is_active=True)
                    .distinct().order_by('title'))
        lines = [f'{service.pk} — {service.title}' for service in services[:70]]
        return ('Назначенные услуги:\n' + '\n'.join(lines)[:3500]) if lines else 'Назначенных услуг пока нет.'
    if command == '/cancel':
        account.pending_action = ''
        account.pending_service = None
        account.save(update_fields=['pending_action', 'pending_service'])
        return 'Действие отменено.'
    if command == '/bio':
        account.pending_action = 'bio'
        account.pending_service = None
        account.save(update_fields=['pending_action', 'pending_service'])
        if argument.strip():
            text = argument.strip()
        else:
            return 'Отправьте новым сообщением описание профиля (до 2000 символов).'
    if command in ('/photo', '/gallery'):
        account.pending_action = 'profile_photo' if command == '/photo' else 'gallery_photo'
        account.pending_service = None
        account.save(update_fields=['pending_action', 'pending_service'])
        return 'Отправьте фотографию следующим сообщением.'
    if command == '/work':
        if not argument.strip().isdecimal():
            return 'Укажите ID услуги: /work 123. Список доступен по /services.'
        service = Service.objects.filter(pk=int(argument.strip()), is_active=True,
                                         staff_prices__master=master).first()
        if not service:
            return 'Услуга не назначена вам. Проверьте /services.'
        account.pending_action = 'work_photo'
        account.pending_service = service
        account.save(update_fields=['pending_action', 'pending_service'])
        return f'Отправьте фотографию работы по услуге «{service.title}».'
    if account.pending_action == 'bio' and text and not text.startswith('/'):
        if len(text) > 2000:
            return 'Описание длиннее 2000 символов. Отправьте более короткий текст.'
        master.bio = str(escape(text)).replace('\n', '<br>')
        master.save(update_fields=['bio'])
        account.pending_action = ''
        account.save(update_fields=['pending_action'])
        return 'Описание профиля обновлено.'
    if photo and account.pending_action in ('profile_photo', 'gallery_photo', 'work_photo'):
        if download is None:
            return 'Не удалось получить фотографию.'
        result = _save_photo(master, account.pending_action, account.pending_service_id,
                             download(photo), caption)
        account.pending_action = ''
        account.pending_service = None
        account.save(update_fields=['pending_action', 'pending_service'])
        return result
    if account.pending_action:
        return 'Ожидаю текст или фото для выбранного действия. Для отмены отправьте /cancel.'
    return 'Отправьте /help, чтобы увидеть команды.'


def telegram_reply_markup(external_user_id, text=''):
    if MasterMessengerAccount.objects.filter(
        platform=MasterMessengerAccount.PLATFORM_TELEGRAM,
        external_user_id=str(external_user_id),
    ).exists():
        url = settings.TELEGRAM_MINI_APP_URL
        if url.startswith('https://'):
            return {'inline_keyboard': [[{'text': 'Открыть кабинет мастера',
                                         'web_app': {'url': url}}]]}
        return None
    if text == LINK_BUTTON_TEXT:
        return {'force_reply': True, 'input_field_placeholder': 'Код подключения'}
    return {'keyboard': [[{'text': LINK_BUTTON_TEXT}]],
            'resize_keyboard': True, 'one_time_keyboard': True}


def send_message(platform, external_user_id, reply, *, source_text=''):
    if platform == MasterMessengerAccount.PLATFORM_TELEGRAM:
        payload = {'chat_id': external_user_id, 'text': reply[:4096]}
        markup = telegram_reply_markup(external_user_id, source_text)
        if markup:
            payload['reply_markup'] = markup
        response = telegram_request('sendMessage',
                                    json=payload)
    else:
        response = requests.post('https://platform-api2.max.ru/messages',
                                 params={'user_id': external_user_id},
                                 headers={'Authorization': settings.MAX_BOT_TOKEN},
                                 json={'text': reply[:4000]}, timeout=20)
        response.raise_for_status()
