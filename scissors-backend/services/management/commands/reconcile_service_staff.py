"""Restore booking assignments on Excel services from reviewed YCLIENTS aliases.

The bundled manifest identifies equivalent services, not prices.  Legacy
services remain historical records; only their staff assignments are read.
"""

import json
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from masters.models import MasterSalon
from services.excel_import import CATEGORIES
from services.models import Service, ServicePrice, ServiceSalon, ServiceStaffPrice


DEFAULT_MANIFEST = Path(__file__).resolve().parents[2] / 'legacy_staff_matches.json'


def same_title(left, right):
    def normalized(value):
        return ' '.join(unicodedata.normalize('NFKC', value).casefold().split())
    return normalized(left) == normalized(right)


def short_title(value):
    """The Russian service name precedes the optional YCLIENTS label after |."""
    return ' '.join(unicodedata.normalize('NFKC', value.split('|', 1)[0]).casefold().split())


def load_manifest(path):
    try:
        entries = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise CommandError(f'Не удалось прочитать таблицу соответствий {path}: {exc}') from exc
    if not isinstance(entries, list):
        raise CommandError('Таблица соответствий должна содержать список услуг.')
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict) or not all(
            key in entry for key in ('category', 'service_code', 'service_title', 'legacy_services')
        ):
            raise CommandError('В таблице соответствий есть неполная запись.')
        if entry['category'] not in CATEGORIES or entry['service_code'] in seen:
            raise CommandError(f'Неизвестная категория или повтор услуги: {entry["service_code"]}')
        seen.add(entry['service_code'])
        if not isinstance(entry['legacy_services'], list) or not entry['legacy_services']:
            raise CommandError(f'Нет старых услуг для {entry["service_code"]}.')
        if any(not isinstance(source, dict) for source in entry['legacy_services']):
            raise CommandError(f'Неверная запись старой услуги для {entry["service_code"]}.')
        source_ids = [source.get('yclients_service_id') for source in entry['legacy_services']]
        if None in source_ids or len(source_ids) != len(set(source_ids)) or any(
            not source.get('title') or source.get('allow_inactive_source', False) not in (True, False)
            or source.get('allow_title_fallback', False) not in (True, False)
            for source in entry['legacy_services']
        ):
            raise CommandError(f'Неверные идентификаторы старых услуг для {entry["service_code"]}.')
    return entries


