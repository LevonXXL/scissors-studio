from unittest.mock import patch
from types import SimpleNamespace

from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from salons.models import Salon

from .models import Review
from .management.commands.sync_rewio_reviews import Command as SyncReviewsCommand


class ReviewFilterTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.moscow = Salon.objects.create(
            name='Москва', address='Тестовый адрес', latitude='0', longitude='0',
        )
        cls.zelenograd = Salon.objects.create(
            name='Зеленоград', address='Тестовый адрес 2', latitude='0', longitude='0',
        )

        cls.review_moscow_yandex = Review.objects.create(
            salon=cls.moscow, rewio_review_id=1, source=Review.SOURCE_YANDEX,
            author='Аня', text='Отлично', rating=5, review_date=timezone.now(),
            has_images=True, images=[{'image': '/media/review.jpg', 'preview': '/media/review.jpg'}],
        )
        cls.review_moscow_2gis = Review.objects.create(
            salon=cls.moscow, rewio_review_id=2, source=Review.SOURCE_2GIS,
            author='Оля', text='Хорошо', rating=4, review_date=timezone.now(),
        )
        cls.review_zelenograd_yandex = Review.objects.create(
            salon=cls.zelenograd, rewio_review_id=3, source=Review.SOURCE_YANDEX,
            author='Игорь', text='Супер', rating=5, review_date=timezone.now(),
        )

    def _get(self, **params):
        url = reverse('review-list')
        return self.client.get(url, params)

    def test_no_filter_returns_all(self):
        response = self._get()
        self.assertEqual(response.data['count'], 3)

    def test_filter_by_salon(self):
        response = self._get(salon=self.moscow.id)
        ids = {r['id'] for r in response.data['results']}
        self.assertEqual(ids, {self.review_moscow_yandex.id, self.review_moscow_2gis.id})

    def test_filter_by_source(self):
        response = self._get(source=Review.SOURCE_YANDEX)
        ids = {r['id'] for r in response.data['results']}
        self.assertEqual(ids, {self.review_moscow_yandex.id, self.review_zelenograd_yandex.id})

    def test_filter_by_salon_and_source_combined(self):
        response = self._get(salon=self.moscow.id, source=Review.SOURCE_YANDEX)
        ids = {r['id'] for r in response.data['results']}
        self.assertEqual(ids, {self.review_moscow_yandex.id})

    def test_filter_by_rating(self):
        response = self._get(rating=4)
        ids = {r['id'] for r in response.data['results']}
        self.assertEqual(ids, {self.review_moscow_2gis.id})

    def test_homepage_filter_returns_only_reviews_with_images(self):
        response = self._get(with_images=1)
        self.assertEqual([r['id'] for r in response.data['results']], [self.review_moscow_yandex.id])
        self.assertEqual(response.data['results'][0]['images'][0]['image'], 'http://testserver/media/review.jpg')
        self.assertEqual(self._get().data['count'], 3)

        home_response = self.client.get(reverse('home-review-list'))
        self.assertEqual([r['id'] for r in home_response.data], [self.review_moscow_yandex.id])
        self.assertEqual(home_response.data[0]['workImage'], 'http://testserver/media/review.jpg')

    @patch('reviews.management.commands.sync_rewio_reviews.fetch_and_store_image')
    def test_sync_stores_rewio_photo_in_filer_and_skips_download_on_dry_run(self, fetch_image):
        review_data = {
            'id': 4,
            'review_date': timezone.now().isoformat(),
            'text': 'Отзыв с фото',
            'images': [{'image': 'https://example.test/full.jpg', 'preview': 'https://example.test/preview.jpg'}],
            'has_images': True,
        }
        command = SyncReviewsCommand()
        command._sync_review(self.moscow, review_data, True)
        fetch_image.assert_not_called()

        fetch_image.return_value = SimpleNamespace(url='/media/local-review.jpg')
        command._sync_review(self.moscow, review_data, False)
        fetch_image.assert_called_once_with('https://example.test/full.jpg', folder_name='reviews/photos')
        saved = Review.objects.get(rewio_review_id=4)
        self.assertTrue(saved.has_images)
        self.assertEqual(saved.images, [{'preview': '/media/local-review.jpg', 'image': '/media/local-review.jpg'}])

    @patch('reviews.management.commands.sync_rewio_reviews.fetch_and_store_image', return_value=None)
    def test_failed_photo_download_does_not_mark_review_as_illustrated(self, fetch_image):
        SyncReviewsCommand()._sync_review(self.moscow, {
            'id': 5,
            'review_date': timezone.now().isoformat(),
            'text': 'Фото не загрузилось',
            'images': [{'image': 'https://example.test/full.jpg'}],
            'has_images': True,
        }, False)
        fetch_image.assert_called_once()
        saved = Review.objects.get(rewio_review_id=5)
        self.assertFalse(saved.has_images)
        self.assertEqual(saved.images, [])
        self.assertNotIn(saved.id, [r['id'] for r in self._get(with_images=1).data['results']])
