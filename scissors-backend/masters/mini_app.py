"""Telegram Mini App identity checks and private master API."""

import hashlib
import hmac
import json
import re
import time
from html import unescape
from urllib.parse import parse_qsl

import nh3
from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils.html import escape, strip_tags
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from services.master_offers import priced_offers_for_master
from services.models import Service, ServiceStaffPrice

from .bot import MAX_IMAGE_BYTES, _save_photo
from .models import MasterMessengerAccount


def verified_telegram_user_id(init_data, *, now=None):
    """Verify the signed initData supplied by Telegram, never initDataUnsafe."""
    if not settings.TELEGRAM_BOT_TOKEN or not init_data or len(init_data) > 8192:
        raise PermissionDenied('Не удалось подтвердить вход через Telegram.')
    try:
        pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=True,
                          max_num_fields=30)
        values = dict(pairs)
        if len(values) != len(pairs) or not values.get('hash'):
            raise ValueError
        auth_date = int(values['auth_date'])
        current_time = int(time.time() if now is None else now)
        if auth_date > current_time + 60 or current_time - auth_date > 86400:
            raise ValueError
        check_string = '\n'.join(f'{key}={value}' for key, value in sorted(pairs)
                                 if key != 'hash')
        secret = hmac.new(b'WebAppData', settings.TELEGRAM_BOT_TOKEN.encode(),
                          hashlib.sha256).digest()
        expected = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, values['hash']):
            raise ValueError
        user = json.loads(values['user'])
        user_id = user['id']
        if not isinstance(user_id, int) or isinstance(user_id, bool) or user_id <= 0:
            raise ValueError
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        raise PermissionDenied('Не удалось подтвердить вход через Telegram.') from None
    return str(user_id)


class TelegramMiniAppView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    parser_classes = [JSONParser, MultiPartParser]

    def master(self, request):
        authorization = request.headers.get('Authorization', '')
        if not authorization.startswith('tma '):
            raise PermissionDenied('Откройте кабинет из Telegram.')
        user_id = verified_telegram_user_id(authorization[4:])
        account = (MasterMessengerAccount.objects.select_related('master__page', 'master__photo')
                   .filter(platform=MasterMessengerAccount.PLATFORM_TELEGRAM,
                           external_user_id=user_id).first())
        if account is None:
            raise PermissionDenied('Сначала подключите профиль в боте.')
        return account.master


class TelegramMiniAppProfile(TelegramMiniAppView):
    def get(self, request):
        master = self.master(request)
        if not master.page_id:
            master.ensure_page()
        services = (Service.objects.filter(staff_prices__master=master, is_active=True)
                    .distinct().order_by('title'))
        salons = list(master.master_salons.select_related('salon').order_by('salon__name'))
        assignments = list(ServiceStaffPrice.objects.filter(master=master)
                           .select_related('service__category', 'salon')
                           .order_by('salon__name', 'service__title'))
        categories = {
            (row['salon_id'], row['service__category_id']): {
                'salon_id': row['salon_id'], 'id': row['service__category_id'],
                'title': row['service__category__title'],
            }
            for row in priced_offers_for_master(
                master, [item.salon_id for item in salons],
            ).values('salon_id', 'service__category_id', 'service__category__title').distinct()
        }
        for item in assignments:
            if item.salon_id:
                categories.setdefault((item.salon_id, item.service.category_id), {
                    'salon_id': item.salon_id, 'id': item.service.category_id,
                    'title': item.service.category.title,
                })
        gallery = master.page.pictures.select_related('image') if master.page_id else []
        works = master.service_work_photos.select_related('image', 'service').all()
        return Response({
            'name': master.name,
            'price_level_display': master.get_price_level_display() if master.price_level else None,
            'bio': unescape(strip_tags(re.sub(r'<br\s*/?>', '\n', master.bio, flags=re.I))),
            'content': master.page.content,
            'photo_url': master.photo.url if master.photo_id else None,
            'services': [{'id': item.pk, 'title': item.title} for item in services],
            'salons': [{'id': item.salon_id, 'name': item.salon.name} for item in salons],
            'service_categories': sorted(categories.values(),
                                         key=lambda item: (item['salon_id'], item['title'].casefold())),
            'assignments': [
                {'id': item.pk, 'salon_id': item.salon_id,
                 'service_id': item.service_id, 'title': item.service.title,
                 'category_id': item.service.category_id,
                 'category': item.service.category.title}
                for item in assignments
            ],
            'gallery': [{'id': item.pk, 'url': item.image_url, 'caption': item.alt}
                        for item in gallery if item.image_url],
            'works': [{'id': item.pk, 'service_id': item.service_id,
                       'service_title': item.service.title, 'url': item.image.url,
                       'caption': item.caption} for item in works],
        })


