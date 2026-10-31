"""Attach downloaded Tilda photos to categories and service Pages via Filer."""

import hashlib
from pathlib import Path

try:
    from hashlib import file_digest
except ImportError:  # Python 3.10
    def file_digest(fileobj, digest, /, *, _bufsize=1024 * 1024):
        hashobj = hashlib.new(digest)
        while True:
            chunk = fileobj.read(_bufsize)
            if not chunk:
                break
            hashobj.update(chunk)
        return hashobj

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from filer.models import Image as FilerImage

from pages.models import PagePicture
from services.models import Service, ServiceCategory
from services.tilda_images import (
    CATEGORY_IMAGES, load_images, match_image, nail_group_card, old_nail_service_card,
)


def source_file(root, relative):
    source = (root / relative).resolve()
    return source if source.is_relative_to(root) and source.is_file() else None


def get_or_upload(source, relative, title, uploaded):
    image = uploaded.get(relative)
    if image is not None:
        return image
    with source.open('rb') as handle:
        digest = file_digest(handle, 'sha1').hexdigest()
    image = FilerImage.objects.filter(sha1=digest).first()
    if image is None:
        with source.open('rb') as handle:
            image = FilerImage(original_filename=source.name, name=f'Tilda: {title}'[:255],
                               file=File(handle, name=source.name))
            image.save()
    uploaded[relative] = image
    return image


class Command(BaseCommand):
    help = 'Загрузить фото категорий и услуг Tilda через Filer; фотографии услуг прикрепить к Page.'

    def add_arguments(self, parser):
        parser.add_argument('--source-path', required=True,
                            help='Каталог tilda_assets; путь может отличаться на продакшене.')
        parser.add_argument('--apply', action='store_true',
                            help='Применить найденные соответствия. Без флага команда только показывает план.')

    def handle(self, *args, **options):
        root = Path(options['source_path']).expanduser().resolve()
        if not root.is_dir():
            raise CommandError(f'Каталог фотографий не найден: {root}')

        images = load_images()
        category_stats = {'ready': 0, 'created': 0, 'existing': 0, 'missing_file': 0}
        stats = {'ready': 0, 'created': 0, 'existing': 0, 'missing_page': 0,
                 'unmatched': 0, 'missing_file': 0, 'group_ready': 0,
                 'group_created': 0, 'group_existing': 0, 'cleanup': 0}
        uploaded = {}

        for category in ServiceCategory.objects.filter(code__in=CATEGORY_IMAGES, is_active=True).select_related('image'):
            if category.image_id:
                category_stats['existing'] += 1
                continue
            relative = CATEGORY_IMAGES[category.code]
            source = source_file(root, relative)
            if source is None:
                category_stats['missing_file'] += 1
                self.stdout.write(self.style.WARNING(f'Нет файла категории {category.title}: {relative}'))
                continue
            category_stats['ready'] += 1
            if not options['apply'] or options['verbosity'] >= 2:
                self.stdout.write(f'Категория {category.title} → {relative}')
            if options['apply']:
                category.image = get_or_upload(source, relative, category.title, uploaded)
                category.save(update_fields=['image'])
                category_stats['created'] += 1

        nail_category = ServiceCategory.objects.filter(code='nails', is_active=True).select_related('page').first()
        if nail_category and nail_category.page_id:
            nail_groups = dict.fromkeys(Service.objects.filter(category=nail_category, is_active=True)
                                        .order_by('weight', 'id').values_list('group_title', flat=True))
            for position, group_title in enumerate(nail_groups):
                card = nail_group_card(group_title, images)
                if not card:
                    continue
                if PagePicture.objects.filter(page=nail_category.page, alt=group_title).exists():
                    stats['group_existing'] += 1
                    continue
                source = source_file(root, card['asset'])
                if source is None:
                    stats['missing_file'] += 1
                    self.stdout.write(self.style.WARNING(f'Нет файла группы {group_title}: {card["asset"]}'))
                    continue
                stats['group_ready'] += 1
                if not options['apply'] or options['verbosity'] >= 2:
                    self.stdout.write(f'Группа {group_title} → {card["asset"]}')
                if options['apply']:
                    image = get_or_upload(source, card['asset'], card['title'], uploaded)
                    PagePicture.objects.create(page=nail_category.page, image=image,
                                               alt=group_title, position=position)
                    stats['group_created'] += 1

        services = Service.objects.filter(category__code__in=images, is_active=True).select_related(
            'category', 'page').prefetch_related('page__pictures__image').order_by('category__code', 'weight', 'id')

        for service in services:
            if not service.page_id:
                stats['missing_page'] += 1
                self.stdout.write(f'Нет Page: #{service.pk} {service.title}')
                continue
            if service.category.code == 'nails':
                card = old_nail_service_card(service, images)
                source = source_file(root, card['asset']) if card else None
                if source:
                    with source.open('rb') as handle:
                        digest = file_digest(handle, 'sha1').hexdigest()
                    for picture in service.page.pictures.all():
                        if (picture.image_id and picture.image.sha1 == digest and
                                picture.image.name.startswith('Tilda: ') and
                                picture.alt == service.title[:255] and picture.position == 0):
                            stats['cleanup'] += 1
                            if not options['apply'] or options['verbosity'] >= 2:
                                self.stdout.write(f'Убрать групповое фото с услуги #{service.pk} {service.title}')
                            if options['apply']:
                                picture.delete()
                            break
                # Tilda has no individual nail-service photos; leave manually added images intact.
                continue
            if service.page.pictures.exists():
                stats['existing'] += 1
                continue

            card, reason = match_image(service, images)
            if not card:
                stats['unmatched'] += 1
                if options['verbosity'] >= 2:
                    self.stdout.write(f'Без фото: #{service.pk} {service.title} — {reason}')
                continue

            source = source_file(root, card['asset'])
            if source is None:
                stats['missing_file'] += 1
                self.stdout.write(self.style.WARNING(f'Нет файла: {card["asset"]} для #{service.pk} {service.title}'))
                continue

            stats['ready'] += 1
            if options['verbosity'] >= 2 or not options['apply']:
                self.stdout.write(f'#{service.pk} {service.title} → {card["asset"]} ({reason})')
            if not options['apply']:
                continue

            image = get_or_upload(source, card['asset'], card['title'], uploaded)
            PagePicture.objects.create(page=service.page, image=image,
                                       alt=service.title[:255], position=0)
            stats['created'] += 1

        verb = 'Добавлено' if options['apply'] else 'Готово к добавлению'
        self.stdout.write(self.style.SUCCESS(
            f'Категории — {verb.lower()}: {category_stats["created"] if options["apply"] else category_stats["ready"]}; '
            f'уже есть изображения: {category_stats["existing"]}; '
            f'нет файла: {category_stats["missing_file"]}.'
        ))
        self.stdout.write(self.style.SUCCESS(
            f'Услуги — {verb}: {stats["created"] if options["apply"] else stats["ready"]}; '
            f'уже есть изображения: {stats["existing"]}; '
            f'без Page: {stats["missing_page"]}; '
            f'без однозначного фото: {stats["unmatched"]}; '
            f'нет файла: {stats["missing_file"]}.'
        ))
        self.stdout.write(self.style.SUCCESS(
            f'Ногтевые группы — {verb.lower()}: '
            f'{stats["group_created"] if options["apply"] else stats["group_ready"]}; '
            f'уже есть: {stats["group_existing"]}; '
            f'ошибочных фото услуг к удалению: {stats["cleanup"]}.'
        ))
