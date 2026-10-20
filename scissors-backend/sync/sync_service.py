"""
Логика синхронизации: YCLIENTS JSON -> наши модели.

Важное разделение полей на каждой модели:
- "синхронизируемые" — перезаписываются при каждом прогоне (имя, телефон,
  адрес, фото и т.п. — то, что реально приходит из YCLIENTS);
- "управляемые вручную в админке" — синхронизация их не трогает, потому
  что в YCLIENTS этих данных просто нет. Пример: Master.status
  (самозанятый/ИП) и Master.category (Универсал/Стилист/Арт-директор) —
  это бизнес-классификация, специфичная для аудита соответствия модели
  независимых партнёров, YCLIENTS о ней ничего не знает. Синхронизация
  задаёт им разумные значения по умолчанию только при ПЕРВОМ создании
  мастера и больше не трогает эти поля.
"""

from __future__ import annotations

import logging
from collections import Counter

from django.utils import timezone

from masters.models import Master, MasterSalon
from salons.models import Salon, SalonPhoto
from services.models import Service, ServiceCategory, ServiceStaffPrice

from .client import YClientsDataClient
from .images import fetch_and_store_image
from .identifiers import staff_name as _staff_name, yclients_id as _yclients_id
from .master_dedup import UnsafeMasterMerge, reconcile_master_duplicate

logger = logging.getLogger(__name__)


def sync_salon(salon: Salon, client: YClientsDataClient) -> None:
    company = client.get_company(salon.yclients_company_id)

    salon.name = company.get('title') or salon.name
    salon.address = company.get('address') or salon.address
    salon.description = company.get('description') or salon.description
    salon.working_hours = company.get('schedule') or salon.working_hours
    salon.phone = (company.get('phones') or [company.get('phone', '')])[0] or salon.phone

    if company.get('coordinate_lat') and company.get('coordinate_lon'):
        salon.latitude = company['coordinate_lat']
        salon.longitude = company['coordinate_lon']

    logo_image = fetch_and_store_image(company.get('logo'), folder_name='salons/logo')
    if logo_image:
        salon.logo = logo_image

    salon.last_synced_at = timezone.now()
    salon.save()

    _sync_salon_photos(salon, company.get('photos') or [])


def _sync_salon_photos(salon: Salon, photo_paths: list[str]) -> None:
    """
    photos в ответе YCLIENTS — относительные пути (например
    "general/f/f8/f89a41657dc6bd4_....png"), fetch_and_store_image сам
    достраивает домен assets.yclients.com.

    Пересобираем список целиком при каждой синхронизации — просто и
    предсказуемо; если позже кто-то добавит фото вручную через админку
    отдельной записью SalonPhoto без source в YCLIENTS, эта функция их
    не тронет, так как работает только со своим набором позиций 0..N-1.
    """
    existing = list(salon.photos.order_by('position'))

    for i, path in enumerate(photo_paths):
        image = fetch_and_store_image(path, folder_name='salons/photos')
        if not image:
            continue
        if i < len(existing):
            existing[i].image = image
            existing[i].save(update_fields=['image'])
        else:
            SalonPhoto.objects.create(salon=salon, image=image, position=i)

    # Лишние старые записи (если в YCLIENTS стало меньше фото) — удаляем.
    if len(existing) > len(photo_paths):
        for stale in existing[len(photo_paths):]:
            stale.delete()