def build_plan(entries):
    """Read current DB state and return additions plus explicit review reasons."""
    catalogue = list(Service.objects.filter(
        category__code__in=CATEGORIES, category__is_active=True, is_active=True,
    ).select_related('category'))
    targets = {service.code: service for service in catalogue if service.code}
    source_ids = {
        source['yclients_service_id'] for entry in entries
        for source in entry['legacy_services']
    }
    sources = {
        service.yclients_service_id: service
        for service in Service.objects.filter(yclients_service_id__in=source_ids).select_related('category')
    }
    fallback_titles = {
        short_title(source['title']) for entry in entries for source in entry['legacy_services']
        if source.get('allow_title_fallback')
    }
    fallback_candidates = defaultdict(list)
    if fallback_titles:
        for service in Service.objects.exclude(yclients_service_id__isnull=True).select_related('category'):
            title = short_title(service.title)
            if title in fallback_titles and service.category.code not in CATEGORIES:
                fallback_candidates[title].append(service)
    target_ids = {service.pk for service in catalogue}
    legacy_ids = {service.pk for service in sources.values()}
    legacy_ids.update(service.pk for group in fallback_candidates.values() for service in group)
    offers = defaultdict(set)
    for service_id, salon_id in ServiceSalon.objects.filter(
        service_id__in=target_ids, is_active=True, salon__is_active=True,
    ).values_list('service_id', 'salon_id'):
        offers[service_id].add(salon_id)
    priced_levels = defaultdict(set)
    for service_id, salon_id, level in ServicePrice.objects.filter(
        salon_service__service_id__in=target_ids, salon_service__is_active=True,
    ).values_list('salon_service__service_id', 'salon_service__salon_id', 'level'):
        priced_levels[(service_id, salon_id)].add(level)
    legacy_offers = set(ServiceSalon.objects.filter(
        service_id__in=legacy_ids, is_active=True,
    ).values_list('service_id', 'salon_id'))
    source_assignments = defaultdict(list)
    master_ids = set()
    for assignment in ServiceStaffPrice.objects.filter(service_id__in=legacy_ids).select_related('master'):
        source_assignments[assignment.service_id].append(assignment)
        master_ids.add(assignment.master_id)
    master_salons = defaultdict(set)
    for master_id, salon_id in MasterSalon.objects.filter(master_id__in=master_ids).values_list(
        'master_id', 'salon_id',
    ):
        master_salons[master_id].add(salon_id)
    existing = set(ServiceStaffPrice.objects.filter(service_id__in=target_ids).values_list(
        'service_id', 'master_id', 'salon_id',
    ))

    plan = {
        'catalogue_count': len(catalogue), 'mapped_count': 0,
        'unmapped': [
            {'id': service.pk, 'category': service.category.code, 'title': service.title}
            for service in catalogue if service.code not in {entry['service_code'] for entry in entries}
        ],
        'without_staff': [], 'issues': [], 'skipped': Counter(), 'additions': {},
        'reviewed_inactive_sources': 0, 'title_fallbacks': [],
    }
    for entry in entries:
        target = targets.get(entry['service_code'])
        if not target:
            plan['issues'].append(f'{entry["service_code"]}: нет действующей услуги Excel с этим кодом.')
            continue
        if target.category.code != entry['category'] or not same_title(target.title, entry['service_title']):
            plan['issues'].append(f'{entry["service_code"]}: название или категория Excel изменились.')
            continue
        plan['mapped_count'] += 1
        target_has_candidate = False
        for listed_source in entry['legacy_services']:
            source = sources.get(listed_source['yclients_service_id'])
            if (not source or not same_title(source.title, listed_source['title'])) and listed_source.get(
                'allow_title_fallback', False,
            ):
                candidates = fallback_candidates[short_title(listed_source['title'])]
                if len(candidates) == 1:
                    source = candidates[0]
                    plan['title_fallbacks'].append({
                        'service_code': entry['service_code'],
                        'expected_yclients_service_id': listed_source['yclients_service_id'],
                        'actual_yclients_service_id': source.yclients_service_id,
                        'actual_title': source.title,
                    })
                else:
                    source = None
                    if len(candidates) > 1:
                        plan['issues'].append(
                            f'{entry["service_code"]}: несколько старых услуг с названием '
                            f'{listed_source["title"]}; требуется ручное сопоставление.'
                        )
                        continue
            if not source or source.category.code in CATEGORIES or (
                not source.is_active and not listed_source.get('allow_inactive_source', False)
            ) or (not same_title(source.title, listed_source['title']) and not listed_source.get(
                'allow_title_fallback', False,
            )):
                plan['issues'].append(
                    f'{entry["service_code"]}: старая услуга {listed_source["yclients_service_id"]} '
                    'отсутствует, выключена без подтверждения или изменила название.'
                )
                continue
            if not source.is_active:
                plan['reviewed_inactive_sources'] += 1
            for assignment in source_assignments[source.pk]:
                master = assignment.master
                if not master.is_active or master.is_system or master.is_booking_placeholder:
                    plan['skipped']['technical_or_inactive_master'] += 1
                    continue
                if (source.pk, assignment.salon_id) not in legacy_offers:
                    plan['skipped']['inactive_legacy_offer'] += 1
                    continue
                salons = master_salons[master.pk]
                if assignment.salon_id in salons:
                    salon_id, route = assignment.salon_id, 'same_salon'
                elif len(salons) == 1:
                    salon_id, route = next(iter(salons)), 'corrected_legacy_salon'
                else:
                    plan['skipped']['ambiguous_master_salon'] += 1
                    continue
                available_levels = priced_levels[(target.pk, salon_id)]
                if salon_id not in offers[target.pk] or not available_levels:
                    plan['skipped']['not_offered_or_priced_in_salon'] += 1
                    continue
                if master.name == 'Михаил Стець' and target.category.code not in {'hair', 'forman'}:
                    plan['skipped']['mikhail_non_hair'] += 1
                    continue
                if route == 'corrected_legacy_salon' and target.category.code in {'hair', 'forman'} and not master.price_level:
                    plan['skipped']['unconfirmed_hair_specialist'] += 1
                    continue
                if route == 'corrected_legacy_salon' and target.category.code in {'cosmetology', 'epilation'}:
                    plan['skipped']['unconfirmed_non_hair_specialist'] += 1
                    continue
                if master.price_level and '' not in available_levels and master.price_level not in available_levels:
                    plan['skipped']['no_price_for_master_level'] += 1
                    continue
                target_has_candidate = True
                key = (target.pk, master.pk, salon_id)
                if key in existing:
                    plan['skipped']['already_assigned'] += 1
                    continue
                current = plan['additions'].get(key)
                if current is None:
                    plan['additions'][key] = {
                        'service_id': target.pk, 'service_title': target.title,
                        'category': target.category.code, 'master_id': master.pk,
                        'master_name': master.name, 'master_price_level': master.price_level,
                        'salon_id': salon_id, 'route': route,
                        'legacy_yclients_service_ids': [source.yclients_service_id],
                    }
                else:
                    if source.yclients_service_id not in current['legacy_yclients_service_ids']:
                        current['legacy_yclients_service_ids'].append(source.yclients_service_id)
                    if route == 'same_salon':
                        current['route'] = route
        if not target_has_candidate and not any(key[0] == target.pk for key in existing):
            plan['without_staff'].append({
                'id': target.pk, 'category': target.category.code, 'title': target.title,
            })
    plan['additions'] = sorted(plan['additions'].values(), key=lambda item: (
        item['category'], item['service_title'], item['salon_id'], item['master_name'],
    ))
    plan['masters_without_price_level'] = sorted({
        item['master_name'] for item in plan['additions']
        if item['category'] in {'hair', 'forman', 'nails'} and not item['master_price_level']
    })
    plan['unmapped'].sort(key=lambda item: (item['category'], item['title']))
    return plan


