"""Conservative merge of a legacy, unidentified Master into its identified row."""

from django.db import transaction

from booking.models import Booking
from masters.models import Master, MasterSalon
from pages.models import Page
from salons.models import Salon
from services.models import Service, ServiceCategory
from services.models import ServiceStaffPrice

from .identifiers import staff_name, yclients_id


MASTER_FIELDS = (
    'name', 'price_level', 'status', 'inn', 'is_system',
    'is_booking_placeholder', 'position',
)
PRICE_FIELDS = ('price_min', 'price_max', 'duration_seconds')


class UnsafeMasterMerge(ValueError):
    """The records cannot be proven to represent the same person safely."""


def reconcile_master_duplicate(canonical_id: int, duplicate_id: int, *, apply: bool = False) -> dict:
    if canonical_id == duplicate_id:
        raise UnsafeMasterMerge('Укажите две разные записи мастера.')

    with transaction.atomic():
        masters = {
            master.pk: master
            for master in Master.objects.select_for_update().filter(pk__in=[canonical_id, duplicate_id])
        }
        if len(masters) != 2:
            raise UnsafeMasterMerge('Одна из записей мастера не найдена.')
        canonical, duplicate = masters[canonical_id], masters[duplicate_id]

        if not yclients_id(canonical.yclients_user_id):
            raise UnsafeMasterMerge('У основной записи нет YCLIENTS user_id.')
        if yclients_id(duplicate.yclients_user_id):
            raise UnsafeMasterMerge('У дубля есть другой YCLIENTS user_id.')

        canonical_links = {link.salon_id: link for link in MasterSalon.objects.filter(master=canonical)}
        duplicate_links = list(MasterSalon.objects.filter(master=duplicate))
        if not duplicate_links:
            raise UnsafeMasterMerge('У дубля нет привязки к салону.')
        for link in duplicate_links:
            counterpart = canonical_links.get(link.salon_id)
            if not counterpart or not yclients_id(counterpart.yclients_staff_id):
                raise UnsafeMasterMerge(f'У основной записи нет подтверждённой привязки к салону {link.salon_id}.')
            if yclients_id(link.yclients_staff_id):
                raise UnsafeMasterMerge(f'У дубля есть собственный YCLIENTS staff ID в салоне {link.salon_id}.')

        legacy_staff_id = yclients_id(duplicate.yclients_staff_id)
        known_staff_ids = {yclients_id(link.yclients_staff_id) for link in canonical_links.values()}
        matching_staff_id = bool(legacy_staff_id and legacy_staff_id in known_staff_ids)
        if legacy_staff_id and not matching_staff_id:
            raise UnsafeMasterMerge('Старый YCLIENTS staff ID дубля не совпадает с привязками основной записи.')
        if not matching_staff_id and (
            not staff_name(canonical.name) or staff_name(canonical.name) != staff_name(duplicate.name)
        ):
            raise UnsafeMasterMerge('Имена мастеров не совпадают.')
        differing_fields = [
            field for field in MASTER_FIELDS
            if getattr(canonical, field) != getattr(duplicate, field)
            and not (field == 'name' and matching_staff_id)
            and not (field == 'price_level' and not duplicate.price_level)
        ]
        if differing_fields:
            raise UnsafeMasterMerge(f'Поля мастеров различаются: {", ".join(differing_fields)}.')

        duplicate_page, canonical_page = duplicate.page, canonical.page
        transfer_page = bool(duplicate_page and not canonical_page)
        page_fields_to_recover = []
        if duplicate_page and canonical_page:
            if (
                duplicate_page.get_children().exists()
                or Salon.objects.filter(page_id=duplicate_page.pk).exists()
                or ServiceCategory.objects.filter(page_id=duplicate_page.pk).exists()
                or Service.objects.filter(page_id=duplicate_page.pk).exists()
            ):
                raise UnsafeMasterMerge('Страница дубля содержит дочерние страницы или связана с другой моделью.')
            # Keep the identified master's published page. Missing editorial
            # content can be recovered; the old page is retained unpublished.
            page_fields_to_recover = [
                field for field in ('title', 'content', 'meta_title', 'meta_description')
                if not getattr(canonical_page, field) and getattr(duplicate_page, field)
            ]
        elif transfer_page:
            if (
                not duplicate_page.parent_id
                or duplicate_page.parent.url_path != 'team'
                or Salon.objects.filter(page_id=duplicate_page.pk).exists()
                or ServiceCategory.objects.filter(page_id=duplicate_page.pk).exists()
                or Service.objects.filter(page_id=duplicate_page.pk).exists()
            ):
                raise UnsafeMasterMerge('Страница дубля не является отдельной страницей мастера.')
            target_path = f'team/{canonical.slug}'
            if Page.objects.filter(url_path=target_path).exclude(pk=duplicate_page.pk).exists():
                raise UnsafeMasterMerge('Адрес страницы основной записи уже занят.')

        canonical_prices = {price.service_id: price for price in ServiceStaffPrice.objects.filter(master=canonical)}
        overlapping, moving = [], []
        conflicting_prices = 0
        for price in ServiceStaffPrice.objects.filter(master=duplicate):
            existing = canonical_prices.get(price.service_id)
            if existing:
                if any(getattr(existing, field) != getattr(price, field) for field in PRICE_FIELDS):
                    conflicting_prices += 1
                overlapping.append(price)
            else:
                moving.append(price)

        bookings = Booking.objects.filter(master=duplicate)
        summary = {
            'canonical_id': canonical_id,
            'duplicate_id': duplicate_id,
            'links': len(duplicate_links),
            'overlapping_prices': len(overlapping),
            'conflicting_prices': conflicting_prices,
            'moving_prices': len(moving),
            'bookings': bookings.count(),
            'transferred_page': transfer_page,
            'recovered_page_fields': len(page_fields_to_recover),
        }
        if apply:
            # Keep the identified, recently synced record's content where it
            # exists; recover older content only when its field is empty.
            recovered_fields = []
            for field in ('bio', 'photo_id'):
                if not getattr(canonical, field) and getattr(duplicate, field):
                    setattr(canonical, field, getattr(duplicate, field))
                    recovered_fields.append(field)
            if recovered_fields:
                canonical.save(update_fields=recovered_fields)
            if page_fields_to_recover:
                for field in page_fields_to_recover:
                    setattr(canonical_page, field, getattr(duplicate_page, field))
                canonical_page.save(update_fields=page_fields_to_recover)
            bookings.update(master=canonical)
            for price in moving:
                price.master = canonical
                price.save(update_fields=['master'])
            ServiceStaffPrice.objects.filter(pk__in=[price.pk for price in overlapping]).delete()
            MasterSalon.objects.filter(pk__in=[link.pk for link in duplicate_links]).delete()
            if transfer_page:
                # The Page carries the editorial content and SEO; move its
                # OneToOne link before deleting the old Master.
                duplicate.page = None
                duplicate.save(update_fields=['page'])
                canonical.page = duplicate_page
                canonical.save(update_fields=['page'])
                if duplicate_page.url != canonical.slug:
                    duplicate_page.url = canonical.slug
                    duplicate_page.save(update_fields=['url'])
            elif duplicate_page and duplicate_page.is_published:
                duplicate_page.is_published = False
                duplicate_page.save(update_fields=['is_published'])
            duplicate.delete()
        return summary
