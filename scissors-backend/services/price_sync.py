"""Keep one stored price per numerically priced level in a salon offer."""

from decimal import Decimal

from .models import ServicePrice


def sync_offer_prices(offer, source_prices):
    amounts = {
        source['level']: Decimal(source['amount'])
        for source in source_prices if source['status'] == 'amount'
    }
    changed = 0
    for level, amount in amounts.items():
        price, created = ServicePrice.objects.get_or_create(
            salon_service=offer, level=level, defaults={'amount': amount},
        )
        if created:
            changed += 1
        elif price.amount != amount:
            price.amount = amount
            price.save(update_fields=['amount'])
            changed += 1
    removed, _ = offer.prices.exclude(level__in=amounts).delete()
    return changed + removed
