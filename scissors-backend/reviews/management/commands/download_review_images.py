
from django.core.management.base import BaseCommand
from django.db.models import Prefetch

from reviews.images import fetch_review_image
from reviews.models import Review, ReviewImage


class Command(BaseCommand):
    help = 'Скачать фотографии отзывов Rewio в django-filer'

    def add_arguments(self, parser):
        parser.add_argument(
            '--review-id',
            type=int,
            help='Обработать только отзыв с указанным ID в Django',
        )

    def handle(self, *args, **options):
        queryset = Review.objects.filter(has_images=True).exclude(images=[])

        if options['review_id']:
            queryset = queryset.filter(pk=options['review_id'])

        queryset = queryset.prefetch_related(
            Prefetch(
                'local_images',
                queryset=ReviewImage.objects.select_related('image'),
            )
        )

        downloaded = 0
        failed = 0
        skipped = 0

        for review in queryset.iterator(chunk_size=100):
            entries = review.images or []

            for position, entry in enumerate(entries):
                if not isinstance(entry, dict):
                    continue

                image_url = entry.get('image') or ''
                preview_url = entry.get('preview') or ''
                urls = list(dict.fromkeys(
                    url for url in (image_url, preview_url) if url
                ))

                if not urls:
                    continue

                # Уже сохранённое фото не скачиваем повторно.
                existing_urls = set(
                    ReviewImage.objects.filter(
                        review=review,
                        source_url__in=urls,
                    ).values_list('source_url', flat=True)
                )
                if existing_urls:
                    skipped += 1
                    continue

                saved = None
                for url in urls:
                    saved = fetch_review_image(review, url, position)
                    if saved:
                        downloaded += 1
                        break

                if not saved:
                    failed += 1
                    self.stderr.write(
                        f'Не удалось скачать фото отзыва Django ID={review.pk}'
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f'Завершено. Загружено: {downloaded}; '
                f'пропущено: {skipped}; ошибок: {failed}.'
            )
        )