class Command(BaseCommand):
    help = 'Сопоставляет услуги Excel со старыми YCLIENTS-услугами и переносит только назначения мастеров.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Применить проверенные назначения; без флага только предпросмотр.')
        parser.add_argument('--strict', action='store_true', help='При любом несовпадении не применять ни одного назначения.')
        parser.add_argument('--manifest', type=Path, default=DEFAULT_MANIFEST, help='JSON с проверенными соответствиями услуг.')
        parser.add_argument('--report', type=Path, help='Сохранить подробный JSON-отчёт предпросмотра.')
        parser.add_argument('--verbose', action='store_true', help='Показать каждое назначение и услуги без соответствий.')

    def handle(self, *args, **options):
        entries = load_manifest(options['manifest'])
        if options['apply']:
            with transaction.atomic():
                plan = build_plan(entries)
                if options['strict'] and plan['issues']:
                    raise CommandError('Данные изменились; исправьте соответствия после предпросмотра. '
                                       + '; '.join(plan['issues'][:3]))
                created = 0
                for item in plan['additions']:
                    assignment = ServiceStaffPrice(
                        service_id=item['service_id'], master_id=item['master_id'],
                        salon_id=item['salon_id'],
                    )
                    try:
                        assignment.full_clean()
                    except ValidationError as exc:
                        raise CommandError(
                            f'Назначение услуги {item["service_id"]} мастеру {item["master_id"]} '
                            f'не прошло проверку: {exc}'
                        ) from exc
                    assignment.save()
                    created += 1
        else:
            plan = build_plan(entries)
            created = 0

        if options['report']:
            report = {**plan, 'skipped': dict(plan['skipped']), 'applied': created}
            options['report'].write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        routes = Counter(item['route'] for item in plan['additions'])
        self.stdout.write(
            f'Услуг Excel: {plan["catalogue_count"]}; с проверенным соответствием: {plan["mapped_count"]}; '
            f'новых назначений: {len(plan["additions"])} '
            f'(тот же салон: {routes["same_salon"]}, исправленный старый салон: '
            f'{routes["corrected_legacy_salon"]}); применено: {created}.'
        )
        self.stdout.write(
            f'Без старого соответствия: {len(plan["unmapped"])}; '
            f'с соответствием, но без действующего мастера: {len(plan["without_staff"])}; '
            f'проверенных выключенных старых строк: {plan["reviewed_inactive_sources"]}; '
            f'сопоставлений по названию: {len(plan["title_fallbacks"])}; '
            f'ошибок сверки: {len(plan["issues"])}.'
        )
        if plan['masters_without_price_level']:
            self.stdout.write('Без подтверждённого уровня парикмахерского прайса: '
                              + ', '.join(plan['masters_without_price_level']))
        for issue in plan['issues']:
            self.stdout.write(self.style.WARNING(issue))
        for item in plan['without_staff']:
            self.stdout.write(f'Без мастера: {item["category"]} #{item["id"]} {item["title"]}')
        if options['verbose']:
            for item in plan['unmapped']:
                self.stdout.write(f'Нет старой пары: {item["category"]} #{item["id"]} {item["title"]}')
            for item in plan['additions']:
                self.stdout.write(
                    f'{item["category"]} #{item["service_id"]} {item["service_title"]} '
                    f'→ {item["master_name"]} (салон #{item["salon_id"]}, {item["route"]})'
                )