def sync_staff(salon, client):
    staff_list = client.get_staff(salon.yclients_company_id)
    result = {}  # {relationship_id: Master} — для сопоставления цен в sync_services
    name_counts = Counter(_staff_name(entry.get('name')) for entry in staff_list)

    for entry in staff_list:
        relationship_id = _yclients_id(entry.get('id'))
        if relationship_id is None:
            logger.warning('YCLIENTS вернул сотрудника без id связи с салоном %s — пропускаю.', salon.pk)
            continue
        user_id = _yclients_id(entry.get('user_id'))
        is_system = user_id is None

        # entry.id is the per-salon staff/link ID; entry.user_id is the
        # cross-salon person ID. Never substitute one for the other.
        link = MasterSalon.objects.select_related('master').filter(yclients_staff_id=relationship_id).first()
        if link and link.salon_id != salon.pk:
            logger.warning('YCLIENTS staff id %s уже привязан к другому салону — пропускаю.', relationship_id)
            continue

        by_user = Master.objects.filter(yclients_user_id=user_id).first() if user_id else None
        if link and by_user and link.master_id != by_user.pk:
            logger.warning('YCLIENTS staff id %s и user_id %s указывают на разных мастеров — пропускаю.', relationship_id, user_id)
            continue

        master = by_user or (link.master if link else None)
        if master is None:
            # Legacy records can have a known staff ID on Master but a blank
            # ID on the salon link. Only consider records linked to this salon.
            legacy = list(Master.objects.filter(
                master_salons__salon=salon, yclients_staff_id=relationship_id,
            ).distinct()[:2])
            if len(legacy) == 1:
                master = legacy[0]

        if master is None:
            # Last resort for old rows whose IDs are all blank or '-'. Names
            # are usable only when unique in both the API response and salon.
            name = _staff_name(entry.get('name'))
            if name:
                candidates = [
                    existing.master for existing in MasterSalon.objects.select_related('master').filter(salon=salon)
                    if _yclients_id(existing.yclients_staff_id) is None
                    and _staff_name(existing.master.name) == name
                    and existing.master.is_system == is_system
                    and _yclients_id(existing.master.yclients_user_id) in {None, user_id}
                    and _yclients_id(existing.master.yclients_staff_id) in {None, relationship_id}
                ]
                if name_counts[name] == 1 and len(candidates) == 1:
                    master = candidates[0]
                elif candidates:
                    logger.warning(
                        'Неоднозначная привязка существующего мастера к YCLIENTS staff id %s в салоне %s; '
                        'старые записи не изменены.', relationship_id, salon.pk,
                    )

        if master is not None and (
            master.is_system != is_system
            or _yclients_id(master.yclients_user_id) not in {None, user_id}
        ):
            logger.warning('YCLIENTS IDs для мастера %s противоречат существующей записи — пропускаю.', master.pk)
            continue

        if master is None:
            master = Master(
                is_system=is_system,
                name=entry.get('name', ''),
                status=Master.STATUS_SELF_EMPLOYED,
                category=Master.CATEGORY_UNIVERSAL,
            )

        if user_id:
            master.yclients_user_id = user_id
        elif _yclients_id(master.yclients_user_id) is None:
            master.yclients_user_id = None
        master.yclients_staff_id = relationship_id  # только справочное последнее значение
        master.name = entry.get('name') or master.name
        master.specialization = entry.get('specialization') or master.specialization
        master.is_active = not (entry.get('fired') or entry.get('hidden'))
        master.last_synced_at = timezone.now()
        master.save()
        MasterSalon.objects.update_or_create(
            master=master,
            salon=salon,
            defaults={'yclients_staff_id': relationship_id},
        )

        # Prefer an exact legacy staff ID. If both old IDs are blank, require
        # a unique name in this salon. The merge helper checks related data.
        if user_id:
            known_staff_ids = {
                _yclients_id(staff_id)
                for staff_id in MasterSalon.objects.filter(master=master).values_list('yclients_staff_id', flat=True)
            }
            candidates = [
                old_link.master.pk
                for old_link in MasterSalon.objects.select_related('master').filter(salon=salon).exclude(master=master)
                if _yclients_id(old_link.yclients_staff_id) is None
                and _yclients_id(old_link.master.yclients_user_id) is None
                and old_link.master.is_system == master.is_system
                and (
                    _yclients_id(old_link.master.yclients_staff_id) in known_staff_ids - {None}
                    or (
                        _yclients_id(old_link.master.yclients_staff_id) is None
                        and name_counts[_staff_name(master.name)] == 1
                        and _staff_name(old_link.master.name) == _staff_name(master.name)
                    )
                )
            ]
            if len(candidates) == 1:
                try:
                    reconcile_master_duplicate(master.pk, candidates[0], apply=True)
                except UnsafeMasterMerge as exc:
                    logger.warning(
                        'Дубль мастера %s в салоне %s не объединён: %s', candidates[0], salon.pk, exc,
                    )
                else:
                    logger.info('Дубль мастера %s объединён с %s в салоне %s.', candidates[0], master.pk, salon.pk)
            elif len(candidates) > 1:
                logger.warning(
                    'Неоднозначные дубли мастера %s в салоне %s: записи %s; пропускаю объединение.',
                    master.pk, salon.pk, ', '.join(str(pk) for pk in sorted(candidates)),
                )

        result[relationship_id] = master

    return result

