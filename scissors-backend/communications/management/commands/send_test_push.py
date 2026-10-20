from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from communications.push import send_to_staff


class Command(BaseCommand):
    help = 'Отправить тестовый Web Push активным суперпользователям с включёнными уведомлениями.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--message',
            default='Проверка push-уведомлений Scissors Studio.',
            help='Текст тестового уведомления (до 200 символов).',
        )

    def handle(self, *args, **options):
        message = options['message'].strip()
        if not message or len(message) > 200:
            raise CommandError('Сообщение должно содержать от 1 до 200 символов.')

        required_settings = (
            'WEB_PUSH_VAPID_PUBLIC_KEY',
            'WEB_PUSH_VAPID_PRIVATE_KEY',
            'WEB_PUSH_VAPID_SUBJECT',
        )
        missing = [name for name in required_settings if not getattr(settings, name)]
        if missing:
            raise CommandError('Не заданы переменные окружения: ' + ', '.join(missing))

        result = send_to_staff(
            'Тестовое уведомление Scissors Studio',
            message,
            '/admin/',
            superusers_only=True,
        )
        if result.unavailable_reason:
            raise CommandError(f'Web Push недоступен: {result.unavailable_reason}')
        if not result.attempted:
            raise CommandError('Нет активных push-подписок суперпользователей с включёнными уведомлениями.')

        self.stdout.write(
            f'Попыток: {result.attempted}; принято push-сервисом: {result.accepted}; '
            f'ошибок: {result.failed}; удалено недействительных подписок: {result.removed}.'
        )
        if result.failed or result.removed:
            raise CommandError('Часть уведомлений не принята. Подробности без секретов — в журнале backend.')
