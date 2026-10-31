from io import BytesIO
from tempfile import TemporaryDirectory

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from communications.models import FeedbackRequest
from pages.models import Page
from pages.models import PagePicture
from .models import Master


class MasterProfileAdminTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.staff = User.objects.create_user('master-test', password='test-password',
                                              is_staff=True)
        self.other_staff = User.objects.create_user('other-master-test', password='test-password',
                                                    is_staff=True)
        self.technician = User.objects.create_superuser('technician-test', password='test-password')
        team = Page.objects.create(url='team', title='Команда')
        self.page = Page.objects.create(parent=team, url='master-test', title='Мой профиль')
        self.other_page = Page.objects.create(parent=team, url='other-master-test', title='Другой')
        self.master = Master.objects.create(name='Мой профиль',
                                            page=self.page, user=self.staff)
        self.other_master = Master.objects.create(name='Другой',
                                                  page=self.other_page, user=self.other_staff)

    def test_staff_can_edit_only_own_master_and_page(self):
        self.client.force_login(self.staff)
        master_list = reverse('admin:masters_master_changelist')
        own_master = reverse('admin:masters_master_change', args=[self.master.pk])
        other_master = reverse('admin:masters_master_change', args=[self.other_master.pk])
        own_page = reverse('admin:pages_page_change', args=[self.page.pk])
        other_page = reverse('admin:pages_page_change', args=[self.other_page.pk])

        self.assertEqual(self.client.get(master_list).status_code, 200)
        self.assertContains(self.client.get(own_master), 'Редактировать свою страницу')
        self.assertNotContains(self.client.get(master_list), self.other_master.name)
        self.assertIn(self.client.get(other_master).status_code, (302, 403, 404))
        self.assertIn(self.client.get(other_page).status_code, (302, 403, 404))
        self.client.post(other_master, {'name': 'Подмена', '_save': 'Сохранить'})
        self.client.post(other_page, {'title': 'Подмена', '_save': 'Сохранить'})
        self.other_master.refresh_from_db()
        self.other_page.refresh_from_db()
        self.assertEqual(self.other_master.name, 'Другой')
        self.assertEqual(self.other_page.title, 'Другой')
        self.assertEqual(self.client.get(reverse('admin:masters_master_add')).status_code, 403)
        self.assertEqual(self.client.get(reverse('admin:masters_master_delete',
                                                     args=[self.master.pk])).status_code, 403)
        own_page_response = self.client.get(own_page)
        self.assertEqual(own_page_response.status_code, 200)
        self.assertEqual(len(own_page_response.context['inline_admin_formsets']), 1)

        response = self.client.post(own_master, {
            'name': 'Обновлённое имя', 'status': 'self_employed', 'inn': '',
            'bio': 'Новый текст', 'is_active': '', 'price_level': 'art_director',
            'user': self.other_staff.pk, 'page': self.other_page.pk,
            'page_title': 'Страница мастера', 'page_content': '<p>Профиль</p>',
            'page_meta_title': 'Мастер', 'page_meta_description': 'Описание',
            'page_is_published': 'on',
            '_save': 'Сохранить',
        })
        self.assertEqual(response.status_code, 302)
        self.master.refresh_from_db()
        self.assertEqual(self.master.name, 'Обновлённое имя')
        self.assertEqual(self.master.bio, 'Новый текст')
        self.assertTrue(self.master.is_active)
        self.assertEqual(self.master.price_level, 'art_director')
        self.assertEqual(self.master.user_id, self.staff.pk)
        self.assertEqual(self.master.page_id, self.page.pk)
        self.page.refresh_from_db()
        self.assertEqual(self.page.content, '<p>Профиль</p>')

        response = self.client.post(own_page, {
            'title': 'Новая страница', 'content': '<p>О мастере</p>',
            'is_published': 'on', 'meta_title': 'Заголовок',
            'meta_description': 'Описание', 'url': 'hijacked',
            'parent': self.other_page.pk, 'pictures-TOTAL_FORMS': '0',
            'pictures-INITIAL_FORMS': '0', '_save': 'Сохранить',
        })
        self.assertEqual(response.status_code, 302)
        self.page.refresh_from_db()
        self.assertEqual(self.page.content, '<p>О мастере</p>')
        self.assertEqual(self.page.parent.url, 'team')
        self.assertEqual(self.page.url, 'master-test')

    def test_technician_without_master_keeps_admin_access(self):
        self.client.force_login(self.technician)
        self.assertEqual(self.client.get(reverse('admin:masters_master_change',
                                                      args=[self.master.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse('admin:pages_page_change',
                                                      args=[self.page.pk])).status_code, 200)

    def test_feedback_view_requires_standard_django_permission(self):
        feedback = FeedbackRequest.objects.create(name='Клиент', phone='+79990000000',
                                                  message='Личное обращение')
        feedback_admin = admin.site._registry[FeedbackRequest]
        ordinary_staff = get_user_model().objects.create_user('ordinary-staff', is_staff=True)
        self.client.force_login(ordinary_staff)
        self.assertEqual(self.client.get(reverse('admin:communications_feedbackrequest_changelist')).status_code,
                         403)

        self.client.force_login(self.staff)
        self.assertFalse(feedback_admin.has_module_permission(self._request()))
        self.assertEqual(self.client.get(reverse('admin:communications_feedbackrequest_changelist')).status_code,
                         403)
        self.assertEqual(self.client.get(reverse('admin:communications_feedbackrequest_change',
                                                      args=[feedback.pk])).status_code, 403)

        permission = Permission.objects.get(content_type__app_label='communications',
                                            codename='view_feedbackrequest')
        self.staff.user_permissions.add(permission)
        self.staff = get_user_model().objects.get(pk=self.staff.pk)
        self.client.force_login(self.staff)
        self.assertTrue(feedback_admin.has_module_permission(self._request()))
        self.assertEqual(self.client.get(reverse('admin:communications_feedbackrequest_changelist')).status_code,
                         200)
        self.assertEqual(self.client.get(reverse('admin:communications_feedbackrequest_change',
                                                      args=[feedback.pk])).status_code, 200)

        self.client.force_login(self.technician)
        self.assertEqual(self.client.get(reverse('admin:communications_feedbackrequest_changelist')).status_code,
                         200)

    def _request(self):
        from django.test import RequestFactory
        request = RequestFactory().get('/admin/')
        request.user = self.staff
        return request

    def test_master_uploads_work_photos_from_own_profile(self):
        buffer = BytesIO()
        Image.new('RGB', (2, 2), 'red').save(buffer, format='PNG')
        image_bytes = buffer.getvalue()
        self.client.force_login(self.staff)
        own_master = reverse('admin:masters_master_change', args=[self.master.pk])

        with TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            response = self.client.post(own_master, {
                'name': self.master.name, 'price_level': 'stylist',
                'status': 'self_employed', 'inn': '', 'bio': '',
                'page_title': self.page.title, 'page_content': '',
                'page_meta_title': '', 'page_meta_description': '',
                'page_is_published': 'on',
                'work_photos': [
                    SimpleUploadedFile('first.png', image_bytes, content_type='image/png'),
                    SimpleUploadedFile('second.png', image_bytes, content_type='image/png'),
                ],
                '_save': 'Сохранить',
            })
            self.assertEqual(response.status_code, 302)
            pictures = list(PagePicture.objects.filter(page=self.page).order_by('position'))
            self.assertEqual(len(pictures), 2)
            self.assertEqual([picture.position for picture in pictures], [0, 1])
            self.assertEqual([picture.image.original_filename for picture in pictures],
                             ['first.png', 'second.png'])
            self.assertContains(self.client.get(own_master), 'Фотографии на странице')
            self.assertContains(self.client.get(own_master), 'first.png')
            public_page = self.client.get('/api/v1/pages/by-path/team/master-test/')
            self.assertEqual(public_page.status_code, 200)
            self.assertEqual(len(public_page.data['pictures']), 2)
