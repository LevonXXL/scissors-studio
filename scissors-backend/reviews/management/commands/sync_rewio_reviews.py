from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_datetime

from reviews.client import RewioClient, RewioError, SOURCE_ID_MAP
from reviews.models import Review
from salons.models import Salon
from sync.images import fetch_and_store_image


class Command(BaseCommand):
    help = (
        'Загружает отзывы из Rewio для салонов с заполненным rewio_object_id. '
        'Поддерживает пагинацию (по умолчанию загружает все страницы).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--salon-id', type=int, default=None,
            help='Синхронизировать только конкретный салон (по id).',
        )
        parser.add_argument(
            '--limit', type=int, default=100,
            help='Кол-во отзывов на запрос (по умолчанию 100, максимум у Rewio).',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Показать что будет сделано, без реальных изменений.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        limit = options['limit']
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN — изменения не будут применены'))

        client = RewioClient()

        salons = Salon.objects.filter(rewio_object_id__gt='')
        if options['salon_id']:
            salons = salons.filter(id=options['salon_id'])

        if not salons.exists():
            self.stdout.write(self.style.WARNING('Нет салонов с rewio_object_id.'))
            return

        total_created = 0
        total_updated = 0

        for salon in salons:
            self.stdout.write(f'\nСалон «{salon}» (rewio_object_id={salon.rewio_object_id}):')
            offset = 0
            salon_created = 0
            salon_updated = 0

            while True:
                try:
                    result = client.get_reviews(
                        object_id=salon.rewio_object_id,
                        limit=limit,
                        offset=offset,
                    )
                except RewioError as exc:
                    self.stderr.write(self.style.ERROR(f'  Ошибка: {exc}'))
                    break

                reviews_data = result.get('data', [])
                if not reviews_data:
                    break

                for r in reviews_data:
                    created, updated = self._sync_review(salon, r, dry_run)
                    salon_created += created
                    salon_updated += updated

                total_reviews = result.get('total', 0)
                offset += limit
                self.stdout.write(f'  Загружено {offset}/{total_reviews}...')

                if not result.get('has_next'):
                    break

            self.stdout.write(
                f'  ✓ {salon_created} новых, {salon_updated} обновлено'
            )
            total_created += salon_created
            total_updated += salon_updated

        self.stdout.write(self.style.SUCCESS(
            f'\nГотово: {total_created} новых, {total_updated} обновлено.'
        ))

    def _sync_review(self, salon, r: dict, dry_run: bool) -> tuple[int, int]:
        """Создаёт или обновляет один отзыв. Возвращает (created, updated) — 0 или 1."""
        rewio_id = r['id']
        review_date = parse_datetime(r.get('review_date') or '')
        reply_date = parse_datetime(r.get('reply_date') or '') or None

        if dry_run:
            return (1, 0)

        # Сохраняем изображения в filer; повторные прогоны используют SyncedImage.
        images = []
        for img in r.get('images') or []:
            if not isinstance(img, dict):
                continue
            full_url = img.get('image') or ''
            preview_url = img.get('preview') or ''
            image = None
            for url in (full_url, preview_url):
                if url and url.startswith(('https://', 'http://')):
                    image = fetch_and_store_image(url, folder_name='reviews/photos')
                if image:
                    images.append({'preview': image.url, 'image': image.url})
                    break

        # Видео (пока просто сохраняем как есть)
        videos = r.get('videos', [])

        # Маппинг source_id
        source = SOURCE_ID_MAP.get(r.get('source_id', 0), Review.SOURCE_OTHER)

        defaults = {
            'rewio_link_id': r.get('link_id'),
            'source': source,
            'author': r.get('author', '') or '',
            'text': r.get('text', '') or '',
            'rating': r.get('rating'),
            'review_date': review_date,
            'review_url': r.get('review_url') or '',
            'reply_text': r.get('reply_text', '') or '',
            'reply_date': reply_date,
            'has_images': bool(images),
            'images': images,
            'has_videos': r.get('has_videos', False),
            'videos': videos,
        }

        obj, created = Review.objects.update_or_create(
            salon=salon,
            rewio_review_id=rewio_id,
            defaults=defaults,
        )
        return (int(created), int(not created))
