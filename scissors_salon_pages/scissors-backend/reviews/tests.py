from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from salons.models import Salon

from .models import Review


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
            author='Аня', text='Отлично', rating=5, review_date=timezone.now(), is_approved=True,
        )
        cls.review_moscow_2gis = Review.objects.create(
            salon=cls.moscow, rewio_review_id=2, source=Review.SOURCE_2GIS,
            author='Оля', text='Хорошо', rating=4, review_date=timezone.now(), is_approved=True,
        )
        cls.review_zelenograd_yandex = Review.objects.create(
            salon=cls.zelenograd, rewio_review_id=3, source=Review.SOURCE_YANDEX,
            author='Игорь', text='Супер', rating=5, review_date=timezone.now(), is_approved=True,
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

    def test_unapproved_reviews_never_returned(self):
        hidden = Review.objects.create(
            salon=self.moscow, rewio_review_id=100, source=Review.SOURCE_YANDEX,
            author='Скрытый', text='Не одобрен', rating=5, review_date=timezone.now(),
        )  # is_approved по умолчанию False
        response = self._get()
        ids = {r['id'] for r in response.data['results']}
        self.assertNotIn(hidden.id, ids)
        self.assertEqual(response.data['count'], 3)

    def test_unapproved_hidden_even_with_explicit_filters(self):
        Review.objects.create(
            salon=self.moscow, rewio_review_id=101, source=Review.SOURCE_YANDEX,
            author='Скрытый2', text='x', rating=5, review_date=timezone.now(),
        )
        response = self._get(salon=self.moscow.id, source=Review.SOURCE_YANDEX, rating=5)
        self.assertEqual({r['author'] for r in response.data['results']}, {'Аня'})

    def test_has_images_filter(self):
        with_img = Review.objects.create(
            salon=self.moscow, rewio_review_id=102, source=Review.SOURCE_YANDEX,
            author='С фото', text='Фото', rating=5, review_date=timezone.now(),
            is_approved=True, has_images=True, images=[{'image': 'https://x/y.jpg'}],
        )
        response = self._get(has_images='true')
        self.assertEqual({r['id'] for r in response.data['results']}, {with_img.id})

    def test_home_reviews_requires_approval_and_image(self):
        approved_with_img = Review.objects.create(
            salon=self.moscow, rewio_review_id=103, source=Review.SOURCE_YANDEX,
            author='Ок', text='Текст', rating=5, review_date=timezone.now(),
            is_approved=True, has_images=True, images=[{'image': 'https://x/y.jpg'}],
        )
        Review.objects.create(  # с фото, но не одобрен
            salon=self.moscow, rewio_review_id=104, source=Review.SOURCE_YANDEX,
            author='НеОдобрен', text='Текст', rating=5, review_date=timezone.now(),
            has_images=True, images=[{'image': 'https://x/z.jpg'}],
        )
        response = self.client.get(reverse('home-review-list'))
        self.assertEqual(response.status_code, 200)
        data = response.data if isinstance(response.data, list) else response.data['results']
        self.assertEqual({r['id'] for r in data}, {approved_with_img.id})