class TelegramMiniAppServices(TelegramMiniAppView):
    def get(self, request):
        master = self.master(request)
        query = request.query_params.get('q', '').strip()
        salon_id = request.query_params.get('salon_id', '')
        category_id = request.query_params.get('category_id', '')
        if not salon_id.isdecimal() or not master.master_salons.filter(salon_id=salon_id).exists():
            raise ValidationError({'salon_id': 'Выберите свой салон.'})
        if not category_id.isdecimal():
            raise ValidationError({'category_id': 'Выберите раздел услуг.'})
        if len(query) < 2:
            return Response({'results': []})
        if len(query) > 100:
            raise ValidationError({'q': 'Введите не более 100 символов.'})
        query_words = re.findall(r'\w+', query.casefold())
        if not query_words:
            return Response({'results': []})
        offers = (priced_offers_for_master(master, [salon_id]).filter(
            service__category_id=category_id,
        ).exclude(service_id__in=ServiceStaffPrice.objects.filter(
            master=master, salon_id=salon_id).values('service_id')).select_related(
            'service__category').order_by('service__title'))
        results = []
        for offer in offers:
            title_words = re.findall(r'\w+', offer.service.title.casefold())
            if all(any(word.startswith(part) for word in title_words) for part in query_words):
                results.append({'id': offer.service_id, 'title': offer.service.title,
                                'category': offer.service.category.title})
                if len(results) == 20:
                    break
        return Response({'results': results})

    def post(self, request):
        master = self.master(request)
        salon_id = request.data.get('salon_id')
        service_id = request.data.get('service_id')
        if (isinstance(salon_id, bool) or not str(salon_id).isdecimal()
                or isinstance(service_id, bool) or not str(service_id).isdecimal()):
            raise ValidationError({'service_id': 'Выберите услугу и салон.'})
        salon_id, service_id = int(salon_id), int(service_id)
        if not master.master_salons.filter(salon_id=salon_id).exists():
            raise ValidationError({'salon_id': 'Мастер не работает в этом салоне.'})
        if not priced_offers_for_master(master, [salon_id]).filter(service_id=service_id).exists():
            raise ValidationError({'service_id': 'Для уровня мастера нет цены этой услуги в выбранном салоне.'})
        with transaction.atomic():
            assignment = ServiceStaffPrice.objects.filter(
                master=master, salon_id=salon_id, service_id=service_id).first()
            if assignment is None:
                assignment = ServiceStaffPrice(
                    master=master, salon_id=salon_id, service_id=service_id)
                try:
                    assignment.full_clean()
                except DjangoValidationError as exc:
                    raise ValidationError({'service_id': exc.messages}) from exc
                assignment.save()
        return Response({'id': assignment.pk}, status=201)

    def delete(self, request, assignment_id):
        master = self.master(request)
        deleted, _ = ServiceStaffPrice.objects.filter(
            pk=assignment_id, master=master).delete()
        if not deleted:
            raise ValidationError({'id': 'Назначение не найдено.'})
        return Response(status=204)


class TelegramMiniAppBio(TelegramMiniAppView):
    def post(self, request):
        master = self.master(request)
        bio = request.data.get('bio')
        if not isinstance(bio, str) or len(bio) > 2000:
            raise ValidationError({'bio': 'Введите описание до 2000 символов.'})
        master.bio = str(escape(bio)).replace('\n', '<br>')
        master.save(update_fields=['bio'])
        return Response({'bio': bio})


class TelegramMiniAppContent(TelegramMiniAppView):
    def post(self, request):
        master = self.master(request)
        content = request.data.get('content')
        if not isinstance(content, str) or len(content) > 20000:
            raise ValidationError({'content': 'Введите текст страницы до 20000 символов.'})
        if not master.page_id:
            master.ensure_page()
        clean_content = nh3.clean(
            content,
            tags={'p', 'div', 'span', 'br', 'strong', 'em', 'b', 'i', 'u', 's',
                  'ul', 'ol', 'li', 'blockquote', 'h2', 'h3', 'h4', 'a'},
            attributes={'a': {'href', 'title'}},
            url_schemes={'http', 'https', 'mailto'},
            clean_content_tags={'script', 'style'},
        )
        master.page.content = clean_content
        master.page.save(update_fields=['content'])
        return Response({'content': clean_content})


class TelegramMiniAppPhoto(TelegramMiniAppView):
    def post(self, request):
        master = self.master(request)
        kind = request.data.get('kind')
        action = {'profile': 'profile_photo', 'gallery': 'gallery_photo',
                  'work': 'work_photo'}.get(kind) if isinstance(kind, str) else None
        upload = request.FILES.get('image')
        if not action or not upload or upload.size > MAX_IMAGE_BYTES:
            raise ValidationError({'image': 'Выберите изображение до 10 МБ.'})
        service_id = request.data.get('service_id')
        if kind == 'work':
            if not str(service_id or '').isdecimal():
                raise ValidationError({'service_id': 'Выберите услугу.'})
            service_id = int(service_id)
        else:
            service_id = None
        caption = request.data.get('caption', '')
        if not isinstance(caption, str) or len(caption) > 255:
            raise ValidationError({'caption': 'Подпись должна быть не длиннее 255 символов.'})
        try:
            message = _save_photo(master, action, service_id, upload.read(), caption)
        except ValueError as exc:
            raise ValidationError({'image': str(exc)}) from exc
        return Response({'detail': message})
