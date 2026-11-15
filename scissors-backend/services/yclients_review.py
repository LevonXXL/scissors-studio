"""Preview YCLIENTS staff assignments without importing its catalogue or prices."""

import json
import unicodedata
from collections import defaultdict
from difflib import get_close_matches
from pathlib import Path

from django.core.exceptions import ValidationError
from django.db import transaction

from masters.models import MasterSalon
from salons.models import Salon
from sync.identifiers import yclients_id

from .models import Service, ServiceSalon, ServiceStaffPrice, YClientsServiceMatch


MANIFEST = Path(__file__).with_name('legacy_staff_matches.json')
AI_SUGGESTIONS = Path(__file__).with_name('ai_service_suggestions.json')


def normalize_title(value):
    return ' '.join(unicodedata.normalize('NFKC', value or '').casefold().split())


def base_title(value):
    """Ignore the optional YCLIENTS label after the first vertical bar."""
    return normalize_title((value or '').split('|', 1)[0])


def positive_seconds(value):
    if isinstance(value, bool):
        return None
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        return None
    return seconds if seconds > 0 else None


def fetch_rows(client, salons):
    """Keep only fields needed for review; never keep YCLIENTS prices."""
    rows = []
    seen_keys = set()
    for salon in salons:
        services = client.get_services(salon.yclients_company_id)
        if not isinstance(services, list):
            raise ValueError(f'YCLIENTS вернул неверный список услуг салона «{salon}».')
        for source in services:
            if not isinstance(source, dict) or source.get('active') is False or source.get('active') == 0:
                continue
            source_id = yclients_id(source.get('id'))
            if not source_id:
                continue
            key = f'{salon.pk}:{source_id}'
            if key in seen_keys:
                raise ValueError(f'YCLIENTS вернул услугу #{source_id} дважды для салона «{salon}».')
            seen_keys.add(key)
            source_staff = source.get('staff') or []
            if not isinstance(source_staff, list):
                raise ValueError(f'YCLIENTS вернул неверный список мастеров услуги #{source_id}.')
            staff = []
            seen_staff = set()
            for member in source_staff:
                if not isinstance(member, dict):
                    continue
                staff_id = yclients_id(member.get('id'))
                if not staff_id or staff_id in seen_staff:
                    continue
                seen_staff.add(staff_id)
                staff.append({
                    'id': staff_id,
                    'name': str(member.get('name') or ''),
                    'duration_seconds': positive_seconds(member.get('seance_length')),
                })
            rows.append({
                'key': key,
                'salon_id': salon.pk,
                'source_id': source_id,
                'title': str(source.get('title') or '')[:1024],
                'category_id': str(source.get('category_id') or ''),
                'staff': staff,
            })
    if len(rows) > 2000:
        raise ValueError('YCLIENTS вернул более 2000 услуг; проверку нужно разбить по салонам.')
    return rows


def manifest_index():
    entries = json.loads(MANIFEST.read_text(encoding='utf-8'))
    index = defaultdict(set)
    for entry in entries:
        for source in entry['legacy_services']:
            index[str(source['yclients_service_id'])].add(entry['service_code'])
    return index


def ai_suggestion_index():
    """Human-readable name comparisons; hints only, never selected automatically."""
    entries = json.loads(AI_SUGGESTIONS.read_text(encoding='utf-8'))
    return {(str(entry['yclients_service_id']), normalize_title(entry['source_title'])):
            entry['service_code'] for entry in entries}


