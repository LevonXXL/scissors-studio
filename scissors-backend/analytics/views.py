"""The beacon accepts only a public path and timestamp, never a browser ID."""

import json
from datetime import datetime, timedelta, timezone as dt_timezone

from django.db import IntegrityError, transaction
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from pages.models import Page

from .aggregation import hour_start, increment
from .models import BeaconEvent, TrafficAggregate


STATIC_PATHS = {'/', '/about', '/team', '/salons', '/privacy', '/vacancy'}


@csrf_exempt
@require_POST
def beacon(request):
    if len(request.body) > 1024:
        return JsonResponse({'detail': 'Invalid event'}, status=400)
    try:
        payload = json.loads(request.body)
        if set(payload) != {'path', 'ts'}:
            raise ValueError
        path = payload['path']
        if not isinstance(path, str) or not path.startswith('/') or len(path) > 255 or '?' in path or '#' in path:
            raise ValueError
        path = path.rstrip('/') or '/'
        at = datetime.fromtimestamp(payload['ts'] / 1000, tz=dt_timezone.utc)
        now = timezone.now()
        if abs(now - at) > timedelta(minutes=5):
            raise ValueError
        if path not in STATIC_PATHS and not Page.objects.filter(url_path=path.lstrip('/'), is_published=True).exists():
            raise ValueError
    except (ValueError, TypeError, OverflowError, UnicodeDecodeError):
        return JsonResponse({'detail': 'Invalid event'}, status=400)

    # Global cap supplements Angie rate limiting without any per-client state.
    period = hour_start(now)
    if TrafficAggregate.objects.filter(
        granularity='hour', period_start=period, event_type='page_view', path=path, count__gte=50000,
    ).exists():
        return HttpResponse(status=429)
    try:
        with transaction.atomic():
            BeaconEvent.objects.create(path=path, occurred_at=at, received_at=now)
            increment('hour', period, 'page_view', path)
    except IntegrityError:
        return HttpResponse(status=208)  # Excluded from visitor/session source log.
    return HttpResponse(status=204)
