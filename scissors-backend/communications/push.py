import base64
import binascii
import json
import logging
import os
import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.urls import reverse
from .models import PushSubscription

logger = logging.getLogger(__name__)


def push_configuration_error():
    """Return a safe reason code, never a key, subject, or subscription URL."""
    public = settings.WEB_PUSH_VAPID_PUBLIC_KEY
    private = settings.WEB_PUSH_VAPID_PRIVATE_KEY
    subject = settings.WEB_PUSH_VAPID_SUBJECT
    if not public or not private or not subject:
        return 'missing_vapid_setting'

    try:
        if not re.fullmatch(r'[A-Za-z0-9_-]+={0,2}', public):
            return 'invalid_public_key'
        public_bytes = base64.urlsafe_b64decode(public + '=' * (-len(public) % 4))
        if len(public_bytes) != 65 or public_bytes[0] != 4:
            return 'invalid_public_key'
    except (ValueError, binascii.Error):
        return 'invalid_public_key'

    if subject.lower().startswith('mailto:'):
        try:
            validate_email(subject[7:])
        except ValidationError:
            return 'invalid_vapid_subject'
    else:
        try:
            url = urlsplit(subject)
            valid_origin = (
                url.scheme == 'https' and bool(url.hostname) and not url.username
                and not url.password and subject[8:] == url.netloc
                and subject[:8].lower() == 'https://'
                and (url.port is None or url.port > 0)
            )
        except ValueError:
            valid_origin = False
        if not valid_origin:
            return 'invalid_vapid_subject'

    # pywebpush accepts a PEM file path, but treats a missing file as an
    # encoded key string. Catch that case before sending a notification.
    if private.startswith('/') or private.endswith('.pem'):
        if not os.path.isfile(private):
            return 'private_key_file_missing_or_inaccessible'
        if not os.access(private, os.R_OK):
            return 'private_key_file_unreadable'
    return None


def push_configured():
    return push_configuration_error() is None


def _error_type(exc):
    return type(exc).__name__


def _error_number(exc):
    return exc.errno if isinstance(exc, OSError) else None


@dataclass
class PushDeliveryResult:
    attempted: int = 0
    accepted: int = 0
    failed: int = 0
    removed: int = 0
    unavailable_reason: str | None = None


def send_to_staff(title, body, url, *, superusers_only=False, required_permission=None):
    """Send one event to each enabled staff browser; keep delivery errors private."""
    result = PushDeliveryResult()
    config_error = push_configuration_error()
    if config_error:
        logger.warning('Web Push unavailable: reason=%s', config_error)
        result.unavailable_reason = config_error
        return result
    try:
        from pywebpush import WebPushException, webpush
    except ImportError:
        logger.warning('Web Push library is unavailable.')
        result.unavailable_reason = 'library_unavailable'
        return result
    subscriptions = PushSubscription.objects.select_related('user').filter(
        user__is_active=True,
        user__is_staff=True,
        user__push_preference__enabled=True,
    )
    if superusers_only:
        subscriptions = subscriptions.filter(user__is_superuser=True)
    payload = json.dumps({'title': title, 'body': body, 'url': url}, ensure_ascii=False)
    for subscription in subscriptions.iterator():
        if required_permission and not subscription.user.has_perm(required_permission):
            continue
        result.attempted += 1
        subscription_id = subscription.pk
        provider = None
        try:
            provider = urlsplit(subscription.endpoint).hostname
            response = webpush(
                subscription_info={
                    'endpoint': subscription.endpoint,
                    'keys': {'p256dh': subscription.p256dh, 'auth': subscription.auth},
                },
                data=payload,
                vapid_private_key=settings.WEB_PUSH_VAPID_PRIVATE_KEY,
                vapid_claims={'sub': settings.WEB_PUSH_VAPID_SUBJECT},
                timeout=5,
            )
            result.accepted += 1
            logger.debug(
                'Push accepted: subscription_id=%s user_id=%s provider=%s status=%s',
                subscription_id, subscription.user_id, provider, getattr(response, 'status_code', None),
            )
        except WebPushException as exc:
            if exc.status_code in (404, 410):
                subscription.delete()
                result.removed += 1
                logger.warning(
                    'Expired push subscription removed: subscription_id=%s user_id=%s provider=%s status=%s',
                    subscription_id, subscription.user_id, provider, exc.status_code,
                )
            else:
                result.failed += 1
                logger.warning(
                    'Push delivery failed: subscription_id=%s user_id=%s provider=%s '
                    'error_type=%s status=%s phase=%s',
                    subscription_id, subscription.user_id, provider, _error_type(exc), exc.status_code,
                    'provider_response' if exc.status_code is not None else 'before_http',
                )
        except Exception as exc:
            result.failed += 1
            logger.warning(
                'Push delivery failed: subscription_id=%s user_id=%s provider=%s '
                'error_type=%s errno=%s',
                subscription_id, subscription.user_id, provider, _error_type(exc), _error_number(exc),
            )
    if not result.attempted:
        logger.warning('No eligible staff push subscriptions.')
    return result


def notify_new_feedback(feedback):
    try:
        url = reverse('admin:communications_feedbackrequest_change', args=[feedback.pk])
        send_to_staff('Новое обращение', f'{feedback.name}: новое обращение', url,
                      required_permission='communications.view_feedbackrequest')
    except Exception as exc:
        logger.warning(
            'Feedback push dispatch failed: feedback_id=%s error_type=%s errno=%s',
            feedback.pk, _error_type(exc), _error_number(exc),
        )
