import logging

from django.conf import settings
from django.core.mail import send_mail


logger = logging.getLogger(__name__)


def notify_feedback_email(feedback):
    recipient = settings.FEEDBACK_RECIPIENT_EMAIL
    if not recipient or not settings.EMAIL_FROM_ADDRESS or not settings.EMAIL_HOST:
        logger.warning('Feedback email not sent: SMTP configuration is incomplete')
        return

    body = '\n'.join((
        f'Имя: {feedback.name}',
        f'Контакт: {feedback.phone}',
        '',
        'Сообщение:',
        feedback.message,
    ))

    try:
        send_mail(
            subject='Новое обращение через сайт Scissors Studio',
            message=body,
            from_email=settings.EMAIL_FROM_ADDRESS,
            recipient_list=[recipient],
            fail_silently=False,
        )
    except Exception as exc:
        logger.warning(
            'Feedback email delivery failed: error_type=%s errno=%s',
            type(exc).__name__,
            getattr(exc, 'errno', None),
        )
