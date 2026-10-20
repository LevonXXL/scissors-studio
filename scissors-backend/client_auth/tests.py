import re
from datetime import timedelta
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import RequestFactory, override_settings
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from .admin import AdminUserChangeForm
from .models import PendingEmailVerification, PhoneCode, PhoneVerificationSession, VerifiedEmail, VerifiedPhone


@override_settings(DEBUG=True)
class ClientAuthTests(APITestCase):
    phone = '+79991234567'

    def request_code(self, phone=None):
        with self.assertLogs('client_auth.services', level='WARNING') as logs:
            response = self.client.post('/api/v1/auth/request-code/', {'phone': phone or self.phone})
        self.assertEqual(response.status_code, 202)
        return re.search(r'(\d{6})$', logs.output[0]).group(1)

    def test_sms_then_password_and_one_time_code(self):
        code = self.request_code('8 (999) 123-45-67')
        response = self.client.post('/api/v1/auth/verify-code/', {'phone': self.phone, 'code': code})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['has_password'])
        user = get_user_model().objects.get(username=self.phone)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(VerifiedPhone.objects.filter(user=user, phone=self.phone).exists())
        self.assertNotIn(code, PhoneCode.objects.get(phone=self.phone).code_hash)
        self.assertEqual(self.client.post('/api/v1/auth/verify-code/', {'phone': self.phone, 'code': code}).status_code, 403)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
        self.assertEqual(self.client.post('/api/v1/auth/set-password/', {'new_password': 'StrongPassphrase#539'}).status_code, 200)
        self.assertEqual(self.client.post('/api/v1/auth/set-password/', {'new_password': 'AnotherStrong#539'}).status_code, 400)
        self.client.credentials()
        login = self.client.post('/api/v1/auth/login-password/', {'phone': self.phone, 'password': 'StrongPassphrase#539'})
        self.assertEqual(login.status_code, 200)
        self.assertTrue(login.data['has_password'])
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        self.assertEqual(self.client.post('/api/v1/auth/change-password/', {
            'current_password': 'wrong', 'new_password': 'AnotherStrong#539',
        }).status_code, 400)
        self.assertEqual(self.client.post('/api/v1/auth/change-password/', {
            'current_password': 'StrongPassphrase#539', 'new_password': 'AnotherStrong#539',
        }).status_code, 200)

    def test_existing_staff_account_is_not_claimed(self):
        staff = get_user_model().objects.create_user(username=self.phone, password='StaffPassphrase#539', is_staff=True)
        code = self.request_code()
        self.assertEqual(self.client.post('/api/v1/auth/verify-code/', {'phone': self.phone, 'code': code}).status_code, 403)
        self.assertFalse(VerifiedPhone.objects.filter(user=staff).exists())
        self.assertTrue(staff.is_staff)
        self.assertEqual(self.client.post('/api/v1/auth/login-password/', {
            'phone': self.phone, 'password': 'StaffPassphrase#539',
        }).status_code, 403)

    def test_wrong_codes_are_limited(self):
        self.request_code()
        for _ in range(5):
            self.assertEqual(self.client.post('/api/v1/auth/verify-code/', {
                'phone': self.phone, 'code': '000000',
            }).status_code, 403)
        self.assertEqual(PhoneVerificationSession.objects.get(phone=self.phone).attempts, 5)

    def test_expired_code_cannot_create_user(self):
        code = self.request_code()
        PhoneCode.objects.filter(phone=self.phone).update(expires_at=timezone.now() - timedelta(seconds=1))
        response = self.client.post('/api/v1/auth/verify-code/', {'phone': self.phone, 'code': code})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(get_user_model().objects.filter(username=self.phone).exists())

    def test_code_requests_are_rate_limited(self):
        for _ in range(3):
            self.request_code()
            PhoneVerificationSession.objects.filter(phone=self.phone).update(
                last_requested_at=timezone.now() - timedelta(seconds=61),
            )
        response = self.client.post('/api/v1/auth/request-code/', {'phone': self.phone})
        self.assertEqual(response.status_code, 429)

    def test_resend_preserves_first_code_and_session_deadline(self):
        with patch('client_auth.services.secrets.randbelow', side_effect=[123456, 654321]):
            first = self.request_code()
            session = PhoneVerificationSession.objects.get(phone=self.phone)
            started_at, expires_at = session.started_at, session.expires_at
            PhoneVerificationSession.objects.filter(pk=session.pk).update(
                last_requested_at=timezone.now() - timedelta(seconds=61),
            )
            second = self.request_code()
        session.refresh_from_db()
        self.assertEqual((session.started_at, session.expires_at), (started_at, expires_at))
        self.assertEqual(expires_at - started_at, timedelta(minutes=30))
        codes = list(PhoneCode.objects.filter(session=session))
        self.assertEqual(len(codes), 2)
        self.assertTrue(all(code.expires_at - code.requested_at == timedelta(minutes=5) for code in codes))
        self.assertEqual(self.client.post('/api/v1/auth/verify-code/', {
            'phone': self.phone, 'code': first,
        }).status_code, 200)
        self.assertIsNotNone(PhoneVerificationSession.objects.get(pk=session.pk).completed_at)
        self.assertEqual(self.client.post('/api/v1/auth/verify-code/', {
            'phone': self.phone, 'code': second,
        }).status_code, 403)

    def test_second_code_valid_after_first_expires(self):
        with patch('client_auth.services.secrets.randbelow', side_effect=[123456, 654321]):
            first = self.request_code()
            PhoneVerificationSession.objects.filter(phone=self.phone).update(
                last_requested_at=timezone.now() - timedelta(seconds=61),
            )
            second = self.request_code()
        first_record = PhoneCode.objects.filter(phone=self.phone).order_by('requested_at').first()
        first_record.expires_at = timezone.now() - timedelta(seconds=1)
        first_record.save(update_fields=['expires_at'])
        self.assertEqual(self.client.post('/api/v1/auth/verify-code/', {
            'phone': self.phone, 'code': first,
        }).status_code, 403)
        self.assertEqual(self.client.post('/api/v1/auth/verify-code/', {
            'phone': self.phone, 'code': second,
        }).status_code, 200)

    def test_session_expiry_invalidates_unexpired_code(self):
        code = self.request_code()
        PhoneVerificationSession.objects.filter(phone=self.phone).update(
            expires_at=timezone.now() - timedelta(seconds=1),
        )
        self.assertEqual(self.client.post('/api/v1/auth/verify-code/', {
            'phone': self.phone, 'code': code,
        }).status_code, 403)
        self.assertFalse(get_user_model().objects.filter(username=self.phone).exists())

    def test_attempt_budget_is_shared_by_all_codes(self):
        with patch('client_auth.services.secrets.randbelow', side_effect=[123456, 654321]):
            self.request_code()
            for _ in range(3):
                self.client.post('/api/v1/auth/verify-code/', {'phone': self.phone, 'code': '000000'})
            PhoneVerificationSession.objects.filter(phone=self.phone).update(
                last_requested_at=timezone.now() - timedelta(seconds=61),
            )
            second = self.request_code()
        for _ in range(2):
            self.client.post('/api/v1/auth/verify-code/', {'phone': self.phone, 'code': '000000'})
        self.assertEqual(PhoneVerificationSession.objects.get(phone=self.phone).attempts, 5)
        self.assertEqual(self.client.post('/api/v1/auth/verify-code/', {
            'phone': self.phone, 'code': second,
        }).status_code, 403)

    def test_new_session_invalidates_old_codes(self):
        with patch('client_auth.services.secrets.randbelow', side_effect=[123456, 654321]):
            first = self.request_code()
            PhoneVerificationSession.objects.filter(phone=self.phone).update(
                expires_at=timezone.now() - timedelta(seconds=1),
                last_requested_at=timezone.now() - timedelta(seconds=61),
            )
            second = self.request_code()
        self.assertEqual(PhoneCode.objects.filter(phone=self.phone).count(), 1)
        self.assertEqual(self.client.post('/api/v1/auth/verify-code/', {
            'phone': self.phone, 'code': first,
        }).status_code, 403)
        self.assertEqual(self.client.post('/api/v1/auth/verify-code/', {
            'phone': self.phone, 'code': second,
        }).status_code, 200)

    def test_completed_session_still_obeys_resend_delay(self):
        first = self.request_code()
        self.assertEqual(self.client.post('/api/v1/auth/verify-code/', {
            'phone': self.phone, 'code': first,
        }).status_code, 200)
        self.assertEqual(self.client.post('/api/v1/auth/request-code/', {
            'phone': self.phone,
        }).status_code, 429)
        session = PhoneVerificationSession.objects.get(phone=self.phone)
        self.assertIsNotNone(session.completed_at)
        PhoneVerificationSession.objects.filter(pk=session.pk).update(
            last_requested_at=timezone.now() - timedelta(seconds=61),
        )
        self.request_code()
        session.refresh_from_db()
        self.assertIsNone(session.completed_at)
        self.assertEqual(PhoneCode.objects.filter(session=session).count(), 1)

    def test_password_login_is_rate_limited_and_never_creates_user(self):
        for _ in range(5):
            response = self.client.post('/api/v1/auth/login-password/', {
                'phone': self.phone, 'password': 'SomePassword#539',
            })
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.data['detail'], 'Неверный номер телефона или пароль.')
        response = self.client.post('/api/v1/auth/login-password/', {
            'phone': self.phone, 'password': 'SomePassword#539',
        })
        self.assertEqual(response.status_code, 429)
        self.assertFalse(get_user_model().objects.filter(username=self.phone).exists())

    def test_existing_password_cannot_be_reset_with_sms_token(self):
        user = get_user_model().objects.create_user(username=self.phone, password='OriginalPassword#539')
        VerifiedPhone.objects.create(user=user, phone=self.phone, verified_at=timezone.now())
        code = self.request_code()
        response = self.client.post('/api/v1/auth/verify-code/', {'phone': self.phone, 'code': code})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['has_password'])
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
        self.assertEqual(self.client.post('/api/v1/auth/set-password/', {
            'new_password': 'ReplacementPassword#539',
        }).status_code, 400)
        user.refresh_from_db()
        self.assertTrue(user.check_password('OriginalPassword#539'))

    @override_settings(DEBUG=False)
    def test_production_does_not_create_or_log_code(self):
        response = self.client.post('/api/v1/auth/request-code/', {'phone': self.phone})
        self.assertEqual(response.status_code, 503)
        self.assertFalse(PhoneCode.objects.exists())


