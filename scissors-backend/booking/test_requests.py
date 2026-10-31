from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework_simplejwt.tokens import AccessToken

from client_auth.models import VerifiedPhone
from masters.models import Master, MasterSalon
from salons.models import Salon
from services.models import Service, ServiceCategory, ServiceStaffPrice, ServiceSalon

from .forms import BookingAdminForm
from .models import Booking


class BookingRequestTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.salon = Salon.objects.create(name='Салон', address='Адрес', latitude=0, longitude=0)
        cls.master = Master.objects.create(name='Мастер', )
        MasterSalon.objects.create(master=cls.master, salon=cls.salon)
        cls.category = ServiceCategory.objects.create(title='Стрижки')
        cls.service = Service.objects.create(
            category=cls.category, title='Стрижка', yclients_service_id='service-1',
        )
        ServiceSalon.objects.create(service=cls.service, salon=cls.salon)
        ServiceStaffPrice.objects.create(service=cls.service, master=cls.master, salon=cls.salon)

    def payload(self):
        start = timezone.now() + timedelta(days=2)
        return {
            'salon': self.salon.pk,
            'service_ids': [self.service.pk],
            'preferred_master': self.master.pk,
            'requested_start': start.isoformat(),
            'requested_end': (start + timedelta(hours=2)).isoformat(),
            'name': 'Клиент',
            'phone': '79991234567',
            'comment': 'После 15:00',
            'status': Booking.STATUS_CONFIRMED,
        }

    def test_anonymous_request_is_pending_and_does_not_reserve_time(self):
        response = self.client.post(reverse('booking-request'), self.payload(), content_type='application/json')
        self.assertEqual(response.status_code, 201)
        booking = Booking.objects.get(pk=response.json()['id'])
        self.assertEqual(booking.status, Booking.STATUS_PENDING)
        self.assertIsNone(booking.start_datetime)
        self.assertIsNone(booking.end_datetime)
        self.assertIsNone(booking.yclients_record_id)
        self.assertEqual(booking.client_phone, '+79991234567')
        self.assertEqual(list(booking.services.values_list('pk', flat=True)), [self.service.pk])
        self.assertNotIn('client_phone', response.json())

    def test_verified_phone_wins_over_submitted_number(self):
        user = get_user_model().objects.create_user(username='client', password='unused')
        VerifiedPhone.objects.create(user=user, phone='+79990000000', verified_at=timezone.now())
        self.client.force_login(user)
        response = self.client.post(reverse('booking-request'), self.payload(), content_type='application/json')
        self.assertEqual(response.status_code, 201)
        booking = Booking.objects.get(pk=response.json()['id'])
        self.assertEqual(booking.client_phone, '+79990000000')
        self.assertEqual(booking.client_user, user)

    def test_my_bookings_match_verified_phone_and_hide_other_clients(self):
        user = get_user_model().objects.create_user(username='client', password='unused')
        VerifiedPhone.objects.create(user=user, phone='+79991234567', verified_at=timezone.now())
        future = timezone.now() + timedelta(days=2)
        past = timezone.now() - timedelta(days=2)
        imported = Booking.objects.create(
            salon=self.salon, master=self.master, client_phone='79991234567',
            start_datetime=future, end_datetime=future + timedelta(hours=1),
            status=Booking.STATUS_CONFIRMED, yclients_record_id='external-1',
        )
        previous = Booking.objects.create(
            salon=self.salon, client_phone='+79991234567',
            start_datetime=past, status=Booking.STATUS_COMPLETED,
        )
        Booking.objects.create(
            salon=self.salon, client_phone='+79990000000',
            start_datetime=future, status=Booking.STATUS_CONFIRMED,
        )
        another = get_user_model().objects.create_user(username='another')
        Booking.objects.create(
            salon=self.salon, client_user=another, client_phone='79991234567',
            start_datetime=future, status=Booking.STATUS_CONFIRMED,
        )
        self.client.force_login(user)
        future_response = self.client.get(reverse('my-bookings'))
        self.assertEqual(future_response.status_code, 200)
        self.assertEqual([item['id'] for item in future_response.json()['results']], [imported.pk])
        self.assertNotIn('client_phone', future_response.content.decode())
        self.assertNotIn('yclients_record_id', future_response.content.decode())
        past_response = self.client.get(reverse('my-bookings'), {'period': 'past'})
        self.assertEqual([item['id'] for item in past_response.json()['results']], [previous.pk])
        self.client.logout()
        self.assertEqual(self.client.get(reverse('my-bookings')).status_code, 401)

    def test_my_bookings_match_all_verified_phones(self):
        user = get_user_model().objects.create_user(username='client', password='unused')
        VerifiedPhone.objects.create(user=user, phone='+79991234567', verified_at=timezone.now())
        VerifiedPhone.objects.create(user=user, phone='+79991112233', verified_at=timezone.now())
        future = timezone.now() + timedelta(days=2)
        bookings = [Booking.objects.create(
            salon=self.salon, client_phone=phone, start_datetime=future,
            status=Booking.STATUS_CONFIRMED,
        ) for phone in ('79991234567', '+79991112233')]
        self.client.force_login(user)
        response = self.client.get(reverse('my-bookings'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual({item['id'] for item in response.json()['results']}, {item.pk for item in bookings})

        previous = Booking.objects.create(
            salon=self.salon, client_phone='79991112233',
            start_datetime=timezone.now() - timedelta(days=1), status=Booking.STATUS_COMPLETED,
        )
        future_cancelled = Booking.objects.create(
            salon=self.salon, client_phone='+79991112233',
            start_datetime=future, status=Booking.STATUS_CANCELLED,
        )
        future_response = self.client.get(reverse('my-bookings'))
        self.assertEqual(
            {item['id'] for item in future_response.json()['results']},
            {item.pk for item in bookings} | {future_cancelled.pk},
        )
        past_response = self.client.get(reverse('my-bookings'), {'period': 'past'})
        self.assertEqual([item['id'] for item in past_response.json()['results']], [previous.pk])

    def test_my_bookings_match_three_stored_phone_formats(self):
        user = get_user_model().objects.create_user(username='client', password='unused')
        VerifiedPhone.objects.create(user=user, phone='+79670303036', verified_at=timezone.now())
        another = get_user_model().objects.create_user(username='another')
        future = timezone.now() + timedelta(days=1)
        own_bookings = [Booking.objects.create(
            salon=self.salon, client_phone=phone, start_datetime=future,
            status=Booking.STATUS_CONFIRMED,
        ) for phone in ('+79670303036', '79670303036', '9670303036')]
        Booking.objects.create(
            salon=self.salon, client_phone='9670303036', client_user=another,
            start_datetime=future, status=Booking.STATUS_CONFIRMED,
        )
        self.client.force_login(user)
        response = self.client.get(reverse('my-bookings'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {item['id'] for item in response.json()['results']},
            {booking.pk for booking in own_bookings},
        )

    def test_my_bookings_accepts_bearer_token(self):
        user = get_user_model().objects.create_user(username='client', password='unused')
        VerifiedPhone.objects.create(user=user, phone='+79991234567', verified_at=timezone.now())
        booking = Booking.objects.create(
            salon=self.salon, client_phone='79991234567',
            start_datetime=timezone.now() + timedelta(days=1), status=Booking.STATUS_CONFIRMED,
        )
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Bearer {AccessToken.for_user(user)}'
        response = self.client.get(reverse('my-bookings'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item['id'] for item in response.json()['results']], [booking.pk])

    def test_authenticated_user_creates_pending_request_with_selected_phone(self):
        user = get_user_model().objects.create_user(username='client', password='unused')
        VerifiedPhone.objects.create(user=user, phone='+79991234567', verified_at=timezone.now())
        VerifiedPhone.objects.create(user=user, phone='+79991112233', verified_at=timezone.now())
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Bearer {AccessToken.for_user(user)}'
        payload = self.payload()
        payload['phone'] = '+79991112233'
        response = self.client.post(reverse('booking-request'), payload, content_type='application/json')
        self.assertEqual(response.status_code, 201)
        booking = Booking.objects.get(pk=response.json()['id'])
        self.assertEqual(booking.client_user, user)
        self.assertEqual(booking.client_phone, '+79991112233')
        self.assertEqual(booking.status, Booking.STATUS_PENDING)
        self.assertIsNone(booking.start_datetime)

    def test_request_can_use_only_own_verified_phone_when_there_are_multiple(self):
        user = get_user_model().objects.create_user(username='client', password='unused')
        VerifiedPhone.objects.create(user=user, phone='+79991234567', verified_at=timezone.now())
        VerifiedPhone.objects.create(user=user, phone='+79991112233', verified_at=timezone.now())
        self.client.force_login(user)
        payload = self.payload()
        payload['phone'] = '+79991112233'
        response = self.client.post(reverse('booking-request'), payload, content_type='application/json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Booking.objects.get(pk=response.json()['id']).client_phone, '+79991112233')
        payload['phone'] = '+79990000000'
        self.assertEqual(self.client.post(reverse('booking-request'), payload, content_type='application/json').status_code, 400)

    def test_unverified_phone_does_not_expose_guest_bookings(self):
        user = get_user_model().objects.create_user(username='client', password='unused')
        Booking.objects.create(
            salon=self.salon, client_phone='79991234567',
            start_datetime=timezone.now() + timedelta(days=1),
            status=Booking.STATUS_CONFIRMED,
        )
        self.client.force_login(user)
        response = self.client.get(reverse('my-bookings'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['results'], [])

    def test_exact_time_and_booking_options(self):
        options = self.client.get(reverse('booking-options'), {'salon': self.salon.pk})
        self.assertEqual(options.status_code, 200)
        self.assertEqual([item['id'] for item in options.json()['services']], [self.service.pk])
        self.assertEqual(options.json()['services'][0]['master_ids'], [self.master.pk])
        payload = self.payload()
        payload.pop('requested_end')
        response = self.client.post(reverse('booking-request'), payload, content_type='application/json')
        self.assertEqual(response.status_code, 201)
        self.assertIsNone(Booking.objects.get().requested_end)

    def test_master_must_offer_all_selected_services(self):
        other = Service.objects.create(
            category=self.category, title='Окрашивание', yclients_service_id='service-2',
        )
        ServiceSalon.objects.create(service=other, salon=self.salon)
        payload = self.payload()
        payload['service_ids'] = [self.service.pk, other.pk]
        response = self.client.post(reverse('booking-request'), payload, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('preferred_master', response.json())
        self.assertFalse(Booking.objects.exists())

    def test_options_respect_salon_and_master_service_links(self):
        other_salon = Salon.objects.create(name='Другой', address='Адрес', latitude=0, longitude=0)
        other_category = ServiceCategory.objects.create(title='Ногти')
        other_service = Service.objects.create(
            category=other_category, title='Маникюр', yclients_service_id='service-3',
        )
        other_master = Master.objects.create(name='Другой мастер', )
        MasterSalon.objects.create(master=other_master, salon=other_salon)
        ServiceSalon.objects.create(service=other_service, salon=other_salon)
        ServiceStaffPrice.objects.create(service=other_service, master=other_master, salon=other_salon)
        response = self.client.get(reverse('booking-options'), {'salon': self.salon.pk})
        self.assertEqual([item['id'] for item in response.json()['services']], [self.service.pk])
        self.assertEqual([item['id'] for item in response.json()['masters']], [self.master.pk])

    def test_authenticated_user_without_phone_must_enter_one(self):
        user = get_user_model().objects.create_user(username='staff', password='unused', is_staff=True)
        self.client.force_login(user)
        payload = self.payload()
        payload.pop('phone')
        response = self.client.post(reverse('booking-request'), payload, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('phone', response.json())

    def test_other_salon_service_is_rejected(self):
        other = Salon.objects.create(name='Другой', address='Адрес', latitude=0, longitude=0)
        payload = self.payload()
        payload['salon'] = other.pk
        response = self.client.post(reverse('booking-request'), payload, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Booking.objects.exists())

    def test_imported_booking_blocks_confirmation_but_pending_does_not(self):
        start = timezone.now() + timedelta(days=2)
        imported = Booking.objects.create(
            salon=self.salon, master=self.master, start_datetime=start,
            end_datetime=start + timedelta(hours=2), status=Booking.STATUS_CONFIRMED,
            yclients_record_id='12345',
        )
        pending = Booking.objects.create(
            salon=self.salon, master=self.master, requested_start=start,
            requested_end=start + timedelta(hours=3), status=Booking.STATUS_PENDING,
            client_name='Другой клиент', client_phone='+79991234567',
        )
        form = BookingAdminForm(data={
            'salon': self.salon.pk, 'master': self.master.pk,
            'start_datetime': (start + timedelta(hours=1)).isoformat(),
            'end_datetime': (start + timedelta(hours=3)).isoformat(),
            'status': Booking.STATUS_CONFIRMED,
            'client_name': 'Другой клиент', 'client_phone': '+79991234567',
        }, instance=pending)
        self.assertFalse(form.is_valid())
        self.assertIn('YCLIENTS', str(form.errors))

        imported.status = Booking.STATUS_CANCELLED
        imported.save(update_fields=['status'])
        Booking.objects.create(
            salon=self.salon, master=self.master, requested_start=start,
            status=Booking.STATUS_PENDING, client_name='Третий клиент',
        )
        form = BookingAdminForm(data=form.data, instance=pending)
        self.assertTrue(form.is_valid(), form.errors)

    def test_admin_confirms_pending_request_after_assigning_time(self):
        user = get_user_model().objects.create_superuser('admin', 'admin@example.test', 'pass')
        self.client.force_login(user)
        start = timezone.now() + timedelta(days=2)
        pending = Booking.objects.create(
            salon=self.salon, requested_start=start, status=Booking.STATUS_PENDING,
            client_name='Клиент', client_phone='+79991234567',
        )
        url = reverse('admin:booking_booking_change', args=[pending.pk]) + '?calendar_modal=1'
        response = self.client.post(url, {
            'salon': self.salon.pk,
            'master': self.master.pk,
            'service_title': 'Стрижка',
            'client_name': 'Клиент',
            'client_phone': '+79991234567',
            'requested_start_0': start.date().isoformat(),
            'requested_start_1': start.strftime('%H:%M:%S'),
            'start_datetime_0': start.date().isoformat(),
            'start_datetime_1': start.strftime('%H:%M:%S'),
            'end_datetime_0': (start + timedelta(hours=1)).date().isoformat(),
            'end_datetime_1': (start + timedelta(hours=1)).strftime('%H:%M:%S'),
            'status': Booking.STATUS_CONFIRMED,
            '_save': 'Сохранить',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/calendar_saved.html')
        pending.refresh_from_db()
        self.assertEqual(pending.status, Booking.STATUS_CONFIRMED)
        self.assertIsNotNone(pending.start_datetime)
