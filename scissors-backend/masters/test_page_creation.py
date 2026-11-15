from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from pages.models import Page

from .models import Master


class MasterPageCreationTests(TestCase):
    def test_new_master_gets_linked_page_once(self):
        team = Page.objects.create(url='team', title='Команда')
        master = Master.objects.create(name='Новый мастер', yclients_user_id='123')

        self.assertIsNotNone(master.page_id)
        self.assertEqual(master.page.parent_id, team.pk)
        self.assertEqual(master.page.url_path, f'team/{master.slug}')
        self.assertTrue(master.page.is_published)

        page_id = master.page_id
        master.bio = 'Описание'
        master.save(update_fields=['bio'])
        self.assertEqual(master.page_id, page_id)
        self.assertEqual(Page.objects.filter(pk=page_id).count(), 1)

    def test_test_master_page_stays_unpublished(self):
        Page.objects.create(url='team', title='Команда')
        master = Master.objects.create(name='Тестовый мастер', is_system=True)

        self.assertIsNotNone(master.page_id)
        self.assertFalse(master.page.is_published)

    def test_master_gets_draft_page_before_team_root_exists(self):
        master = Master.objects.create(name='Новый мастер')

        self.assertIsNotNone(master.page_id)
        self.assertTrue(master.page.url_path.startswith('master-draft-'))
        self.assertFalse(master.page.is_published)

        call_command('populate_site_pages', stdout=StringIO())
        master.page.refresh_from_db()
        self.assertEqual(master.page.url_path, f'team/{master.slug}')
        self.assertTrue(master.page.is_published)
