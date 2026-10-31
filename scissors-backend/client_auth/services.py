import logging
import re
import secrets
from datetime import timedelta
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone
from django.utils.crypto import salted_hmac
from rest_framework.exceptions import APIException, AuthenticationFailed, Throttled, ValidationError as DRFValidationError
from rest_framework_simplejwt.tokens import AccessToken

from .models import AuthRateLimit, PendingEmailVerification, PhoneCode, PhoneVerificationSession, VerifiedEmail, VerifiedPhone

logger = logging.getLogger(__name__)
CODE_TTL = timedelta(minutes=5)
SESSION_TTL = timedelta(minutes=30)
RESEND_DELAY = timedelta(seconds=60)
MAX_CODE_ATTEMPTS = 5
INVALID_CODE = 'Неверный или просроченный код.'
INVALID_LOGIN = 'Неверный номер телефона или пароль.'
INVALID_EMAIL_LOGIN = 'Неверный email или пароль.'
EMAIL_TOKEN_TTL = timedelta(hours=24)


class EmailDeliveryUnavailable(APIException):
    status_code = 503
    default_detail = 'Подтверждение email временно недоступно.'


def normalize_phone(value):
    if not isinstance(value, str):
        raise ValidationError('Укажите номер телефона.')
    digits = re.sub(r'[\s()\-]', '', value)
    if digits.startswith('+7'):
        digits = digits[2:]
    elif digits.startswith('8') and len(digits) == 11:
        digits = digits[1:]
    elif digits.startswith('7') and len(digits) == 11:
        digits = digits[1:]
    if not re.fullmatch(r'9\d{9}', digits):
        raise ValidationError('Укажите российский мобильный номер телефона.')
    return '+7' + digits


def client_ip(request):
    # REMOTE_ADDR comes from the trusted web server; never trust client-supplied X-Forwarded-For.
    return request.META.get('REMOTE_ADDR') or 'unknown'


def count_attempt(scope, identity, limit, window_seconds):
    key = salted_hmac('client-auth-rate', f'{scope}:{identity}').hexdigest()
    now = timezone.now()
    with transaction.atomic():
        bucket, _ = AuthRateLimit.objects.select_for_update().get_or_create(
            key=key, defaults={'window_start': now, 'count': 0},
        )
        elapsed = (now - bucket.window_start).total_seconds()
        if elapsed >= window_seconds:
            bucket.window_start = now
            bucket.count = 0
            elapsed = 0
        if bucket.count >= limit:
            raise Throttled(wait=max(1, int(window_seconds - elapsed)))
        bucket.count += 1
        bucket.save(update_fields=['window_start', 'count'])


def throttle(request, action, phone, phone_limit, ip_limit, window_seconds):
    count_attempt(action + ':ip', client_ip(request), ip_limit, window_seconds)
    count_attempt(action + ':phone', phone, phone_limit, window_seconds)


def deliver_code(phone, code):
    """Delivery seam for a future YCLIENTS SMS adapter; never log in production."""
    if settings.DEBUG:
        logger.warning('Development SMS code for %s: %s', phone, code)
        return True
    return False


def request_code(request, phone):
    if not settings.DEBUG:
        return False
    throttle(request, 'request', phone, 3, 30, 15 * 60)
    with transaction.atomic():
        initial_now = timezone.now()
        session, created = PhoneVerificationSession.objects.select_for_update().get_or_create(
            phone=phone,
            defaults={
                'started_at': initial_now,
                'expires_at': initial_now + SESSION_TTL,
                'last_requested_at': initial_now - RESEND_DELAY,
            },
        )
        now = timezone.now()
        if not created and (session.completed_at or session.expires_at <= now):
            session.codes.all().delete()
            session.started_at = now
            session.expires_at = now + SESSION_TTL
            session.attempts = 0
            session.completed_at = None
        if session.attempts >= MAX_CODE_ATTEMPTS:
            raise Throttled(wait=max(1, int((session.expires_at - now).total_seconds())))
        if now - session.last_requested_at < RESEND_DELAY:
            raise Throttled(wait=max(1, int((RESEND_DELAY - (now - session.last_requested_at)).total_seconds())))
        code = f'{secrets.randbelow(1_000_000):06d}'
        code_hash = make_password(code)
        issued_at = timezone.now()
        PhoneCode.objects.create(
            phone=phone,
            session=session,
            code_hash=code_hash,
            requested_at=issued_at,
            expires_at=issued_at + CODE_TTL,
        )
        session.last_requested_at = issued_at
        session.save()
    return deliver_code(phone, code)


