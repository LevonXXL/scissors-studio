from django.core.cache import caches
from django.test import SimpleTestCase, override_settings

from .public_cache import invalidate_public_data, remember_public_data


@override_settings(DEBUG=False)
class PublicDataCacheTests(SimpleTestCase):
    def setUp(self):
        caches['public_content'].clear()

    def tearDown(self):
        caches['public_content'].clear()

    def test_cached_value_is_reused_until_its_domain_is_invalidated(self):
        calls = []

        def load():
            calls.append(len(calls) + 1)
            return {'value': calls[-1]}

        self.assertEqual(remember_public_data('test-domain', 'item', load, 60), {'value': 1})
        self.assertEqual(remember_public_data('test-domain', 'item', load, 60), {'value': 1})
        self.assertEqual(calls, [1])

        invalidate_public_data('test-domain')

        self.assertEqual(remember_public_data('test-domain', 'item', load, 60), {'value': 2})
        self.assertEqual(calls, [1, 2])
