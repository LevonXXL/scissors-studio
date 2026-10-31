import json
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from masters.models import Master, MasterSalon
from salons.models import Salon

from .models import Service, ServiceCategory, ServicePrice, ServiceSalon, ServiceStaffPrice


class ReconcileServiceStaffTests(TestCase):
    def setUp(self):
        self.zelenograd = Salon.objects.create(
            name='Зеленоград', address='Адрес', latitude=55, longitude=37,
        )
        self.red_gate = Salon.objects.create(
            name='Красные Ворота', slug='scissors-krasnye-vorota',
            address='Адрес', latitude=55, longitude=37,
        )
        self.category = ServiceCategory.objects.create(
            title='Для мужчин', code='forman',
        )
        self.legacy_category = ServiceCategory.objects.create(
            title='Стрижки', is_active=False,
        )
        self.current = Service.objects.create(
            category=self.category, code='forman-test-cut', title='Мужская стрижка',
        )
        self.legacy = Service.objects.create(
            category=self.legacy_category, yclients_service_id='legacy-cut',
            title='Мужская стрижка | Mens Cut',
        )
        for salon in (self.zelenograd, self.red_gate):
            offer = ServiceSalon.objects.create(service=self.current, salon=salon)
            ServicePrice.objects.create(
                salon_service=offer, level='art_director', amount=8500,
            )
        ServiceSalon.objects.create(service=self.legacy, salon=self.red_gate)
        self.direct = Master.objects.create(
            name='Михаил Стець', price_level='art_director',
        )
        self.relocated = Master.objects.create(
            name='Оксана', price_level='art_director',
        )
        self.cosmetologist = Master.objects.create(
            name='Анна',
        )
        self.placeholder = Master.objects.create(
            name='Лист Ожидания', is_booking_placeholder=True,
        )
        MasterSalon.objects.create(master=self.direct, salon=self.red_gate)
        MasterSalon.objects.create(master=self.relocated, salon=self.zelenograd)
        MasterSalon.objects.create(master=self.cosmetologist, salon=self.zelenograd)
        MasterSalon.objects.create(master=self.placeholder, salon=self.red_gate)
        for master in (self.direct, self.relocated, self.cosmetologist, self.placeholder):
            ServiceStaffPrice.objects.create(
                service=self.legacy, master=master, salon=self.red_gate,
                price_min=1000, duration_seconds=3600,
            )

    def manifest(self, directory, title='Мужская стрижка', allow_inactive=False):
        path = Path(directory) / 'matches.json'
        path.write_text(json.dumps([{
            'category': 'forman', 'service_code': 'forman-test-cut',
            'service_title': title, 'legacy_services': [{
                'yclients_service_id': 'legacy-cut', 'title': 'Мужская стрижка | Mens Cut',
                **({'allow_inactive_source': True} if allow_inactive else {}),
            }],
        }]), encoding='utf-8')
        return path

    def test_preview_apply_and_repeat_preserve_old_prices_and_assignments(self):
        with TemporaryDirectory() as directory:
            manifest = self.manifest(directory)
            output = StringIO()
            call_command('reconcile_service_staff', manifest=manifest, stdout=output)
            self.assertIn('новых назначений: 2', output.getvalue())
            self.assertFalse(ServiceStaffPrice.objects.filter(service=self.current).exists())

            call_command('reconcile_service_staff', manifest=manifest, apply=True, stdout=StringIO())
            self.assertEqual(set(ServiceStaffPrice.objects.filter(service=self.current).values_list(
                'master_id', 'salon_id',
            )), {(self.direct.pk, self.red_gate.pk), (self.relocated.pk, self.zelenograd.pk)})
            self.assertTrue(all(
                assignment.price_min is None and assignment.duration_seconds is None
                for assignment in ServiceStaffPrice.objects.filter(service=self.current)
            ))
            self.assertEqual(ServiceStaffPrice.objects.filter(service=self.legacy).count(), 4)
            call_command('reconcile_service_staff', manifest=manifest, apply=True, stdout=output)
            self.assertEqual(ServiceStaffPrice.objects.filter(service=self.current).count(), 2)

    def test_known_master_level_without_price_is_not_assigned(self):
        offer = ServiceSalon.objects.get(service=self.current, salon=self.red_gate)
        ServicePrice.objects.filter(salon_service=offer, level='art_director').delete()
        with TemporaryDirectory() as directory:
            call_command('reconcile_service_staff', manifest=self.manifest(directory),
                         apply=True, stdout=StringIO())
        self.assertFalse(ServiceStaffPrice.objects.filter(service=self.current, master=self.direct).exists())
        self.assertTrue(ServiceStaffPrice.objects.filter(service=self.current, master=self.relocated).exists())

    def test_existing_manual_assignment_is_kept(self):
        manual = ServiceStaffPrice.objects.create(
            service=self.current, master=self.direct, salon=self.red_gate,
            price_min=1234, duration_seconds=1800,
        )
        with TemporaryDirectory() as directory:
            output = StringIO()
            call_command('reconcile_service_staff', manifest=self.manifest(directory),
                         apply=True, stdout=output)
        manual.refresh_from_db()
        self.assertEqual(manual.price_min, 1234)
        self.assertEqual(manual.duration_seconds, 1800)
        self.assertIn('применено: 1', output.getvalue())

    def test_reviewed_inactive_old_service_can_supply_staff_only(self):
        self.legacy.is_active = False
        self.legacy.save(update_fields=['is_active'])
        with TemporaryDirectory() as directory:
            with self.assertRaises(CommandError):
                call_command('reconcile_service_staff', manifest=self.manifest(directory),
                             apply=True, strict=True, stdout=StringIO())
            manifest = self.manifest(directory, allow_inactive=True)
            call_command('reconcile_service_staff', manifest=manifest, apply=True, stdout=StringIO())
        self.assertEqual(ServiceStaffPrice.objects.filter(service=self.current).count(), 2)
        self.legacy.refresh_from_db()
        self.assertFalse(self.legacy.is_active)

    def test_changed_catalogue_title_blocks_apply(self):
        with TemporaryDirectory() as directory:
            with self.assertRaises(CommandError):
                call_command('reconcile_service_staff', manifest=self.manifest(directory, 'Другая услуга'),
                             apply=True, strict=True, stdout=StringIO())
        self.assertFalse(ServiceStaffPrice.objects.filter(service=self.current).exists())

    def test_missing_old_row_does_not_block_other_checked_matches(self):
        with TemporaryDirectory() as directory:
            manifest = self.manifest(directory)
            rows = json.loads(manifest.read_text())
            rows.append({
                'category': 'forman', 'service_code': 'forman-missing-source',
                'service_title': 'Оформление бороды', 'legacy_services': [{
                    'yclients_service_id': 'missing-old-row', 'title': 'Оформление бороды | Beard Cut',
                }],
            })
            beard = Service.objects.create(
                category=self.category, code='forman-missing-source', title='Оформление бороды',
            )
            offer = ServiceSalon.objects.create(service=beard, salon=self.red_gate)
            ServicePrice.objects.create(salon_service=offer, level='art_director', amount=1000)
            manifest.write_text(json.dumps(rows))
            with self.assertRaises(CommandError):
                call_command('reconcile_service_staff', manifest=manifest,
                             apply=True, strict=True, stdout=StringIO())
            self.assertFalse(ServiceStaffPrice.objects.filter(service=self.current).exists())

            output = StringIO()
            call_command('reconcile_service_staff', manifest=manifest, apply=True, stdout=output)
            self.assertIn('ошибок сверки: 1', output.getvalue())
            self.assertEqual(ServiceStaffPrice.objects.filter(service=self.current).count(), 2)
            self.assertFalse(ServiceStaffPrice.objects.filter(service=beard).exists())

    def test_unique_reviewed_title_fallback_uses_changed_old_id(self):
        self.legacy.yclients_service_id = 'replacement-id'
        self.legacy.title = 'Мужская стрижка | Man Cut'
        self.legacy.save(update_fields=['yclients_service_id', 'title'])
        with TemporaryDirectory() as directory:
            manifest = self.manifest(directory)
            rows = json.loads(manifest.read_text())
            rows[0]['legacy_services'][0]['allow_title_fallback'] = True
            manifest.write_text(json.dumps(rows))
            output = StringIO()
            call_command('reconcile_service_staff', manifest=manifest, apply=True, stdout=output)
        self.assertIn('сопоставлений по названию: 1', output.getvalue())
        self.assertEqual(ServiceStaffPrice.objects.filter(service=self.current).count(), 2)

    def test_ambiguous_title_fallback_is_skipped(self):
        self.legacy.yclients_service_id = 'replacement-id'
        self.legacy.save(update_fields=['yclients_service_id'])
        Service.objects.create(
            category=self.legacy_category, yclients_service_id='other-id',
            title='Мужская стрижка | Other Cut',
        )
        with TemporaryDirectory() as directory:
            manifest = self.manifest(directory)
            rows = json.loads(manifest.read_text())
            rows[0]['legacy_services'][0]['allow_title_fallback'] = True
            manifest.write_text(json.dumps(rows))
            output = StringIO()
            call_command('reconcile_service_staff', manifest=manifest, apply=True, stdout=output)
        self.assertIn('несколько старых услуг', output.getvalue())
        self.assertFalse(ServiceStaffPrice.objects.filter(service=self.current).exists())

    def test_relocated_epilation_without_verified_specialist_is_skipped(self):
        epilation = ServiceCategory.objects.create(title='Эпиляция', code='epilation')
        current = Service.objects.create(category=epilation, code='epilation-wax', title='Воск S')
        legacy = Service.objects.create(
            category=self.legacy_category, yclients_service_id='legacy-wax', title='Воск S | Wax',
        )
        offer = ServiceSalon.objects.create(service=current, salon=self.zelenograd)
        ServicePrice.objects.create(salon_service=offer, level='', amount=1000)
        ServiceSalon.objects.create(service=legacy, salon=self.red_gate)
        for master in (self.relocated, self.cosmetologist):
            ServiceStaffPrice.objects.create(service=legacy, master=master, salon=self.red_gate)
        with TemporaryDirectory() as directory:
            manifest = Path(directory) / 'matches.json'
            manifest.write_text(json.dumps([{
                'category': 'epilation', 'service_code': current.code,
                'service_title': current.title, 'legacy_services': [{
                    'yclients_service_id': 'legacy-wax', 'title': legacy.title,
                }],
            }]), encoding='utf-8')
            call_command('reconcile_service_staff', manifest=manifest, apply=True, stdout=StringIO())
        self.assertFalse(ServiceStaffPrice.objects.filter(service=current).exists())
