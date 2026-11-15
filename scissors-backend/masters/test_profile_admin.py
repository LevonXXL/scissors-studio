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
from salons.models import Salon
from services.models import Service, ServiceCategory, ServicePrice, ServiceSalon, ServiceStaffPrice
from .models import Master, MasterSalon, MasterServiceWorkPhoto


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
        response = self.client.get(reverse('admin:masters_master_change', args=[self.master.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Редактировать услуги и длительность')
        self.assertContains(response, 'назначений: 0')
        self.assertEqual(self.client.get(reverse('admin:masters_master_services',
                                                      args=[self.master.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse('admin:pages_page_change',
                                                      args=[self.page.pk])).status_code, 200)

    def test_superuser_can_attach_master_to_salon_in_change_form(self):
        salon = Salon.objects.create(name='Новый салон', address='Адрес', latitude=55, longitude=37)
        self.client.force_login(self.technician)
        url = reverse('admin:masters_master_change', args=[self.master.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        formset = response.context['inline_admin_formsets'][0].formset
        self.assertEqual(len(formset.forms), 1)
        self.assertFalse(formset.forms[0].fields['salon'].disabled)
        self.assertTrue(formset.forms[0].fields['yclients_staff_id'].disabled)
        self.assertContains(response, 'Выберите салон, в котором работает мастер.')
        self.assertContains(response, 'Заполняется при синхронизации')
        self.assertContains(response, 'Необязательная прямая ссылка на запись')

        prefix = formset.prefix
        response = self.client.post(url, {
            'name': self.master.name, 'status': self.master.status,
            'slug': self.master.slug, 'page': self.page.pk,
            'user': self.staff.pk, 'is_active': 'on', 'position': 0,
            f'{prefix}-TOTAL_FORMS': 1,
            f'{prefix}-INITIAL_FORMS': 0,
            f'{prefix}-MIN_NUM_FORMS': 0,
            f'{prefix}-MAX_NUM_FORMS': 1000,
            f'{prefix}-0-salon': salon.pk,
            f'{prefix}-0-yclients_booking_url': '',
            '_save': 'Сохранить',
        })
        self.assertEqual(response.status_code, 302)
        link = MasterSalon.objects.get(master=self.master, salon=salon)
        self.assertIsNone(link.yclients_staff_id)

        response = self.client.get(url)
        formset = response.context['inline_admin_formsets'][0].formset
        self.assertTrue(formset.forms[0].fields['salon'].disabled)
        self.assertFalse(formset.forms[1].fields['salon'].disabled)

    def test_master_can_manage_only_own_service_assignments(self):
        salon = Salon.objects.create(name='Салон', address='Адрес', latitude=55, longitude=37)
        category = ServiceCategory.objects.create(title='Стрижки', code='profile-services')
        service = Service.objects.create(category=category, title='Стрижка',
                                         duration_seconds=3600, price_code='MASTER-1')
        offer = ServiceSalon.objects.create(service=service, salon=salon)
        ServicePrice.objects.create(salon_service=offer, level='', amount=2000)
        MasterSalon.objects.create(master=self.master, salon=salon)
        MasterSalon.objects.create(master=self.other_master, salon=salon)
        own_url = reverse('admin:masters_master_services', args=[self.master.pk])
        other_url = reverse('admin:masters_master_services', args=[self.other_master.pk])
        self.client.force_login(self.staff)
        self.assertContains(self.client.get(own_url), 'Стрижка')
        self.assertEqual(self.client.get(other_url).status_code, 404)
        self.assertEqual(self.client.post(other_url, {
            'action': 'add', 'salon_id': salon.pk, 'service_id': service.pk,
        }).status_code, 404)
        self.assertEqual(self.client.post(own_url, {
            'action': 'add', 'salon_id': salon.pk, 'service_id': service.pk,
            'duration_minutes': '50',
        }).status_code, 302)
        assignment = ServiceStaffPrice.objects.get(master=self.master, salon=salon, service=service)
        self.assertEqual(assignment.duration_seconds, 3000)
        self.assertFalse(ServiceStaffPrice.objects.filter(master=self.other_master).exists())
        self.assertEqual(self.client.post(own_url, {
            'action': 'update', 'salon_id': salon.pk, 'service_id': service.pk,
            'duration_minutes': '',
        }).status_code, 302)
        assignment.refresh_from_db()
        self.assertIsNone(assignment.duration_seconds)
        self.assertEqual(assignment.effective_duration_seconds, 3600)
        self.assertEqual(self.client.post(own_url, {
            'action': 'remove', 'salon_id': salon.pk, 'service_id': service.pk,
        }).status_code, 302)
        self.assertFalse(ServiceStaffPrice.objects.filter(master=self.master).exists())

    def test_master_can_remove_old_assignment_but_not_add_inactive_offer(self):
        salon = Salon.objects.create(name='Салон', address='Адрес', latitude=55, longitude=37)
        category = ServiceCategory.objects.create(title='Стрижки', code='profile-old')
        service = Service.objects.create(category=category, title='Старая услуга',
                                         price_code='MASTER-2')
        ServiceSalon.objects.create(service=service, salon=salon, is_active=False)
        MasterSalon.objects.create(master=self.master, salon=salon)
        assignment = ServiceStaffPrice.objects.create(master=self.master, salon=salon, service=service)
        url = reverse('admin:masters_master_services', args=[self.master.pk])
        self.client.force_login(self.staff)
        self.assertContains(self.client.get(url), 'Нет в актуальных услугах этого салона')
        self.assertEqual(self.client.post(url, {
            'action': 'remove', 'salon_id': salon.pk, 'service_id': service.pk,
        }).status_code, 302)
        self.assertFalse(ServiceStaffPrice.objects.filter(pk=assignment.pk).exists())
        self.assertEqual(self.client.post(url, {
            'action': 'add', 'salon_id': salon.pk, 'service_id': service.pk,
        }).status_code, 200)
        self.assertFalse(ServiceStaffPrice.objects.filter(master=self.master).exists())

    def test_master_service_list_only_has_prices_for_selected_level(self):
        salon = Salon.objects.create(name='Салон', address='Адрес', latitude=55, longitude=37)
        category = ServiceCategory.objects.create(title='Стрижки', code='level-filter')
        service = Service.objects.create(category=category, title='Стрижка только арт-директора',
                                         price_code='LEVEL-1')
        offer = ServiceSalon.objects.create(service=service, salon=salon)
        ServicePrice.objects.create(salon_service=offer, level='art_director', amount=3000)
        MasterSalon.objects.create(master=self.master, salon=salon)
        self.master.price_level = 'stylist'
        self.master.save(update_fields=['price_level'])
        self.client.force_login(self.staff)
        url = reverse('admin:masters_master_services', args=[self.master.pk])
        self.assertNotContains(self.client.get(url), service.title)
        response = self.client.post(url, {
            'action': 'add', 'salon_id': salon.pk, 'service_id': service.pk,
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ServiceStaffPrice.objects.filter(master=self.master, service=service).exists())

        ServicePrice.objects.create(salon_service=offer, level='stylist', amount=2500)
        self.assertContains(self.client.get(url), service.title)

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

    def test_master_uploads_service_work_only_for_assigned_service(self):
        salon = Salon.objects.create(name='Салон работ', address='Адрес', latitude=55, longitude=37)
        category = ServiceCategory.objects.create(title='Стрижки', code='work-photos')
        service = Service.objects.create(category=category, title='Мужская стрижка', price_code='WORK-1')
        other_service = Service.objects.create(category=category, title='Окрашивание', price_code='WORK-2')
        ServiceSalon.objects.create(service=service, salon=salon)
        MasterSalon.objects.create(master=self.master, salon=salon)
        ServiceStaffPrice.objects.create(master=self.master, salon=salon, service=service)
        url = reverse('admin:masters_master_service_work', args=[self.master.pk])
        other_url = reverse('admin:masters_master_service_work', args=[self.other_master.pk])
        image_buffer = BytesIO()
        Image.new('RGB', (2, 2), 'blue').save(image_buffer, format='PNG')
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(other_url).status_code, 404)

        with TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            response = self.client.post(url, {
                'action': 'upload', 'service': other_service.pk,
                'image': SimpleUploadedFile('bad.png', image_buffer.getvalue(), content_type='image/png'),
            })
            self.assertEqual(response.status_code, 200)
            self.assertFalse(MasterServiceWorkPhoto.objects.exists())
            response = self.client.post(url, {
                'action': 'upload', 'service': service.pk, 'caption': 'Готовая стрижка',
                'image': SimpleUploadedFile('work.png', image_buffer.getvalue(), content_type='image/png'),
            })
            self.assertEqual(response.status_code, 302)
            photo = MasterServiceWorkPhoto.objects.get(master=self.master, service=service)
            self.assertEqual(photo.caption, 'Готовая стрижка')
            page = self.client.get('/api/v1/pages/by-path/team/master-test/')
            self.assertEqual(page.data['master']['service_work_photos'][0]['service_id'], service.pk)
            self.assertEqual(page.data['master']['service_work_photos'][0]['caption'], 'Готовая стрижка')
            self.assertEqual(self.client.post(url, {
                'action': 'delete', 'photo_id': photo.pk,
            }).status_code, 302)
            self.assertFalse(MasterServiceWorkPhoto.objects.exists())
