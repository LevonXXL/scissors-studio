import base64
import json
import sys
from io import StringIO
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings
from rest_framework.test import APITestCase

from masters.models import Master

from .models import FeedbackRequest, PushPreference, PushSubscription
from .push import notify_new_feedback, push_configuration_error, send_to_staff


PUBLIC_KEY = base64.urlsafe_b64encode(b'\x04' + b'\x01' * 64).rstrip(b'=').decode()
PUSH_SETTINGS = {
    'WEB_PUSH_VAPID_PUBLIC_KEY': PUBLIC_KEY,
    'WEB_PUSH_VAPID_PRIVATE_KEY': 'encoded-test-key',
    'WEB_PUSH_VAPID_SUBJECT': 'mailto:ops@example.test',
}


class FakeWebPushException(Exception):
    def __init__(self, status_code):
        super().__init__('secret response body')
        self.status_code = status_code


def fake_pywebpush(sender):
    module = ModuleType('pywebpush')
    module.WebPushException = FakeWebPushException
    module.webpush = sender
    return patch.dict(sys.modules, {'pywebpush': module})


@override_settings(**PUSH_SETTINGS)
class FeedbackPushTests(APITestCase):
    def create_subscription(self, username, *, staff=True, superuser=False, active=True, enabled=True):
        user = get_user_model().objects.create_user(
            username=username, password='TestPassword#539', is_staff=staff,
            is_superuser=superuser, is_active=active,
        )
        PushPreference.objects.create(user=user, enabled=enabled)
        subscription = PushSubscription.objects.create(
            user=user, endpoint=f'https://push.example.test/{username}-secret-endpoint',
            p256dh='secret-p256dh', auth='secret-auth',
        )
        return user, subscription

    def test_feedback_is_saved_before_notification_dispatch(self):
        observed = []
        with patch('communications.views.notify_new_feedback', side_effect=lambda feedback: observed.append(feedback.pk)):
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post('/api/v1/feedback/', {
                    'name': 'Клиент', 'phone': '+79991234567', 'message': 'Перезвоните мне',
                })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(observed, [response.data['id']])
        self.assertTrue(FeedbackRequest.objects.filter(pk=response.data['id']).exists())

    def test_feedback_accepts_email_as_contact(self):
        response = self.client.post('/api/v1/feedback/', {
            'name': 'Клиент', 'phone': 'client@example.com', 'message': 'Подскажите цену',
        })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(FeedbackRequest.objects.get(pk=response.data['id']).phone, 'client@example.com')

    def test_feedback_rejects_invalid_contact(self):
        response = self.client.post('/api/v1/feedback/', {
            'name': 'Клиент', 'phone': 'client@invalid', 'message': 'Подскажите цену',
        })
        self.assertEqual(response.status_code, 400)
        self.assertFalse(FeedbackRequest.objects.exists())

    def test_only_enabled_active_staff_subscriptions_are_sent(self):
        staff, selected = self.create_subscription('staff')
        self.create_subscription('client', staff=False)
        self.create_subscription('disabled', enabled=False)
        self.create_subscription('inactive', active=False)
        sender = Mock(return_value=SimpleNamespace(status_code=201))

        with fake_pywebpush(sender):
            send_to_staff('Новое обращение', 'Перезвонить', '/admin/communications/feedbackrequest/1/change/')

        sender.assert_called_once()
        self.assertEqual(sender.call_args.kwargs['subscription_info']['endpoint'], selected.endpoint)
        self.assertEqual(selected.user_id, staff.pk)

    def test_feedback_push_requires_view_permission(self):
        master_user, master_subscription = self.create_subscription('master')
        Master.objects.create(name='Мастер', user=master_user)
        _, technical_subscription = self.create_subscription('technical')
        self.create_subscription('staff-without-permission')
        permission = Permission.objects.get(content_type__app_label='communications',
                                            codename='view_feedbackrequest')
        group = Group.objects.create(name='Просмотр обращений')
        group.permissions.add(permission)
        master_user.groups.add(group)
        technical_subscription.user.user_permissions.add(permission)
        sender = Mock(return_value=SimpleNamespace(status_code=201))
        feedback = FeedbackRequest.objects.create(
            name='Клиент', phone='+79991234567', message='Перезвоните мне',
        )

        with fake_pywebpush(sender):
            notify_new_feedback(feedback)

        self.assertEqual(sender.call_count, 2)
        endpoints = {call.kwargs['subscription_info']['endpoint'] for call in sender.call_args_list}
        self.assertEqual(endpoints, {master_subscription.endpoint, technical_subscription.endpoint})

    def test_subscription_api_saves_to_current_user_and_disabling_removes_it(self):
        staff = get_user_model().objects.create_user(
            username='staff', password='TestPassword#539', is_staff=True,
        )
        self.client.force_authenticate(user=staff)
        payload = {
            'endpoint': 'https://push.example.test/device-secret-endpoint',
            'keys': {'p256dh': 'device-p256dh', 'auth': 'device-auth'},
        }
        self.assertEqual(self.client.post('/api/v1/push/subscriptions/', payload, format='json').status_code, 403)
        self.assertEqual(self.client.put('/api/v1/push/preferences/', {'enabled': True}, format='json').status_code, 200)
        self.assertEqual(self.client.post('/api/v1/push/subscriptions/', payload, format='json').status_code, 204)
        subscription = PushSubscription.objects.get(endpoint=payload['endpoint'])
        self.assertEqual(subscription.user_id, staff.pk)
        self.assertTrue(PushPreference.objects.get(user=staff).enabled)

        self.assertEqual(self.client.put('/api/v1/push/preferences/', {'enabled': False}, format='json').status_code, 200)
        self.assertFalse(PushSubscription.objects.filter(pk=subscription.pk).exists())

    def test_generic_failure_logs_type_and_errno_without_secret_values(self):
        _, subscription = self.create_subscription('staff')
        sender = Mock(side_effect=PermissionError(13, 'secret private key path'))

        with fake_pywebpush(sender), self.assertLogs('communications.push', level='WARNING') as captured:
            send_to_staff('Новое обращение', 'Перезвонить', '/')

        log = '\n'.join(captured.output)
        self.assertIn('PermissionError', log)
        self.assertIn('errno=13', log)
        self.assertIn(f'subscription_id={subscription.pk}', log)
        self.assertNotIn('secret private key path', log)
        self.assertNotIn('staff-secret-endpoint', log)
        self.assertNotIn('secret-p256dh', log)
        self.assertNotIn('secret-auth', log)

    def test_revoked_subscription_is_removed_and_other_http_errors_are_logged_safely(self):
        _, revoked = self.create_subscription('revoked')
        _, missing = self.create_subscription('missing')
        _, rejected = self.create_subscription('rejected')

        def reject_by_endpoint(*, subscription_info, **kwargs):
            endpoint = subscription_info['endpoint']
            if 'revoked' in endpoint:
                raise FakeWebPushException(410)
            if 'missing' in endpoint:
                raise FakeWebPushException(404)
            raise FakeWebPushException(403)

        sender = Mock(side_effect=reject_by_endpoint)

        with fake_pywebpush(sender), self.assertLogs('communications.push', level='INFO') as captured:
            send_to_staff('Новое обращение', 'Перезвонить', '/')

        self.assertEqual(sender.call_count, 3)
        self.assertFalse(PushSubscription.objects.filter(pk=revoked.pk).exists())
        self.assertFalse(PushSubscription.objects.filter(pk=missing.pk).exists())
        self.assertTrue(PushSubscription.objects.filter(pk=rejected.pk).exists())
        log = '\n'.join(captured.output)
        self.assertIn('status=410', log)
        self.assertIn('status=404', log)
        self.assertIn('status=403', log)
        self.assertIn(f'subscription_id={revoked.pk}', log)
        self.assertIn('WebPushException', log)
        self.assertNotIn('secret response body', log)

    def test_webpush_error_before_http_is_distinguished_from_provider_response(self):
        self.create_subscription('staff')
        sender = Mock(side_effect=FakeWebPushException(None))
        with fake_pywebpush(sender), self.assertLogs('communications.push', level='WARNING') as captured:
            send_to_staff('Новое обращение', 'Перезвонить', '/')
        log = '\n'.join(captured.output)
        self.assertIn('error_type=FakeWebPushException', log)
        self.assertIn('phase=before_http', log)
        self.assertNotIn('secret response body', log)

    def test_dispatch_failure_does_not_remove_saved_feedback_or_log_exception_text(self):
        feedback = FeedbackRequest.objects.create(
            name='Клиент', phone='+79991234567', message='Перезвоните мне',
        )
        with patch('communications.push.send_to_staff', side_effect=RuntimeError('secret failure detail')):
            with self.assertLogs('communications.push', level='WARNING') as captured:
                notify_new_feedback(feedback)
        self.assertTrue(FeedbackRequest.objects.filter(pk=feedback.pk).exists())
        log = '\n'.join(captured.output)
        self.assertIn('RuntimeError', log)
        self.assertNotIn('secret failure detail', log)

    def test_invalid_configuration_reports_safe_reason_codes(self):
        self.assertIsNone(push_configuration_error())
        with override_settings(WEB_PUSH_VAPID_PRIVATE_KEY='/missing/private-key.pem'):
            self.assertEqual(push_configuration_error(), 'private_key_file_missing_or_inaccessible')
        with override_settings(WEB_PUSH_VAPID_PUBLIC_KEY='not-a-public-key'):
            self.assertEqual(push_configuration_error(), 'invalid_public_key')
        with override_settings(WEB_PUSH_VAPID_SUBJECT='not-a-valid-subject'):
            self.assertEqual(push_configuration_error(), 'invalid_vapid_subject')

    def test_test_push_command_targets_only_eligible_superusers(self):
        _, selected = self.create_subscription('superuser', superuser=True)
        self.create_subscription('staff')
        self.create_subscription('disabled-superuser', superuser=True, enabled=False)
        self.create_subscription('inactive-superuser', superuser=True, active=False)
        sender = Mock(return_value=SimpleNamespace(status_code=201))
        output = StringIO()

        with fake_pywebpush(sender):
            call_command('send_test_push', '--message', 'Проверка', stdout=output)

        sender.assert_called_once()
        self.assertEqual(sender.call_args.kwargs['subscription_info']['endpoint'], selected.endpoint)
        self.assertEqual(json.loads(sender.call_args.kwargs['data'])['body'], 'Проверка')
        self.assertIn('принято push-сервисом: 1', output.getvalue())

    def test_test_push_command_reports_no_eligible_subscriptions(self):
        self.create_subscription('staff')
        with fake_pywebpush(Mock()), self.assertLogs('communications.push', level='WARNING'):
            with self.assertRaisesMessage(CommandError, 'Нет активных push-подписок суперпользователей'):
                call_command('send_test_push', stdout=StringIO())

    def test_test_push_command_identifies_missing_setting_without_value(self):
        with override_settings(WEB_PUSH_VAPID_SUBJECT=''):
            with self.assertRaisesMessage(CommandError, 'WEB_PUSH_VAPID_SUBJECT'):
                call_command('send_test_push', stdout=StringIO())

    def test_test_push_command_reports_delivery_failure(self):
        self.create_subscription('superuser', superuser=True)
        sender = Mock(side_effect=FakeWebPushException(403))
        output = StringIO()
        with fake_pywebpush(sender), self.assertLogs('communications.push', level='WARNING'):
            with self.assertRaisesMessage(CommandError, 'Часть уведомлений не принята'):
                call_command('send_test_push', stdout=output)
        self.assertIn('ошибок: 1', output.getvalue())
        sender.assert_called_once()