@override_settings(
    DEBUG=True,
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    EMAIL_FROM_ADDRESS='noreply@example.test',
    FRONTEND_BASE_URL='http://localhost:9100',
)
class EmailAuthTests(APITestCase):
    def confirmation_token(self):
        return re.search(r'verify_email=([A-Za-z0-9_-]+)', mail.outbox[-1].body).group(1)

    def test_staff_admin_session_can_confirm_email_then_use_jwt_and_push_profile(self):
        user = get_user_model().objects.create_user(
            username='manager', email='manager@example.test', password='StrongPassphrase#539', is_staff=True,
        )
        login_url = '/api/v1/auth/login-email/'
        credentials = {'email': 'manager@example.test', 'password': 'StrongPassphrase#539'}
        self.assertEqual(self.client.post(login_url, credentials).status_code, 403)
        self.assertTrue(self.client.login(username='manager', password='StrongPassphrase#539'))
        request = self.client.post('/api/v1/auth/email/request-verification/', {'email': user.email})
        self.assertEqual(request.status_code, 202)
        token = self.confirmation_token()
        self.assertIn(f'http://localhost:9100/login#verify_email={token}', mail.outbox[-1].body)
        self.client.logout()
        self.assertEqual(self.client.post('/api/v1/auth/email/verify/', {'token': token}).status_code, 200)
        self.assertEqual(self.client.post('/api/v1/auth/email/verify/', {'token': token}).status_code, 403)
        result = self.client.post(login_url, credentials)
        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.data['is_staff'])
        self.assertTrue(AccessToken(result.data['access'])['is_staff'])
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {result.data['access']}")
        self.assertEqual(self.client.get('/api/v1/auth/me/').status_code, 200)
        self.assertEqual(self.client.put('/api/v1/push/preferences/', {'enabled': True}).status_code, 200)
        self.assertTrue(self.client.get('/api/v1/auth/me/').data['push_enabled'])

    def test_phone_client_sets_password_and_confirms_email_before_email_login(self):
        phone = '+79991234567'
        with self.assertLogs('client_auth.services', level='WARNING') as logs:
            self.assertEqual(self.client.post('/api/v1/auth/request-code/', {'phone': phone}).status_code, 202)
        code = re.search(r'(\d{6})$', logs.output[0]).group(1)
        sms_result = self.client.post('/api/v1/auth/verify-code/', {'phone': phone, 'code': code})
        self.assertEqual(sms_result.status_code, 200)
        self.assertFalse(sms_result.data['is_staff'])
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {sms_result.data['access']}")
        self.assertEqual(self.client.post('/api/v1/auth/set-password/', {'new_password': 'StrongPassphrase#539'}).status_code, 200)
        self.assertEqual(self.client.post('/api/v1/auth/email/request-verification/', {
            'email': 'client@example.test',
        }).status_code, 202)
        token = self.confirmation_token()
        self.client.credentials()
        credentials = {'email': 'client@example.test', 'password': 'StrongPassphrase#539'}
        self.assertEqual(self.client.post('/api/v1/auth/login-email/', credentials).status_code, 403)
        self.assertEqual(self.client.post('/api/v1/auth/email/verify/', {'token': token}).status_code, 200)
        result = self.client.post('/api/v1/auth/login-email/', credentials)
        self.assertEqual(result.status_code, 200)
        self.assertFalse(AccessToken(result.data['access'])['is_staff'])
        self.assertEqual(VerifiedEmail.objects.get(email='client@example.test').user.username, phone)

    def test_email_change_requires_current_password_and_expired_link_fails(self):
        user = get_user_model().objects.create_user(username='client', password='StrongPassphrase#539')
        VerifiedEmail.objects.create(user=user, email='old@example.test', verified_at=timezone.now())
        self.client.force_authenticate(user=user)
        endpoint = '/api/v1/auth/email/request-verification/'
        self.assertEqual(self.client.post(endpoint, {'email': 'new@example.test'}).status_code, 400)
        self.assertEqual(self.client.post(endpoint, {
            'email': 'new@example.test', 'current_password': 'StrongPassphrase#539',
        }).status_code, 202)
        token = self.confirmation_token()
        PendingEmailVerification.objects.filter(user=user).update(expires_at=timezone.now() - timedelta(seconds=1))
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.post('/api/v1/auth/email/verify/', {'token': token}).status_code, 403)
        self.assertEqual(VerifiedEmail.objects.get(user=user).email, 'old@example.test')