def review_rows(snapshot):
    """Recompute candidates and staff links against the current database."""
    salon_ids = {row['salon_id'] for row in snapshot}
    salons = {salon.pk: salon for salon in Salon.objects.filter(pk__in=salon_ids)}
    services_by_salon = defaultdict(list)
    for offer in ServiceSalon.objects.filter(
        salon_id__in=salon_ids, is_active=True, salon__is_active=True,
        service__is_active=True, service__category__is_active=True,
        service__price_code__isnull=False,
    ).select_related('service'):
        if not offer.service.price_code:
            continue
        services_by_salon[offer.salon_id].append(offer.service)
    links = defaultdict(dict)
    for link in MasterSalon.objects.filter(salon_id__in=salon_ids).select_related('master'):
        if staff_id := yclients_id(link.yclients_staff_id):
            links[link.salon_id][staff_id] = link.master
    saved = defaultdict(set)
    for match in YClientsServiceMatch.objects.filter(salon_id__in=salon_ids):
        saved[(match.salon_id, match.yclients_service_id)].add(match.service_id)
    existing_assignments = set(ServiceStaffPrice.objects.filter(
        salon_id__in=salon_ids,
    ).values_list('salon_id', 'service_id', 'master_id'))
    manifest = manifest_index()
    ai_suggestions = ai_suggestion_index()
    unlinked_index = {}
    title_index = {}
    base_index = {}
    code_index = {}
    for salon_id in salon_ids:
        services = services_by_salon[salon_id]
        titles = defaultdict(set)
        bases = defaultdict(set)
        codes = defaultdict(set)
        for service in services:
            titles[normalize_title(service.title)].add(service.pk)
            bases[base_title(service.title)].add(service.pk)
            codes[service.code].add(service.pk)
        title_index[salon_id] = titles
        base_index[salon_id] = bases
        code_index[salon_id] = codes
        unlinked_index[salon_id] = [service for service in services
                                    if not service.yclients_service_id]
        unlinked_index[salon_id].sort(key=lambda service: (service.title, service.pk))

    reviewed = []
    for source in snapshot:
        salon_id = source['salon_id']
        services = services_by_salon[salon_id]
        by_id = {service.pk: service for service in services}
        previous = saved[(salon_id, source['source_id'])] & by_id.keys()
        by_legacy_id = {service.pk for service in services
                        if service.yclients_service_id == source['source_id']}
        by_manifest = set().union(*(code_index[salon_id].get(code, set())
                                    for code in manifest[source['source_id']]))
        by_title = title_index[salon_id].get(normalize_title(source['title']), set())
        source_base = base_title(source['title'])
        by_base_title = base_index[salon_id].get(source_base, set()) if source_base else set()
        ai_code = ai_suggestions.get((source['source_id'], normalize_title(source['title'])))
        ai_ids = code_index[salon_id].get(ai_code, set()) if ai_code else set()
        if previous:
            suggested_ids, reason = previous, 'Сохранённое соответствие'
        elif by_manifest:
            suggested_ids, reason = by_manifest, 'Проверенный список соответствий'
        elif by_legacy_id:
            suggested_ids, reason = by_legacy_id, 'ID YCLIENTS'
        elif len(by_title) == 1:
            suggested_ids, reason = by_title, 'Точное название'
        elif len(by_base_title) == 1:
            suggested_ids, reason = by_base_title, 'Совпадение основного названия до |'
        else:
            suggested_ids, reason = set(), 'Требуется выбор'

        close_bases = get_close_matches(source_base, base_index[salon_id].keys(), n=8, cutoff=0.4)
        fuzzy_ids = set().union(*(base_index[salon_id][title] for title in close_bases))
        candidate_ids = suggested_ids | by_legacy_id | by_manifest | by_title | by_base_title | ai_ids | fuzzy_ids
        candidates = [service for service in services if service.pk in candidate_ids]
        candidates.sort(key=lambda service: (service.pk not in suggested_ids,
                                             service.pk not in ai_ids, service.title, service.pk))
        staff = []
        unresolved = False
        active_staff_count = 0
        for member in source['staff']:
            master = links[salon_id].get(member['id'])
            if master is None:
                state = 'Нет связи ID мастера с салоном в БД'
                unresolved = True
            elif master.is_system or master.is_booking_placeholder or not master.is_active:
                state = 'Технический или неактивный мастер — пропуск'
            else:
                state = 'Готово'
                active_staff_count += 1
            staff.append({**member, 'master': master, 'state': state})
        pending_assignments = sum(
            (salon_id, service_id, member['master'].pk) not in existing_assignments
            for service_id in suggested_ids for member in staff if member['state'] == 'Готово'
        )
        if not suggested_ids or unresolved or not active_staff_count:
            status = 'problem'
        elif previous and not pending_assignments:
            status = 'saved'
        else:
            status = 'ready'
        reviewed.append({
            **source, 'salon': salons.get(salon_id), 'candidates': candidates,
            'suggested_ids': suggested_ids, 'reason': reason,
            'staff_preview': staff, 'unresolved': unresolved,
            'active_staff_count': active_staff_count,
            'saved_ids': previous,
            'ai_ids': ai_ids,
            'status': status, 'pending_assignments': pending_assignments,
            'needs_assignment': bool(pending_assignments or
                                     (not suggested_ids and active_staff_count)),
            'unlinked_services': unlinked_index[salon_id],
        })
    return reviewed


@transaction.atomic
def apply_row(source, target_ids):
    """Add only reviewed mappings and missing assignments for one source row."""
    salon_id = source['salon_id']
    if not target_ids or len(target_ids) > 10:
        raise ValueError('Выберите от 1 до 10 услуг каталога.')
    targets = list(Service.objects.filter(
        pk__in=target_ids, is_active=True, category__is_active=True,
        price_code__isnull=False, salon_offers__salon_id=salon_id,
        salon_offers__is_active=True,
    ).exclude(price_code='').distinct())
    if len(targets) != len(target_ids):
        raise ValueError('Выбранная услуга не найдена в актуальном Excel-каталоге этого салона.')
    links = {yclients_id(link.yclients_staff_id): link.master
             for link in MasterSalon.objects.filter(salon_id=salon_id).select_related('master')
             if yclients_id(link.yclients_staff_id)}
    staff = []
    for member in source['staff']:
        master = links.get(member['id'])
        if master is None:
            raise ValueError(f'Сотрудник YCLIENTS #{member["id"]} не сопоставлен с мастером в БД.')
        if not master.is_system and not master.is_booking_placeholder and master.is_active:
            staff.append((master, member['duration_seconds']))
    if not staff:
        raise ValueError('У услуги нет действующих мастеров для сохранения.')

    created = 0
    linked_id = False
    for service in targets:
        for master, duration in staff:
            if ServiceStaffPrice.objects.filter(service=service, salon_id=salon_id, master=master).exists():
                continue
            assignment = ServiceStaffPrice(
                service=service, salon_id=salon_id, master=master,
                duration_seconds=duration if duration != service.duration_seconds else None,
            )
            try:
                assignment.full_clean()
            except ValidationError as exc:
                raise ValueError(f'Нельзя назначить «{service}» мастеру «{master}»: {exc}') from exc
            assignment.save()
            created += 1
        YClientsServiceMatch.objects.update_or_create(
            salon_id=salon_id, yclients_service_id=source['source_id'], service=service,
            defaults={'source_title': source['title']},
        )
    if len(targets) == 1:
        target = targets[0]
        if (not target.yclients_service_id and
                not Service.objects.filter(yclients_service_id=source['source_id']).exists()):
            target.yclients_service_id = source['source_id']
            target.save(update_fields=['yclients_service_id'])
            linked_id = True
    return created, linked_id
