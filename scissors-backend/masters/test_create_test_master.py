from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from pages.management.commands.generate_sitemap import public_paths

from .models import Master


class CreateTestMasterCommandTests(TestCase):
    def test_default_reuses_hidden_master_with_admin_user(self):
        output = StringIO()
        call_command('create_test_master', stdout=output)
        master = Master.objects.get(slug='test-master-sandbox-1')
        user = master.user

        self.assertTrue(user.is_staff)
        self.assertTrue(user.has_usable_password())
        self.assertFalse(master.is_active)
        self.assertIsNone(master.yclients_user_id)
        self.assertFalse(master.master_salons.exists())
        self.assertFalse(master.page.is_published)
        self.assertIn(user.username, output.getvalue())
        self.assertIn('Пароль', output.getvalue())

        call_command('create_test_master', stdout=output)
        self.assertEqual(Master.objects.count(), 1)
        self.assertEqual(get_user_model().objects.count(), 1)

        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse('admin:masters_master_change',
                                              args=[master.pk])).status_code, 200)
        self.client.logout()
        self.assertEqual(self.client.get('/api/v1/masters/').status_code, 200)
        self.assertNotContains(self.client.get('/api/v1/masters/'), master.slug)
        self.assertEqual(self.client.get(f'/api/v1/pages/by-path/{master.page.url_path}/').status_code,
                         404)

        # Public routes and sitemap must still exclude the sandbox if someone
        # accidentally enables the master and publishes its page in admin.
        master.is_active = True
        master.yclients_user_id = 'sandbox-only'
        master.save(update_fields=['is_active', 'yclients_user_id'])
        master.page.is_published = True
        master.page.save(update_fields=['is_published'])
        self.assertNotIn(master.page.url_path, public_paths())
        self.assertNotContains(self.client.get('/api/v1/masters/'), master.slug)
        self.assertEqual(self.client.get(f'/api/v1/pages/by-path/{master.page.url_path}/').status_code,
                         404)

    def test_no_idempotent_creates_next_pair(self):
        call_command('create_test_master', stdout=StringIO())
        call_command('create_test_master', '--no-idempotent', stdout=StringIO())
        self.assertEqual(Master.objects.count(), 2)
        self.assertTrue(Master.objects.filter(slug='test-master-sandbox-2').exists())
