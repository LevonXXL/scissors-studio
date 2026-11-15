"""Catalogue offers that have an Excel price for a master's level."""

from django.db.models import Exists, OuterRef

from .models import ServicePrice, ServiceSalon


def priced_offers_for_master(master, salon_ids):
    levels = ('', master.price_level) if master.price_level else ('',)
    matching_price = ServicePrice.objects.filter(
        salon_service_id=OuterRef('pk'), level__in=levels,
    )
    offers = (ServiceSalon.objects.filter(
        salon_id__in=salon_ids, salon__is_active=True, is_active=True,
        service__is_active=True, service__category__is_active=True,
        service__price_code__isnull=False,
    ).exclude(service__price_code='').annotate(
        has_matching_price=Exists(matching_price),
    ).filter(has_matching_price=True))
    if master.name == 'Михаил Стець':
        offers = offers.filter(service__category__code__in=('hair', 'forman'))
    return offers
