"""
Заглушка отправки push. Реальная реализация появится вместе с мобильным
приложением на Quasar (Capacitor + @capacitor/push-notifications) — тогда
у пользователя будет сохранённый device token (FCM для Android, APNs для
iOS через FCM), и здесь будет вызов Firebase Admin SDK / HTTP v1 API.

Пока — просто пишет в лог, чтобы send_booking_reminders можно было
протестировать и подключить уже сейчас, не блокируясь на мобильной части.
"""

import logging

logger = logging.getLogger(__name__)


def send_push_to_user(user, text: str):
    # TODO: заменить на реальную отправку через Firebase Cloud Messaging,
    # когда появится модель DeviceToken (user -> fcm_token) из мобильного приложения.
    logger.info('PUSH -> %s: %s', user, text)