def verify_code(request, phone, code, target_user=None):
    throttle(request, 'verify', phone, 10, 50, 15 * 60)
    error = False
    user = None
    with transaction.atomic():
        session = PhoneVerificationSession.objects.select_for_update().filter(phone=phone).first()
        now = timezone.now()
        if not session or session.completed_at or session.expires_at <= now or session.attempts >= MAX_CODE_ATTEMPTS:
            error = True
        else:
            matched_code = next(
                (candidate for candidate in session.codes.filter(consumed_at__isnull=True, expires_at__gt=now)
                 if check_password(code, candidate.code_hash)),
                None,
            )
            accepted_at = timezone.now()
            if session.expires_at <= accepted_at:
                error = True
            elif matched_code is None or matched_code.expires_at <= accepted_at:
                PhoneVerificationSession.objects.filter(
                    pk=session.pk, completed_at__isnull=True,
                    expires_at__gt=accepted_at, attempts__lt=MAX_CODE_ATTEMPTS,
                ).update(attempts=F('attempts') + 1)
                error = True
            else:
                claimed = PhoneVerificationSession.objects.filter(
                    pk=session.pk, completed_at__isnull=True,
                    expires_at__gt=accepted_at, attempts__lt=MAX_CODE_ATTEMPTS,
                ).update(completed_at=accepted_at)
                if not claimed:
                    error = True
                else:
                    matched_code.consumed_at = accepted_at
                    matched_code.save(update_fields=['consumed_at'])
                    identity = VerifiedPhone.objects.select_related('user').filter(phone=phone).first()
                    if target_user is not None:
                        User = get_user_model()
                        user = User.objects.select_for_update().get(pk=target_user.pk)
                        if (not user.is_active or
                                (identity and identity.user_id != user.pk) or
                                User.objects.filter(username=phone).exclude(pk=user.pk).exists()):
                            error = True
                        elif identity:
                            identity.verified_at = accepted_at
                            identity.save(update_fields=['verified_at'])
                        else:
                            VerifiedPhone.objects.create(user=user, phone=phone, verified_at=accepted_at)
                    elif identity:
                        user = identity.user
                        if not user.is_active:
                            error = True
                        else:
                            identity.verified_at = accepted_at
                            identity.save(update_fields=['verified_at'])
                    else:
                        User = get_user_model()
                        # Never attach a pre-existing account to a number it did not previously verify.
                        if User.objects.filter(username=phone).exists():
                            error = True
                        else:
                            user = User(username=phone, is_staff=False, is_superuser=False)
                            user.set_unusable_password()
                            user.save()
                            VerifiedPhone.objects.create(user=user, phone=phone, verified_at=accepted_at)
    if error:
        raise AuthenticationFailed(INVALID_CODE)
    return user


def password_login(request, phone, password):
    throttle(request, 'password', phone, 5, 30, 15 * 60)
    identity = VerifiedPhone.objects.select_related('user').filter(phone=phone).first()
    user = identity.user if identity else None
    authenticated = authenticate(request=request, username=user.get_username() if user else phone, password=password)
    if not user or authenticated != user or not user.is_active or not user.has_usable_password():
        raise AuthenticationFailed(INVALID_LOGIN)
    return user


def email_password_login(request, email, password):
    throttle(request, 'email-password', email, 5, 30, 15 * 60)
    identity = VerifiedEmail.objects.select_related('user').filter(email=email).first()
    user = identity.user if identity else None
    authenticated = authenticate(request=request, username=user.get_username() if user else email, password=password)
    if not user or authenticated != user or not user.is_active or not user.has_usable_password():
        raise AuthenticationFailed(INVALID_EMAIL_LOGIN)
    return user


