import json
import hashlib
import hmac
import time
from io import BytesIO
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.parse import urlencode

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.exceptions import PermissionDenied
from PIL import Image

from pages.models import Page, PagePicture
from salons.models import Salon
from services.models import Service, ServiceCategory, ServicePrice, ServiceSalon, ServiceStaffPrice

from .bot import create_pairing_code, handle_message
from .mini_app import verified_telegram_user_id
from .models import (Master, MasterSalon, MasterMessengerAccount, MasterMessengerPairingCode,
                     MasterServiceWorkPhoto, ProcessedMessengerUpdate)


@override_settings(TELEGRAM_BOT_TOKEN='test-token', TELEGRAM_WEBHOOK_SECRET='test-secret',
                   TELEGRAM_PROXY_URL='socks5://proxy.example',
                   TELEGRAM_WEBHOOK_URL='https://api.studio.scissors.group/webhooks/staff/telegram/',
                   TELEGRAM_MINI_APP_URL='https://scissors.group/master-app',
                   MAX_BOT_TOKEN='max-test-token', MAX_WEBHOOK_SECRET='max-secret')
class StaffBotTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user('bot-master', is_staff=True)
        team = Page.objects.create(url='team', title='Команда')
        page = Page.objects.create(parent=team, url='bot-master', title='Мастер')
        self.master = Master.objects.create(name='Мастер', user=user, page=page)
        salon = Salon.objects.create(name='Салон', address='Адрес', latitude=55, longitude=37)
        category = ServiceCategory.objects.create(title='Стрижки', code='bot-hair')
        self.service = Service.objects.create(category=category, title='Стрижка', price_code='BOT-1')
        ServiceSalon.objects.create(service=self.service, salon=salon)
        ServiceStaffPrice.objects.create(master=self.master, salon=salon, service=self.service)
        self.user = user

    def image_bytes(self):
        buffer = BytesIO()
        Image.new('RGB', (2, 2), 'green').save(buffer, format='PNG')
        return buffer.getvalue()

    def signed_init_data(self, user_id=123, auth_date=None):
        values = {
            'auth_date': str(int(time.time()) if auth_date is None else auth_date),
            'user': json.dumps({'id': user_id}, separators=(',', ':')),
        }
        check_string = '\n'.join(f'{key}={value}' for key, value in sorted(values.items()))
        secret = hmac.new(b'WebAppData', b'test-token', hashlib.sha256).digest()
        values['hash'] = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
        return urlencode(values)

    def test_pairing_code_is_one_time_and_scopes_edits_to_master(self):
        code = create_pairing_code(self.master)
        self.assertIn('подключите', handle_message('telegram', '123', '/bio чужой'))
        self.assertIn('подключён профиль', handle_message('telegram', '123', f'/link {code}'))
        self.assertIn('недействителен', handle_message('max', '456', f'/link {code}'))
        self.assertIsNotNone(MasterMessengerPairingCode.objects.get(master=self.master).used_at)
        self.assertIn('обновлено', handle_message('telegram', '123', '/bio Новое описание'))
        self.master.refresh_from_db()
        self.assertEqual(self.master.bio, 'Новое описание')
        handle_message('telegram', '123', '/bio <img src=x onerror=alert(1)>')
        self.master.refresh_from_db()
        self.assertNotIn('<img', self.master.bio)
        self.assertIn('Стрижка', handle_message('telegram', '123', '/services'))
        self.assertIn('не назначена', handle_message('telegram', '123', '/work 999999'))
        self.assertIn('Отправьте фотографию', handle_message(
            'telegram', '123', f'/work {self.service.pk}'))
        with TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            reply = handle_message('telegram', '123', photo='file-id',
                                   caption='Работа', download=lambda _: self.image_bytes())
            self.assertIn('Фото добавлено', reply)
            self.assertEqual(MasterServiceWorkPhoto.objects.get().service, self.service)
            self.assertIn('Отправьте фотографию', handle_message('telegram', '123', '/gallery'))
            handle_message('telegram', '123', photo='file-id', download=lambda _: self.image_bytes())
            self.assertEqual(PagePicture.objects.filter(page=self.master.page).count(), 1)
            self.assertIn('Отправьте фотографию', handle_message('telegram', '123', '/photo'))
            handle_message('telegram', '123', photo='file-id', download=lambda _: self.image_bytes())
            self.master.refresh_from_db()
            self.assertIsNotNone(self.master.photo_id)

    def test_messenger_admin_code_and_access_control(self):
        self.client.force_login(self.user)
        url = reverse('admin:masters_master_messenger', args=[self.master.pk])
        response = self.client.post(url, {'action': 'generate'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['code'])
        self.assertContains(response, '/link ')
        other = Master.objects.create(name='Другой')
        self.assertEqual(self.client.get(reverse('admin:masters_master_messenger',
                                                     args=[other.pk])).status_code, 404)

    @patch('masters.telegram_api.requests.post')
    def test_telegram_setup_is_superuser_only_and_uses_proxy(self, post):
        url = reverse('admin-telegram-webhook-settings')
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(url).status_code, 403)
        post.assert_not_called()

        self.user.is_superuser = True
        self.user.save(update_fields=['is_superuser'])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'test-token')
        self.assertNotContains(response, 'test-secret')

        post.return_value.json.return_value = {'ok': True, 'result': True}
        self.assertEqual(self.client.post(url).status_code, 302)
        args, kwargs = post.call_args
        self.assertEqual(args[0], 'https://api.telegram.org/bottest-token/setWebhook')
        self.assertEqual(kwargs['proxies'], {
            'http': 'socks5://proxy.example',
            'https': 'socks5://proxy.example',
        })
        self.assertEqual(kwargs['json'], {
            'url': 'https://api.studio.scissors.group/webhooks/staff/telegram/',
            'secret_token': 'test-secret',
            'allowed_updates': ['message'],
        })

    @patch('masters.telegram_api.requests.post')
    def test_telegram_requests_fail_closed_without_proxy(self, post):
        from .telegram_api import set_telegram_webhook

        with override_settings(TELEGRAM_PROXY_URL=''):
            with self.assertRaisesMessage(ValueError, 'TELEGRAM_PROXY_URL'):
                set_telegram_webhook()
        post.assert_not_called()

    @patch('masters.telegram_api.requests.get')
    @patch('masters.telegram_api.requests.post')
    def test_telegram_photo_calls_use_proxy(self, post, get):
        from .bot import download_telegram_photo

        post.return_value.json.return_value = {
            'ok': True, 'result': {'file_path': 'photos/example.jpg'},
        }
        get.return_value.is_redirect = False
        get.return_value.iter_content.return_value = [self.image_bytes()]
        self.assertEqual(download_telegram_photo('file-id'), self.image_bytes())
        self.assertEqual(post.call_args.kwargs['proxies']['https'],
                         'socks5://proxy.example')
        self.assertEqual(get.call_args.kwargs['proxies']['https'],
                         'socks5://proxy.example')

    @patch('masters.telegram_api.requests.post')
    def test_telegram_reply_uses_proxy(self, post):
        from .bot import send_message

        post.return_value.json.return_value = {'ok': True, 'result': True}
        send_message('telegram', '123', 'Готово')
        self.assertEqual(post.call_args.kwargs['json']['chat_id'], '123')
        self.assertEqual(post.call_args.kwargs['json']['text'], 'Готово')
        self.assertEqual(post.call_args.kwargs['json']['reply_markup']['keyboard'][0][0]['text'],
                         'Подключить профиль')
        self.assertEqual(post.call_args.kwargs['proxies']['https'],
                         'socks5://proxy.example')

    def test_start_button_accepts_code_and_opens_mini_app(self):
        from .bot import LINK_BUTTON_TEXT, telegram_reply_markup

        self.assertIn('/link', handle_message('telegram', '123', '/start'))
        self.assertEqual(telegram_reply_markup('123')['keyboard'][0][0]['text'],
                         LINK_BUTTON_TEXT)
        self.assertIn('Введите код', handle_message('telegram', '123', LINK_BUTTON_TEXT))
        self.assertTrue(telegram_reply_markup('123', LINK_BUTTON_TEXT)['force_reply'])
        code = create_pairing_code(self.master)
        self.assertIn('подключён профиль', handle_message('telegram', '123', code))
        self.assertEqual(
            telegram_reply_markup('123')['inline_keyboard'][0][0]['web_app']['url'],
            'https://scissors.group/master-app',
        )

    def test_mini_app_requires_signed_linked_telegram_identity(self):
        init_data = self.signed_init_data()
        self.assertEqual(verified_telegram_user_id(init_data), '123')
        with self.assertRaises(PermissionDenied):
            verified_telegram_user_id(init_data.replace('123', '456'))
        with self.assertRaises(PermissionDenied):
            verified_telegram_user_id(self.signed_init_data(auth_date=1))

        url = reverse('telegram-mini-app-profile')
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.get(url, HTTP_AUTHORIZATION=f'tma {init_data}').status_code,
                         403)
        code = create_pairing_code(self.master)
        handle_message('telegram', '123', f'/link {code}')
        response = self.client.get(url, HTTP_AUTHORIZATION=f'tma {init_data}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['name'], self.master.name)
        self.assertEqual(response.json()['content'], self.master.page.content)
        self.assertEqual(response.json()['services'][0]['title'], self.service.title)
        other_init_data = self.signed_init_data(user_id=456)
        self.assertEqual(self.client.get(url, HTTP_AUTHORIZATION=f'tma {other_init_data}').status_code,
                         403)

        response = self.client.post(reverse('telegram-mini-app-bio'),
                                    json.dumps({'bio': '<script>x</script>\nОписание'}),
                                    content_type='application/json',
                                    HTTP_AUTHORIZATION=f'tma {init_data}')
        self.assertEqual(response.status_code, 200)
        self.master.refresh_from_db()
        self.assertNotIn('<script>', self.master.bio)

        content_url = reverse('telegram-mini-app-content')
        self.assertEqual(self.client.post(content_url, {'content': 'Чужой текст'}).status_code,
                         403)
        response = self.client.post(content_url, json.dumps({
            'content': '<p>О мастере</p><script>alert(1)</script>'
                       '<a href="javascript:alert(1)">Ссылка</a>',
        }), content_type='application/json', HTTP_AUTHORIZATION=f'tma {init_data}')
        self.assertEqual(response.status_code, 200)
        self.master.page.refresh_from_db()
        self.assertIn('<p>О мастере</p>', self.master.page.content)
        self.assertNotIn('<script', self.master.page.content)
        self.assertNotIn('javascript:', self.master.page.content)
        self.assertEqual(self.client.get(url, HTTP_AUTHORIZATION=f'tma {init_data}').json()['content'],
                         self.master.page.content)

        with TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            response = self.client.post(reverse('telegram-mini-app-photo'), {
                'kind': 'work', 'service_id': str(self.service.pk),
                'image': self.uploaded_image(),
            }, HTTP_AUTHORIZATION=f'tma {init_data}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(MasterServiceWorkPhoto.objects.count(), 1)

    def test_mini_app_master_can_search_add_and_remove_own_salon_services(self):
        salon = Salon.objects.get()
        MasterSalon.objects.create(master=self.master, salon=salon)
        self.master.price_level = 'stylist'
        self.master.save(update_fields=['price_level'])
        extra = Service.objects.create(
            category=self.service.category, title='Мужская стрижка', price_code='BOT-2')
        offer = ServiceSalon.objects.create(service=extra, salon=salon)
        ServicePrice.objects.create(salon_service=offer, level='art_director', amount=3000)
        coloring = Service.objects.create(
            category=self.service.category, title='Сложное окрашивание волос', price_code='BOT-3')
        coloring_offer = ServiceSalon.objects.create(service=coloring, salon=salon)
        ServicePrice.objects.create(salon_service=coloring_offer, level='stylist', amount=4500)
        men = ServiceCategory.objects.create(title='Для мужчин', code='bot-men')
        beard = Service.objects.create(category=men, title='Окрашивание бороды', price_code='BOT-4')
        beard_offer = ServiceSalon.objects.create(service=beard, salon=salon)
        ServicePrice.objects.create(salon_service=beard_offer, level='stylist', amount=1800)
        other_salon = Salon.objects.create(name='Другой', address='Адрес', latitude=55, longitude=37)
        ServiceSalon.objects.create(service=extra, salon=other_salon)
        MasterMessengerAccount.objects.create(
            master=self.master, platform='telegram', external_user_id='123')
        auth = f'tma {self.signed_init_data()}'
        url = reverse('telegram-mini-app-services')

        params = {'salon_id': salon.pk, 'category_id': self.service.category_id}
        response = self.client.get(url, {**params, 'q': 'стриж'},
                                   HTTP_AUTHORIZATION=auth)
        self.assertEqual(response.json()['results'], [])
        body = json.dumps({'salon_id': salon.pk, 'service_id': extra.pk})
        self.assertEqual(self.client.post(url, body, content_type='application/json',
                                          HTTP_AUTHORIZATION=auth).status_code, 400)
        ServicePrice.objects.create(salon_service=offer, level='stylist', amount=2500)
        response = self.client.get(url, {**params, 'q': 'стриж'},
                                   HTTP_AUTHORIZATION=auth)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item['id'] for item in response.json()['results']], [extra.pk])
        self.assertEqual([item['id'] for item in self.client.get(
            url, {**params, 'q': 'окра'}, HTTP_AUTHORIZATION=auth).json()['results']],
            [coloring.pk])
        self.assertEqual(self.client.get(url, {**params, 'q': 'кра'},
                                         HTTP_AUTHORIZATION=auth).json()['results'], [])
        self.assertEqual([item['id'] for item in self.client.get(
            url, {'salon_id': salon.pk, 'category_id': men.pk, 'q': 'окра'},
            HTTP_AUTHORIZATION=auth).json()['results']], [beard.pk])
        self.assertEqual(self.client.get(url, {**params, 'q': 'с'},
                                         HTTP_AUTHORIZATION=auth).json()['results'], [])
        self.assertEqual(self.client.get(url, {
            'salon_id': other_salon.pk, 'category_id': self.service.category_id, 'q': 'стриж',
        },
                                         HTTP_AUTHORIZATION=auth).status_code, 400)

        self.assertEqual(self.client.post(url, body, content_type='application/json',
                                          HTTP_AUTHORIZATION=auth).status_code, 201)
        assignment = ServiceStaffPrice.objects.get(master=self.master, salon=salon, service=extra)
        self.assertEqual(self.client.post(url, body, content_type='application/json',
                                          HTTP_AUTHORIZATION=auth).status_code, 201)
        self.assertEqual(ServiceStaffPrice.objects.filter(master=self.master, service=extra).count(), 1)
        profile = self.client.get(reverse('telegram-mini-app-profile'),
                                  HTTP_AUTHORIZATION=auth).json()
        self.assertIn(extra.pk, [item['id'] for item in profile['services']])
        self.assertIn(assignment.pk, [item['id'] for item in profile['assignments']])
        self.assertEqual({item['id'] for item in profile['service_categories']},
                         {self.service.category_id, men.pk})

        detail = reverse('telegram-mini-app-service-detail', args=[assignment.pk])
        self.assertEqual(self.client.delete(detail, HTTP_AUTHORIZATION=auth).status_code, 204)
        self.assertFalse(ServiceStaffPrice.objects.filter(pk=assignment.pk).exists())
        self.assertEqual(self.client.delete(detail, HTTP_AUTHORIZATION=auth).status_code, 400)
        self.assertEqual(self.client.post(
            url, json.dumps({'salon_id': other_salon.pk, 'service_id': extra.pk}),
            content_type='application/json', HTTP_AUTHORIZATION=auth).status_code, 400)
        self.assertEqual(self.client.delete(reverse('telegram-mini-app-service-detail',
                                                    args=[self.master.service_prices.first().pk]),
                                            HTTP_AUTHORIZATION=f'tma {self.signed_init_data(456)}').status_code,
                         403)

    def uploaded_image(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        return SimpleUploadedFile('work.png', self.image_bytes(), content_type='image/png')

    @patch('masters.bot_views.send_message')
    def test_telegram_webhook_checks_secret_and_ignores_duplicate(self, send_message):
        code = create_pairing_code(self.master)
        update = {'update_id': 101, 'message': {
            'from': {'id': 123}, 'chat': {'id': 123, 'type': 'private'},
            'text': f'/link {code}',
        }}
        url = reverse('staff-telegram-webhook')
        self.assertEqual(self.client.post(url, json.dumps(update), content_type='application/json').status_code,
                         403)
        for _ in range(2):
            self.assertEqual(self.client.post(
                url, json.dumps(update), content_type='application/json',
                HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN='test-secret',
            ).status_code, 200)
        self.assertEqual(send_message.call_count, 1)
        self.assertEqual(ProcessedMessengerUpdate.objects.count(), 1)
        self.assertTrue(MasterMessengerAccount.objects.filter(
            platform='telegram', external_user_id='123', master=self.master).exists())

    @patch('masters.telegram_api.requests.post')
    def test_telegram_send_failure_is_logged_without_token(self, post):
        post.return_value.json.return_value = {'ok': False, 'error_code': 400}
        update = {'update_id': 909, 'message': {
            'from': {'id': 123}, 'chat': {'id': 123, 'type': 'private'}, 'text': '/start',
        }}
        with self.assertLogs('masters.bot_views', level='INFO') as logs:
            response = self.client.post(
                reverse('staff-telegram-webhook'), json.dumps(update),
                content_type='application/json',
                HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN='test-secret',
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn('update_id=909', '\n'.join(logs.output))
        self.assertIn('API=400', '\n'.join(logs.output))
        self.assertNotIn('test-token', '\n'.join(logs.output))

    @patch('masters.bot_views.send_message')
    def test_max_webhook_uses_private_message_user_id(self, send_message):
        code = create_pairing_code(self.master)
        update = {'update_type': 'message_created', 'message': {
            'sender': {'user_id': 456}, 'recipient': {'chat_type': 'dialog'},
            'body': {'mid': 'msg-1', 'text': f'/link {code}'},
        }}
        response = self.client.post(reverse('staff-max-webhook'), json.dumps(update),
                                    content_type='application/json',
                                    HTTP_X_MAX_BOT_API_SECRET='max-secret')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(MasterMessengerAccount.objects.filter(
            platform='max', external_user_id='456', master=self.master).exists())
        send_message.assert_called_once()

    @patch('masters.bot_views.download_max_photo')
    @patch('masters.bot_views.send_message')
    def test_max_image_can_add_work_to_assigned_service(self, send_message, download):
        code = create_pairing_code(self.master)
        handle_message('max', '456', f'/link {code}')
        handle_message('max', '456', f'/work {self.service.pk}')
        download.return_value = self.image_bytes()
        update = {'update_type': 'message_created', 'message': {
            'sender': {'user_id': 456}, 'recipient': {'chat_type': 'dialog'},
            'body': {'mid': 'photo-1', 'text': 'Готовая работа', 'attachments': [
                {'type': 'image', 'payload': {'url': 'https://media.max.ru/example.png'}},
            ]},
        }}
        with TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            response = self.client.post(reverse('staff-max-webhook'), json.dumps(update),
                                        content_type='application/json',
                                        HTTP_X_MAX_BOT_API_SECRET='max-secret')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(MasterServiceWorkPhoto.objects.get().service, self.service)
        download.assert_called_once_with('https://media.max.ru/example.png')
