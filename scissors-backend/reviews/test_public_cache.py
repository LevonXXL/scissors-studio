from django.core.cache import caches
from django.test import TestCase, override_settings
from django.utils import timezone

from salons.models import Salon

from .models import Review


@override_settings(DEBUG=False)
class PublicReviewCacheTests(TestCase):
    def setUp(self):
        caches['public_content'].clear()
        salon = Salon.objects.create(name='Салон', address='Адрес', latitude=55, longitude=37)
        self.review = Review.objects.create(
            salon=salon,
            rewio_review_id=991001,
            author='До изменения',
            text='Отзыв',
            rating=5,
            review_date=timezone.now(),
        )

    def tearDown(self):
        caches['public_content'].clear()

    def test_review_edit_invalidates_cached_first_page_after_commit(self):
        url = '/api/v1/reviews/?page=1'
        first = self.client.get(url).json()
        self.assertEqual(first['results'][0]['author'], 'До изменения')

        with self.captureOnCommitCallbacks(execute=True):
            self.review.author = 'После изменения'
            self.review.save(update_fields=['author'])

        second = self.client.get(url).json()
        self.assertEqual(second['results'][0]['author'], 'После изменения')