def request_email_verification(request, user, email, current_password=''):
    count_attempt('email-request:user', str(user.pk), 3, 60 * 60)
    count_attempt('email-request:ip', client_ip(request), 20, 60 * 60)
    current = VerifiedEmail.objects.filter(user=user).first()
    if current and current.email == email:
        PendingEmailVerification.objects.filter(user=user).delete()
        return
    if current and not user.check_password(current_password):
        raise DRFValidationError({'current_password': 'Для смены email укажите текущий пароль.'})
    if VerifiedEmail.objects.filter(email=email).exclude(user=user).exists():
        return
    unsafe_backends = (
        'django.core.mail.backends.console.EmailBackend',
        'django.core.mail.backends.filebased.EmailBackend',
        'django.core.mail.backends.locmem.EmailBackend',
        'django.core.mail.backends.dummy.EmailBackend',
    )
    frontend_url = urlsplit(settings.FRONTEND_BASE_URL)
    if (not frontend_url.hostname or frontend_url.username or frontend_url.password or
            frontend_url.query or frontend_url.fragment or
            (not settings.DEBUG and frontend_url.scheme != 'https') or
            not settings.EMAIL_FROM_ADDRESS or
            (not settings.DEBUG and (not settings.EMAIL_HOST or settings.EMAIL_BACKEND in unsafe_backends))):
        raise EmailDeliveryUnavailable()
    token = secrets.token_urlsafe(32)
    token_hash = salted_hmac('client-auth-email', token).hexdigest()
    now = timezone.now()
    link = f'{settings.FRONTEND_BASE_URL.rstrip("/")}/login?verify_email={token}'
    try:
        with transaction.atomic():
            PendingEmailVerification.objects.update_or_create(
                user=user,
                defaults={
                    'email': email,
                    'token_hash': token_hash,
                    'created_at': now,
                    'expires_at': now + EMAIL_TOKEN_TTL,
                },
            )
            delivered = send_mail(
                'Подтвердите email для Scissors Studio',
                f'Чтобы подтвердить адрес электронной почты, откройте ссылку и нажмите кнопку подтверждения: {link}\n\nСсылка действует 24 часа.',
                settings.EMAIL_FROM_ADDRESS,
                [email],
                fail_silently=False,
            )
            if delivered != 1:
                raise EmailDeliveryUnavailable()
    except EmailDeliveryUnavailable:
        raise
    except Exception:
        raise EmailDeliveryUnavailable() from None


def verify_email_token(token):
    token_hash = salted_hmac('client-auth-email', token).hexdigest()
    try:
        with transaction.atomic():
            pending = PendingEmailVerification.objects.select_for_update().filter(token_hash=token_hash).first()
            now = timezone.now()
            if not pending or pending.expires_at <= now:
                raise AuthenticationFailed('Ссылка подтверждения недействительна или истекла.')
            if VerifiedEmail.objects.filter(email=pending.email).exclude(user=pending.user).exists():
                raise AuthenticationFailed('Ссылка подтверждения недействительна или истекла.')
            VerifiedEmail.objects.update_or_create(
                user=pending.user,
                defaults={'email': pending.email, 'verified_at': now},
            )
            user = pending.user
            user.email = pending.email
            user.save(update_fields=['email'])
            pending.delete()
    except IntegrityError as exc:
        raise AuthenticationFailed('Ссылка подтверждения недействительна или истекла.') from exc


def profile_response(user):
    from communications.models import PushPreference

    phones = list(VerifiedPhone.objects.filter(user=user).order_by('pk').values_list('phone', flat=True))
    email = VerifiedEmail.objects.filter(user=user).values_list('email', flat=True).first() or ''
    pending_email = PendingEmailVerification.objects.filter(user=user).values_list('email', flat=True).first() or ''
    return {
        'is_staff': bool(user.is_staff),
        'phone': phones[0] if phones else '',
        'phones': phones,
        'email': email,
        'pending_email': pending_email,
        'has_password': user.has_usable_password(),
        'push_enabled': PushPreference.objects.filter(user=user, enabled=True).exists(),
    }


def auth_response(user):
    token = AccessToken.for_user(user)
    token['is_staff'] = bool(user.is_staff)
    return {'access': str(token), **profile_response(user)}
