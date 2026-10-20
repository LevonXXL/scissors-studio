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

from django.utils import timezone

from masters.models import Master, MasterSalon
from salons.models import Salon, SalonPhoto
from services.models import Service, ServiceCategory, ServiceStaffPrice

from .client import YClientsDataClient
from .images import fetch_and_store_image

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

    for entry in staff_list:
        relationship_id = str(entry['id'])
        user_id = str(entry['user_id']) if entry.get('user_id') else None
        is_system = user_id is None

        if is_system:
            # Нет стабильной "личности" для дедупликации между салонами —
            # ищем строго в рамках уже известной связи с этим салоном.
            master = Master.objects.filter(
                is_system=True, yclients_staff_id=relationship_id, salons=salon,
            ).first()
            created = master is None
            if created:
                master = Master.objects.create(
                    is_system=True,
                    yclients_staff_id=relationship_id,
                    name=entry.get('name', ''),
                    status=Master.STATUS_SELF_EMPLOYED,
                    category=Master.CATEGORY_UNIVERSAL,
                )
        else:
            master, created = Master.objects.get_or_create(
                yclients_user_id=user_id,
                defaults={
                    'name': entry.get('name', ''),
                    'status': Master.STATUS_SELF_EMPLOYED,
                    'category': Master.CATEGORY_UNIVERSAL,
                },
            )
            master.yclients_staff_id = relationship_id  # последнее увиденное значение

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
