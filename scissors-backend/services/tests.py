from copy import deepcopy
from base64 import b64decode
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from filer.models import Image as FilerImage

from salons.models import Salon
from pages.models import Page, PagePicture
from masters.models import Master, MasterSalon
from django.core.exceptions import ValidationError
from .excel_import import apply_preview, capitalize_description, read_xlsx
from .unified_excel_import import apply_unified_preview, read_unified_xlsx
from .models import Service, ServiceCategory, ServicePrice, ServiceSalon, ServiceStaffPrice


PRICE_DIR = Path(__file__).resolve().parents[2] / 'price'


class ServiceImageTests(TestCase):
    def test_catalogue_prefers_service_image_and_adds_it_to_page(self):
        root = Page.objects.get(url_path='uslugi')
        category_page = Page.objects.create(parent=root, url='image-test', title='Фото услуг')
        service_page = Page.objects.create(parent=category_page, url='service', title='Услуга')
        category = ServiceCategory.objects.create(title='Фото услуг', code='image-test', page=category_page)
        service = Service.objects.create(category=category, page=service_page, title='Услуга')
        salon = Salon.objects.create(name='Зеленоград', slug='zelenograd', address='Адрес',
                                     latitude=55, longitude=37)
        ServiceSalon.objects.create(service=service, salon=salon)
        gif = b64decode('R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs=')

        with TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            page_image = FilerImage.objects.create(
                original_filename='page.gif', name='Фото страницы',
                file=SimpleUploadedFile('page.gif', gif, content_type='image/gif'),
            )
            service_image = FilerImage.objects.create(
                original_filename='service.gif', name='Фото услуги',
                file=SimpleUploadedFile('service.gif', gif, content_type='image/gif'),
            )
            PagePicture.objects.create(page=service_page, image=page_image, position=0)

            def catalogue_image():
                response = self.client.get(f'/api/v1/service-categories/?salon={salon.pk}')
                self.assertEqual(response.status_code, 200)
                categories = response.data['results'] if isinstance(response.data, dict) else response.data
                return categories[0]['services'][0]['image']

            self.assertTrue(catalogue_image().endswith(page_image.url))
            service.image = service_image
            service.save(update_fields=['image'])
            service.save(update_fields=['image'])
            self.assertTrue(catalogue_image().endswith(service_image.url))
            self.assertEqual(PagePicture.objects.filter(page=service_page,
                                                        image=service_image).count(), 1)
            service.image = None
            service.save(update_fields=['image'])
            self.assertTrue(catalogue_image().endswith(page_image.url))


class ExcelImportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.salon = Salon.objects.create(name='Scissors Зеленоград', slug='zelenograd',
                                         address='Адрес', latitude=55, longitude=37)

    def previews(self):
        return [read_xlsx(path.read_bytes()) for path in PRICE_DIR.glob('*.xlsx')
                if not path.name.startswith('SCISSORS-')]

    def test_description_capitalizes_first_letter_without_changing_brand(self):
        self.assertEqual(capitalize_description('до лопаток — Goldwell iQ'),
                         'До лопаток — Goldwell iQ')
        self.assertEqual(capitalize_description('«мягкий» уход Comfort Zone'),
                         '«Мягкий» уход Comfort Zone')


    def test_three_formats_and_idempotent_catalogue(self):
        previews = self.previews()
        self.assertEqual({p['kind']: len(p['rows']) for p in previews},
                         {'hair': 74, 'nails': 52, 'fixed': 113})
        self.assertTrue(all(p['city'] == 'zelenograd' and not p['errors'] for p in previews))
        self.assertTrue(all(not row['group'][:2].isdigit() for p in previews for row in p['rows']))
        hair = next(p for p in previews if p['kind'] == 'hair')
        self.assertEqual(hair['rows'][0]['group'], 'Стрижки и мужской сервис')
        for preview in previews:
            self.assertGreater(apply_preview(preview, self.salon, {}), 0)
            self.assertEqual(apply_preview(preview, self.salon, {}), 0)
        self.assertEqual(ServiceCategory.objects.filter(is_active=True).count(), 6)
        self.assertEqual(Service.objects.count(), 239)
        self.assertEqual(ServiceSalon.objects.count(), 239)
        self.assertEqual(ServicePrice.objects.count(), sum(
            price['status'] == 'amount'
            for preview in previews for item in preview['rows'] for price in item['prices']
        ))
        self.assertEqual(ServiceStaffPrice.objects.count(), 0)
        self.assertTrue(Page.objects.filter(url_path='uslugi/hair/zhenskaya-strizhka').exists())

    def test_dash_is_not_zero_and_same_catalogue_has_salon_prices(self):
        hair = next(p for p in self.previews() if p['kind'] == 'hair')
        brow = next(row for row in hair['rows'] if row['row'] == 15)
        self.assertEqual([p['status'] for p in brow['prices']],
                         ['dash', 'amount', 'dash', 'amount', 'amount'])
        apply_preview(hair, self.salon, {}, {brow['row']})
        self.assertEqual(set(ServicePrice.objects.filter(
            salon_service__service__title=brow['title'], salon_service__salon=self.salon,
        ).values_list('level', flat=True)), {'modeler', 'top_stylist', 'art_director'})
        other = Salon.objects.create(name='Scissors Красные Ворота', slug='scissors-krasnye-vorota',
                                     address='Адрес',
                                     latitude=55, longitude=37)
        first = hair['rows'][0]
        apply_preview(hair, self.salon, {}, {first['row']})
        service = Service.objects.get(title=first['title'])
        service.description = 'Сохранённое описание'
        service.save(update_fields=['description'])
        red_gate_price = deepcopy(hair)
        red_gate_price['rows'][0]['prices'][0]['amount'] = '9999'
        red_gate_price['rows'][0]['description'] = 'Обновлённое описание'
        apply_preview(red_gate_price, other, {}, {first['row']})
        service.refresh_from_db()
        self.assertEqual(service.description, 'Обновлённое описание')
        self.assertEqual(Service.objects.filter(title=first['title']).count(), 1)
        self.assertEqual(ServiceSalon.objects.filter(service=service).count(), 2)
        self.assertEqual(ServicePrice.objects.get(salon_service__service=service,
                                                  salon_service__salon=other,
                                                  level='universal').amount, 9999)
        self.assertNotEqual(ServicePrice.objects.get(salon_service__service=service,
                                                     salon_service__salon=self.salon,
                                                     level='universal').amount, 9999)
        apply_preview(hair, self.salon, {}, {first['row']})
        service.refresh_from_db()
        self.assertEqual(service.description, 'Обновлённое описание')

    def test_import_preserves_editorial_page(self):
        hair = next(p for p in self.previews() if p['kind'] == 'hair')
        apply_preview(hair, self.salon, {})
        page = Page.objects.get(url_path='uslugi/hair/zhenskaya-strizhka')
        page.content = '<p>Текст редактора</p>'
        page.save()
        apply_preview(hair, self.salon, {})
        page.refresh_from_db()
        self.assertEqual(page.content, '<p>Текст редактора</p>')

    def test_mikhail_cannot_be_assigned_cosmetology(self):
        fixed = next(p for p in self.previews() if p['kind'] == 'fixed')
        apply_preview(fixed, self.salon, {})
        master = Master.objects.create(name='Михаил Стець',
                                       price_level='art_director')
        MasterSalon.objects.create(master=master, salon=self.salon)
        service = Service.objects.get(title__startswith='Архитектура бровей')
        with self.assertRaises(ValidationError):
            ServiceStaffPrice(service=service, master=master, salon=self.salon).full_clean()

    def test_api_uses_selected_salon_and_exact_master_level(self):
        hair = next(p for p in self.previews() if p['kind'] == 'hair')
        apply_preview(hair, self.salon, {})
        service = Service.objects.get(title='Женская стрижка')
        master = Master.objects.create(name='Михаил Стець',
                                       price_level='art_director')
        MasterSalon.objects.create(master=master, salon=self.salon)
        ServiceStaffPrice.objects.create(service=service, master=master, salon=self.salon)
        moscow = Salon.objects.create(name='Scissors Красные Ворота', address='Адрес',
                                      latitude=55, longitude=37)
        other_offer = ServiceSalon.objects.create(service=service, salon=moscow)
        ServicePrice.objects.create(salon_service=other_offer, level='art_director', amount=99999)

        response = self.client.get(f'/api/v1/service-categories/?salon={self.salon.pk}')
        self.assertEqual(response.status_code, 200)
        categories = response.data['results'] if isinstance(response.data, dict) else response.data
        item = next(s for c in categories for s in c['services'] if s['id'] == service.pk)
        expected = ServicePrice.objects.get(salon_service__salon=self.salon,
                                            salon_service__service=service,
                                            level='art_director').amount
        self.assertEqual(item['masters'][0]['amount'], expected)

        response = self.client.get(f'/api/v1/service-categories/?salon={moscow.pk}')
        categories = response.data['results'] if isinstance(response.data, dict) else response.data
        item = next(s for c in categories for s in c['services'] if s['id'] == service.pk)
        self.assertEqual(item['prices'][0]['amount'], 99999)
        self.assertEqual(item['masters'], [])

    def test_admin_requires_review_before_apply(self):
        admin_user = get_user_model().objects.create_superuser('importer', 'importer@example.com', 'password')
        self.client.force_login(admin_user)
        url = reverse('admin:services_servicecategory_import_excel')
        source = next(path for path in PRICE_DIR.glob('*.xlsx') if 'ногтевого' in path.name)
        upload = SimpleUploadedFile(source.name, source.read_bytes())
        self.assertEqual(self.client.post(url, {'file': upload, 'salon': self.salon.pk}).status_code, 200)
        self.assertEqual(self.client.post(url, {'apply_selected': '1', 'selected_rows': ['9']}).status_code, 200)
        self.assertFalse(Service.objects.exists())
        self.assertEqual(self.client.post(url, {'review_matches': '1'}).status_code, 200)
        first_row = read_xlsx(source.read_bytes())['rows'][0]['row']
        self.assertEqual(self.client.post(url, {'apply_selected': '1',
                                                'selected_rows': [str(first_row)]}).status_code, 302)
        self.assertEqual(Service.objects.count(), 1)
        self.assertEqual(ServiceSalon.objects.get().salon, self.salon)

    def test_admin_can_select_red_gate_for_zelenograd_hair_file(self):
        red_gate = Salon.objects.create(name='Scissors Красные Ворота',
                                        slug='scissors-krasnye-vorota', address='Адрес',
                                        latitude=55, longitude=37)
        admin_user = get_user_model().objects.create_superuser('redgate', 'redgate@example.com', 'password')
        self.client.force_login(admin_user)
        url = reverse('admin:services_servicecategory_import_excel')
        source = next(path for path in PRICE_DIR.glob('*.xlsx') if 'парикмахерского' in path.name)
        first_row = read_xlsx(source.read_bytes())['rows'][0]['row']
        response = self.client.post(url, {'file': SimpleUploadedFile(source.name, source.read_bytes()),
                                          'salon': red_gate.pk})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Город в файле отличается')
        self.assertContains(response, 'Выбрать все')
        self.assertContains(response, 'Снять выбор')
        self.assertContains(response, 'id="select-all-rows"')
        self.assertContains(response, 'id="clear-selected-rows"')
        self.assertContains(response, f'name="selected_rows" value="{first_row}"')
        self.assertContains(response, 'excel-preview-table')
        self.assertContains(response, 'price-lines')
        self.assertContains(response, 'name="review_matches"')
        self.assertFalse(Service.objects.exists())
        self.assertEqual(self.client.post(url, {'review_matches': '1'}).status_code, 200)
        self.assertEqual(self.client.post(url, {'apply_selected': '1',
                                                'selected_rows': [str(first_row)]}).status_code, 302)
        self.assertEqual(ServiceSalon.objects.count(), 1)
        self.assertEqual(ServiceSalon.objects.get().salon, red_gate)
        self.assertFalse(ServiceSalon.objects.filter(salon=self.salon).exists())

    def test_unselected_row_error_does_not_block_selected_row(self):
        hair = next(p for p in self.previews() if p['kind'] == 'hair')
        first, second = hair['rows'][:2]
        hair['errors'] = ['Ошибка второй строки']
        hair['issues'] = [{'message': 'Ошибка второй строки', 'rows': [second['row']]}]
        self.assertGreater(apply_preview(hair, self.salon, {}, {first['row']}), 0)
        self.assertEqual(Service.objects.count(), 1)
        with self.assertRaisesRegex(ValueError, 'Ошибка второй строки'):
            apply_preview(hair, self.salon, {}, {second['row']})
        self.assertEqual(Service.objects.count(), 1)

    def test_admin_select_all_does_not_apply_without_checked_rows(self):
        admin_user = get_user_model().objects.create_superuser('allrows', 'allrows@example.com', 'password')
        self.client.force_login(admin_user)
        url = reverse('admin:services_servicecategory_import_excel')
        source = next(path for path in PRICE_DIR.glob('*.xlsx') if 'ногтевого' in path.name)
        row_numbers = [str(row['row']) for row in read_xlsx(source.read_bytes())['rows']]
        self.client.post(url, {'file': SimpleUploadedFile(source.name, source.read_bytes()),
                               'salon': self.salon.pk})
        self.client.post(url, {'review_matches': '1'})
        self.assertEqual(self.client.post(url, {'apply_all': '1'}).status_code, 200)
        self.assertFalse(Service.objects.exists())
        self.assertEqual(self.client.post(url, {'apply_selected': '1',
                                                'selected_rows': row_numbers}).status_code, 302)
        self.assertEqual(Service.objects.count(), 52)
        self.assertEqual(ServiceSalon.objects.filter(salon=self.salon).count(), 52)

    def test_import_link_is_an_unfold_button_in_both_lists(self):
        admin_user = get_user_model().objects.create_superuser('listbutton', 'listbutton@example.com', 'password')
        self.client.force_login(admin_user)
        import_url = reverse('admin:services_servicecategory_import_excel')
        for list_name in ('admin:services_servicecategory_changelist',
                          'admin:services_service_changelist'):
            with self.subTest(list_name=list_name):
                response = self.client.get(reverse(list_name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, f'href="{import_url}"')
                self.assertContains(response, 'table_view')
                self.assertContains(response, 'Импорт Excel-прайса')

    def test_booking_placeholder_is_not_a_priced_master(self):
        hair = next(p for p in self.previews() if p['kind'] == 'hair')
        apply_preview(hair, self.salon, {})
        service = Service.objects.get(title='Женская стрижка')
        placeholder = Master.objects.create(name='Лист Ожидания',
                                            yclients_user_id='technical',
                                            is_booking_placeholder=True)
        MasterSalon.objects.create(master=placeholder, salon=self.salon)
        ServiceStaffPrice.objects.create(service=service, master=placeholder, salon=self.salon)
        with self.assertRaises(ValidationError):
            placeholder.price_level = 'universal'
            placeholder.full_clean()
        response = self.client.get(f'/api/v1/service-categories/?salon={self.salon.pk}')
        categories = response.data['results'] if isinstance(response.data, dict) else response.data
        item = next(s for c in categories for s in c['services'] if s['id'] == service.pk)
        self.assertEqual(item['masters'], [])
        self.assertFalse(any(m['id'] == placeholder.pk for m in self.client.get('/api/v1/masters/').data['results']))
        options = self.client.get(f'/api/v1/booking-options/?salon={self.salon.pk}')
        self.assertFalse(any(m['id'] == placeholder.pk for m in options.data['masters']))

    def test_red_gate_only_allows_hair_catalogue(self):
        nails = next(p for p in self.previews() if p['kind'] == 'nails')
        apply_preview(nails, self.salon, {})
        moscow = Salon.objects.create(name='Scissors Красные Ворота', slug='scissors-krasnye-vorota',
                                      address='Адрес', latitude=55, longitude=37)
        service = Service.objects.filter(category__code='nails').first()
        with self.assertRaises(ValidationError):
            ServiceSalon(service=service, salon=moscow).full_clean()
        without_city = {**nails, 'city': None}
        with self.assertRaises(ValueError):
            apply_preview(without_city, moscow, {})


class UnifiedExcelImportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.zelenograd = Salon.objects.create(name='Scissors Зеленоград', slug='scissors-zelenograd-17mkr',
                                              address='Адрес', latitude=55, longitude=37)
        cls.moscow = Salon.objects.create(name='Scissors Красные Ворота', slug='scissors-krasnye-vorota',
                                          address='Адрес', latitude=55, longitude=37)

    def preview(self):
        return read_unified_xlsx((PRICE_DIR / 'SCISSORS-29.10.26.xlsx').read_bytes())

    def test_parser_reads_two_salons_codes_and_editorial_columns(self):
        preview = self.preview()
        self.assertEqual(preview['sheet'], 'Единый прайс 29.10.2026')
        self.assertEqual(len(preview['rows']), 242)
        self.assertEqual(preview['errors'], [])
        haircut = next(item for item in preview['rows'] if item['price_code'] == 'H-007')
        self.assertEqual(haircut['prices_by_city']['zelenograd'][0]['amount'], '2800.0')
        self.assertEqual(haircut['prices_by_city']['moscow'][0]['amount'], '3500.0')
        self.assertEqual(haircut['group'], 'Стрижки и мужской сервис')
        self.assertEqual(haircut['internal_category'], 'Вол')
        camouflage = next(item for item in preview['rows'] if item['price_code'] == 'H-012')
        self.assertTrue(camouflage['description'].startswith('Матирование'))
        luxury = next(item for item in preview['rows'] if item['price_code'] == 'H-27')
        self.assertTrue(luxury['title'].endswith('— короткие'))
        self.assertEqual({price['amount'] for price in luxury['prices_by_city']['moscow']}, {'1500.0'})
        brows = {item['price_code']: item for item in preview['rows']
                 if item['price_code'] in {'B-105', 'B-106', 'B-107'}}
        self.assertEqual(
            [(price['level'], price['amount']) for price in brows['B-105']['prices_by_city']['zelenograd']],
            [('modeler', '1900.0'), ('top_stylist', '2400.0'), ('art_director', '3500.0')],
        )
        self.assertEqual(
            [price['level'] for price in brows['B-107']['prices_by_city']['zelenograd']],
            ['modeler', 'top_stylist'],
        )

    def test_apply_updates_both_salons_and_preserves_service_page(self):
        preview = self.preview()
        category = ServiceCategory.objects.create(title='Для волос', code='hair')
        page_root = Page.objects.get(url_path='uslugi')
        category_page = Page.objects.create(parent=page_root, url='hair', title='Для волос')
        category.page = category_page
        category.save(update_fields=['page'])
        page = Page.objects.create(parent=category_page, url='zhenskaya-strizhka',
                                   title='Женская стрижка', content='<p>Текст редактора</p>')
        service = Service.objects.create(category=category, title='Женская стрижка',
                                         code='hair-existing-code', page=page)
        for salon in (self.zelenograd, self.moscow):
            offer = ServiceSalon.objects.create(service=service, salon=salon)
            ServicePrice.objects.create(salon_service=offer, level='universal', amount=2800)

        self.assertGreater(apply_unified_preview(preview, {'10': 'new'}, [5, 10]), 0)
        service.refresh_from_db()
        page.refresh_from_db()
        self.assertEqual(service.price_code, 'H-007')
        self.assertEqual(service.code, 'hair-existing-code')
        self.assertEqual(page.content, '<p>Текст редактора</p>')
        self.assertEqual(ServicePrice.objects.get(salon_service__service=service,
                                                  salon_service__salon=self.zelenograd,
                                                  level='universal').amount, 2800)
        self.assertEqual(ServicePrice.objects.get(salon_service__service=service,
                                                  salon_service__salon=self.moscow,
                                                  level='universal').amount, 3500)
        camouflage = Service.objects.get(price_code='H-012')
        self.assertTrue(camouflage.description.startswith('Матирование'))
        self.assertEqual(camouflage.price_internal_category, 'Вол')
        self.assertEqual(apply_unified_preview(preview, {}, [5, 10]), 0)

    def test_brow_tiers_import_and_catalogue_show_only_priced_levels(self):
        preview = self.preview()
        self.assertGreater(apply_unified_preview(preview, {'94': 'new', '96': 'new'}, [94, 96]), 0)
        category = ServiceCategory.objects.get(code='browlashes')
        self.assertEqual(category.code, 'browlashes')
        response = self.client.get(f'/api/v1/service-categories/?salon={self.zelenograd.pk}')
        self.assertEqual(response.status_code, 200)
        categories = response.data['results'] if isinstance(response.data, dict) else response.data
        services = {service['id']: service for service in
                    next(item for item in categories if item['code'] == 'browlashes')['services']}
        self.assertEqual(
            [(price['level'], price['amount']) for price in
             services[Service.objects.get(price_code='B-105').pk]['prices']],
            [('modeler', 1900), ('top_stylist', 2400), ('art_director', 3500)],
        )
        self.assertEqual([price['level'] for price in
                          services[Service.objects.get(price_code='B-107').pk]['prices']],
                         ['modeler', 'top_stylist'])
        self.assertEqual(apply_unified_preview(preview, {}, [94, 96]), 0)

    def test_reimport_adds_and_removes_price_levels_for_any_category(self):
        preview = self.preview()
        apply_unified_preview(preview, {'5': 'new', '94': 'new'}, [5, 94])
        haircut = Service.objects.get(price_code='H-007')
        brows = Service.objects.get(price_code='B-105')
        hair_offer = ServiceSalon.objects.get(service=haircut, salon=self.zelenograd)
        brow_offer = ServiceSalon.objects.get(service=brows, salon=self.zelenograd)
        removed_level = preview['rows'][0]['prices_by_city']['zelenograd'][0]['level']
        changed = deepcopy(preview)
        changed_hair = next(item for item in changed['rows'] if item['row'] == 5)
        changed_hair['prices_by_city']['zelenograd'] = [
            price for price in changed_hair['prices_by_city']['zelenograd']
            if price['level'] != removed_level
        ]
        changed_brow = next(item for item in changed['rows'] if item['row'] == 94)
        changed_brow['prices_by_city']['zelenograd'] = [
            price for price in changed_brow['prices_by_city']['zelenograd']
            if price['level'] != 'art_director'
        ]
        apply_unified_preview(changed, {}, [5, 94])
        self.assertFalse(hair_offer.prices.filter(level=removed_level).exists())
        self.assertFalse(brow_offer.prices.filter(level='art_director').exists())
        apply_unified_preview(preview, {}, [5, 94])
        self.assertTrue(hair_offer.prices.filter(level=removed_level).exists())
        self.assertTrue(brow_offer.prices.filter(level='art_director').exists())

    def test_unified_import_does_not_republish_inactive_service(self):
        preview = self.preview()
        item = next(item for item in preview['rows'] if item['price_code'] == 'C-267')
        category = ServiceCategory.objects.create(title='Косметология', code='cosmetology')
        service = Service.objects.create(category=category, title=item['title'],
                                         description='Снята с публикации', is_active=False)
        offer = ServiceSalon.objects.create(service=service, salon=self.zelenograd, is_active=False)

        apply_unified_preview(preview, {}, [item['row']])

        service.refresh_from_db()
        offer.refresh_from_db()
        self.assertFalse(service.is_active)
        self.assertFalse(offer.is_active)
        self.assertEqual(service.description, 'Снята с публикации')
        self.assertEqual(service.price_code, 'C-267')

    def test_admin_imports_both_salons_without_salon_selector(self):
        user = get_user_model().objects.create_superuser('unified-importer', 'importer@example.com', 'password')
        self.client.force_login(user)
        url = reverse('admin:services_servicecategory_import_excel')
        self.assertNotContains(self.client.get(url), 'name="salon"')
        source = PRICE_DIR / 'SCISSORS-29.10.26.xlsx'
        response = self.client.post(url, {'file': SimpleUploadedFile(source.name, source.read_bytes())})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'H-007')
        self.assertNotContains(response, 'name="salon"')
        self.assertContains(response, 'href="#price-row-89"')
        self.assertContains(response, 'id="price-row-89" class="price-row-problem"')
        self.assertContains(response, 'action="' + url + '"')
        self.assertContains(response, 'id="apply-selected-rows"')
        self.assertContains(response, 'services/js/unified_excel_import.js')
        self.assertNotContains(response, 'services/js/excel_import_selection.js')
        row_89 = next(row for row in response.context['rows'] if row['row'] == 89)
        self.assertTrue(row_89['errors'])
        self.assertFalse(row_89['checked'])
        no_selection = self.client.post(url, {'apply_selected': '1'})
        self.assertContains(no_selection, 'Прайс не применён.')
        self.assertContains(no_selection, 'Отметьте существующие строки прайса')
        unresolved = self.client.post(url, {'apply_selected': '1', 'selected_rows': ['89']})
        self.assertContains(unresolved, 'Прайс не применён.')
        self.assertContains(unresolved, 'Перейти к строке 89')
        reviewed = self.client.post(url, {'review_matches': '1', 'match_89': 'new',
                                          'selected_rows': ['89']})
        self.assertEqual(reviewed.status_code, 200)
        row_89 = next(row for row in reviewed.context['rows'] if row['row'] == 89)
        self.assertFalse(row_89['errors'])
        self.assertTrue(row_89['checked'])
        response = self.client.post(url, {'apply_selected': '1', 'match_5': 'new', 'selected_rows': ['5']})
        self.assertEqual(response.status_code, 302)
        haircut = Service.objects.get(price_code='H-007')
        self.assertEqual(ServiceSalon.objects.filter(service=haircut).count(), 2)
        response = self.client.post(url, {'file': SimpleUploadedFile(source.name, source.read_bytes())})
        row_5 = next(row for row in response.context['rows'] if row['row'] == 5)
        self.assertFalse(row_5['errors'])
        self.assertTrue(row_5['checked'])

    def test_unified_price_matches_existing_catalogue_without_duplicate_services(self):
        for source in PRICE_DIR.glob('*.xlsx'):
            if source.name.startswith('SCISSORS-'):
                continue
            legacy = read_xlsx(source.read_bytes())
            apply_preview(legacy, self.zelenograd, {})
            if legacy['kind'] == 'hair':
                apply_preview(legacy, self.moscow, {})
        self.assertEqual(Service.objects.filter(category__code__isnull=False).count(), 239)
        preview = self.preview()
        selected = [item['row'] for item in preview['rows']]
        renamed = Service.objects.get(category__code='hair', title='Экспресс коррекция Желтого')
        matches = {str(row): 'new' for row in (37, 89, 90, 91, 92)}

        self.assertGreater(apply_unified_preview(preview, matches, selected), 0)

        renamed.refresh_from_db()
        self.assertEqual(renamed.price_code, 'H-044')
        self.assertEqual(Service.objects.filter(price_code__isnull=False).count(), len(selected))
        self.assertEqual(Service.objects.filter(category__code__isnull=False).count(), 244)
        self.assertEqual(ServicePrice.objects.get(salon_service__service__price_code='H-007',
                                                  salon_service__salon=self.moscow,
                                                  level='universal').amount, 3500)
        brow = Service.objects.get(price_code='B-105')
        self.assertEqual(brow.category.code, 'browlashes')
        self.assertEqual(
            set(ServicePrice.objects.filter(salon_service__service=brow,
                                            salon_service__salon=self.zelenograd)
                .values_list('level', flat=True)),
            {'modeler', 'top_stylist', 'art_director'},
        )
        self.assertFalse(ServicePrice.objects.filter(salon_service__service=brow,
                                                     level='').exists())
