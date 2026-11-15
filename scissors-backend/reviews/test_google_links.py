from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from reviews.client import SOURCE_ID_MAP
from salons.models import Salon


class RewioGoogleLinksTests(TestCase):
    def setUp(self):
        self.salon = Salon.objects.create(
            name='Тестовый салон',
            address='Тестовый адрес',
            latitude=55.0,
            longitude=37.0,
            google_maps_url='https://www.google.com/maps/place/Test/data=123',
            rewio_object_id='42',
        )

    @patch('reviews.management.commands.sync_rewio_google_links.RewioClient')
    def test_adds_google_link_once(self, client_class):
        client = client_class.return_value
        client.get_object.side_effect = [
            {'id': 42, 'links': []},
            {'id': 42, 'links': [{'source_id': 2}]},
        ]
        client.add_links.return_value = {'link_results': [{'url': self.salon.google_maps_url, 'link_id': 7, 'error': None}]}

        call_command('sync_rewio_google_links', '--apply', stdout=StringIO())
        call_command('sync_rewio_google_links', '--apply', stdout=StringIO())

        client.add_links.assert_called_once_with('42', [self.salon.google_maps_url])

    def test_current_source_ids(self):
        self.assertEqual(SOURCE_ID_MAP, {1: 1, 2: 4, 3: 2, 201: 3, 207: 5})
