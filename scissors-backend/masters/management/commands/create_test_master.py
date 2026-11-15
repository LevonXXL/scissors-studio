"""Create an admin-accessible master sandbox hidden from the public site."""

import argparse
import secrets

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from masters.constants import TEST_MASTER_SLUG_PREFIX
from masters.models import Master
from pages.models import Page


USERNAME_PREFIX = 'test_master_sandbox_'


class Command(BaseCommand):
    help = 'Создать скрытого тестового мастера и пользователя для входа в админку.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--idempotent', action=argparse.BooleanOptionalAction, default=True,
            help='По умолчанию повторно использовать существующего тестового мастера. '
                 'Для новой пары укажите --no-idempotent.',
        )

    def handle(self, *args, **options):
        if options['idempotent']:
            existing = (Master.objects.filter(slug__startswith=TEST_MASTER_SLUG_PREFIX)
                        .select_related('user').order_by('pk').first())
            if existing:
                self.stdout.write(self.style.WARNING(
                    f'Тестовый мастер уже существует: ID {existing.pk}, '
                    f'пользователь {existing.user.username if existing.user else "не привязан"}. '
                    'Новая запись не создана.'
                ))
                return

        User = get_user_model()
        index = 1
        while (Master.objects.filter(slug=f'{TEST_MASTER_SLUG_PREFIX}{index}').exists()
               or User.objects.filter(username=f'{USERNAME_PREFIX}{index}').exists()
               or Page.objects.filter(url_path=f'{TEST_MASTER_SLUG_PREFIX}{index}').exists()):
            index += 1

        username = f'{USERNAME_PREFIX}{index}'
        slug = f'{TEST_MASTER_SLUG_PREFIX}{index}'
        name = f'Тестовый мастер (песочница {index})'
        password = secrets.token_urlsafe(24)

        with transaction.atomic():
            user = User.objects.create_user(
                username=username, password=password, is_staff=True, is_active=True,
            )
            page = Page.objects.create(title=name, url=slug, is_published=False)
            master = Master.objects.create(
                name=name, slug=slug, user=user, page=page, is_active=False,
            )

        self.stdout.write(self.style.SUCCESS(
            f'Создан тестовый мастер ID {master.pk}. '
            'Он не показывается на сайте; страница не опубликована.'
        ))
        self.stdout.write(f'Логин для админки: {username}')
        self.stdout.write(f'Пароль (показывается только сейчас): {password}')