def sync_categories(salon: Salon, client: YClientsDataClient) -> dict[str, ServiceCategory]:
    categories = client.get_service_categories(salon.yclients_company_id)
    result = {}

    for entry in categories:
        yclients_id = str(entry['id'])
        category, _ = ServiceCategory.objects.update_or_create(
            salon=salon,
            yclients_category_id=yclients_id,
            defaults={
                'title': entry.get('title', ''),
                'weight': entry.get('weight', 0),
                'is_chain': bool(entry.get('is_chain')),
                'last_synced_at': timezone.now(),
            },
        )
        result[yclients_id] = category

    return result


def sync_services(
    salon: Salon,
    client: YClientsDataClient,
    categories_by_yid: dict[str, ServiceCategory],
    masters_by_yid: dict[str, Master],
) -> None:
    services = client.get_services(salon.yclients_company_id)

    for entry in services:
        category = categories_by_yid.get(str(entry.get('category_id')))
        if category is None:
            logger.warning(
                'Услуга "%s" (id=%s) ссылается на неизвестную категорию %s — пропускаю.',
                entry.get('title'), entry.get('id'), entry.get('category_id'),
            )
            continue

        image = None
        image_group = entry.get('image_group') or {}
        images = image_group.get('images') or {}
        if images:
            # Предпочитаем версию "basic", если она есть, иначе — любую первую.
            variant = images.get('basic') or next(iter(images.values()))
            image_url = variant.get('path') or variant.get('relative_path')
            image = fetch_and_store_image(image_url, folder_name='services/photos')

        service, _ = Service.objects.update_or_create(
            yclients_service_id=str(entry['id']),
            defaults={
                'category': category,
                'title': entry.get('title', ''),
                'description': entry.get('comment', ''),
                'price_min': entry.get('price_min') or 0,
                'price_max': entry.get('price_max') or 0,
                'duration_seconds': entry.get('duration'),
                'is_active': bool(entry.get('active')),
                'weight': entry.get('weight', 0),
                'last_synced_at': timezone.now(),
                **({'image': image} if image else {}),
            },
        )

        _sync_service_staff_prices(service, entry.get('staff') or [], masters_by_yid)


def _sync_service_staff_prices(service: Service, staff_entries: list[dict], masters_by_yid: dict[str, Master]) -> None:
    for staff_entry in staff_entries:
        master = masters_by_yid.get(str(staff_entry.get('id')))
        if master is None:
            continue  # мастер скрыт/не синхронизирован — пропускаем переопределение

        price_range = staff_entry.get('price') or {}
        price_min = price_range.get('min') if isinstance(price_range, dict) else None
        price_max = price_range.get('max') if isinstance(price_range, dict) else None
        duration = staff_entry.get('seance_length')

        if price_min is None and price_max is None and duration is None:
            continue  # нет переопределения — используется базовая цена услуги

        ServiceStaffPrice.objects.update_or_create(
            service=service,
            master=master,
            defaults={'price_min': price_min, 'price_max': price_max, 'duration_seconds': duration},
        )


def sync_salon_full(salon: Salon) -> None:
    """Полная синхронизация одного салона: сам салон, сотрудники, категории, услуги.
    Порядок важен — услугам и ценам нужны уже засинхронленные категории и мастера."""
    if not salon.yclients_company_id:
        logger.warning('У салона "%s" не задан yclients_company_id — пропускаю.', salon)
        return

    client = YClientsDataClient()

    sync_salon(salon, client)
    masters_by_yid = sync_staff(salon, client)
    categories_by_yid = sync_categories(salon, client)
    sync_services(salon, client, categories_by_yid, masters_by_yid)