class AdminEmailVerificationTests(APITestCase):
    def save_user(self, actor, user, *, verified, email=None):
        request = RequestFactory().post(f'/admin/auth/user/{user.pk}/change/')
        request.user = actor
        form = AdminUserChangeForm({
            'username': user.username,
            'email': email or user.email,
            'is_active': user.is_active,
            'is_staff': user.is_staff,
            'date_joined': user.date_joined,
            'email_verified': verified,
        }, instance=user)
        self.assertTrue(form.is_valid(), form.errors)
        model_admin = admin.site._registry[get_user_model()]
        model_admin.save_model(request, form.save(commit=False), form, change=True)

    def test_superuser_confirms_staff_email_and_existing_password_can_log_in(self):
        User = get_user_model()
        actor = User.objects.create_superuser('root', 'root@example.test', 'AdminPassphrase#539')
        staff = User.objects.create_user('manager', 'Manager@Example.test', 'StaffPassphrase#539', is_staff=True)
        request = RequestFactory().get(f'/admin/auth/user/{staff.pk}/change/')
        request.user = actor
        fieldsets = admin.site._registry[User].get_fieldsets(request, staff)
        self.assertIn('email_verified', str(fieldsets))
        self.client.force_login(actor)
        self.assertContains(self.client.get(f'/admin/auth/user/{staff.pk}/change/'), 'Email подтверждён')
        self.client.logout()
        PendingEmailVerification.objects.create(
            user=staff, email='other@example.test', token_hash='a' * 64,
            created_at=timezone.now(), expires_at=timezone.now() + timedelta(hours=1),
        )
        self.save_user(actor, staff, verified=True)
        self.assertEqual(VerifiedEmail.objects.get(user=staff).email, 'manager@example.test')
        self.assertFalse(PendingEmailVerification.objects.filter(user=staff).exists())
        response = self.client.post('/api/v1/auth/login-email/', {
            'email': 'manager@example.test', 'password': 'StaffPassphrase#539',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['is_staff'])
        self.save_user(actor, staff, verified=False)
        self.assertFalse(VerifiedEmail.objects.filter(user=staff).exists())

    def test_only_superuser_can_use_checkbox_and_email_cannot_be_claimed_twice(self):
        User = get_user_model()
        actor = User.objects.create_user('operator', 'operator@example.test', 'OperatorPassphrase#539', is_staff=True)
        target = User.objects.create_user('manager', 'manager@example.test', 'StaffPassphrase#539', is_staff=True)
        owner = User.objects.create_user('owner', 'taken@example.test', 'OwnerPassphrase#539')
        VerifiedEmail.objects.create(user=owner, email='taken@example.test', verified_at=timezone.now())
        request = RequestFactory().get(f'/admin/auth/user/{target.pk}/change/')
        request.user = actor
        self.assertNotIn('email_verified', str(admin.site._registry[User].get_fieldsets(request, target)))
        self.save_user(actor, target, verified=True)
        self.assertFalse(VerifiedEmail.objects.filter(user=target).exists())
        form = AdminUserChangeForm({
            'username': target.username,
            'email': 'taken@example.test',
            'is_active': True,
            'is_staff': True,
            'date_joined': target.date_joined,
            'email_verified': True,
        }, instance=target)
        self.assertFalse(form.is_valid())
        self.assertIn('email_verified', form.errors)
        self.assertFalse(VerifiedEmail.objects.filter(user=target).exists())
