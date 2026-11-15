"""Only aggregate numbers leave this module; visitor keys live in process memory."""

import hashlib
import hmac
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F
from django.urls import Resolver404, resolve

from .models import TrafficAggregate


MOSCOW = ZoneInfo('Europe/Moscow')
LOG_RE = re.compile(
    r'^(?P<ip>\S+) \S+ \S+ \[(?P<when>[^]]+)\] '
    r'"(?P<method>\S+) (?P<uri>\S+) [^"]+" '
    r'(?P<status>\d{3}) \S+ "[^"]*" "(?P<ua>[^"]*)"'
)


def parse_angie_line(line):
    match = LOG_RE.match(line)
    if not match:
        return None
    try:
        values = match.groupdict()
        values['at'] = datetime.strptime(values['when'], '%d/%b/%Y:%H:%M:%S %z')
        values['status'] = int(values['status'])
        return values
    except ValueError:
        return None


def moscow_day_start(day):
    return datetime.combine(day, datetime.min.time(), tzinfo=MOSCOW).astimezone(dt_timezone.utc)


def hour_start(at):
    return at.astimezone(MOSCOW).replace(minute=0, second=0, microsecond=0).astimezone(dt_timezone.utc)


def endpoint_name(uri):
    path = uri.split('?', 1)[0]
    if not path.startswith('/api/') or len(path) > 1024:
        return None
    try:
        route = resolve(path).route
    except Resolver404:
        return '/api/(unmatched)'
    # Django's route template contains no values supplied by the caller.
    route = '/' + route.lstrip('/')
    return route[:255]


def increment(granularity, period_start, event_type, path, count=1, errors_4xx=0, errors_5xx=0):
    lookup = dict(granularity=granularity, period_start=period_start, event_type=event_type, path=path)
    with transaction.atomic():
        try:
            obj, _ = TrafficAggregate.objects.get_or_create(**lookup)
        except IntegrityError:
            obj = TrafficAggregate.objects.get(**lookup)
        TrafficAggregate.objects.filter(pk=obj.pk).update(
            count=F('count') + count,
            errors_4xx=F('errors_4xx') + errors_4xx,
            errors_5xx=F('errors_5xx') + errors_5xx,
        )


def visitor_totals(events, day):
    """Return daily totals without returning or persisting a visitor key."""
    daily_salt = hmac.digest(settings.SECRET_KEY.encode(), day.isoformat().encode(), hashlib.sha256)
    grouped = defaultdict(list)
    for event in events:
        if event['status'] != 204 or event['method'] != 'POST':
            continue
        if event['at'].astimezone(MOSCOW).date() != day:
            continue
        key = hmac.digest(daily_salt, (event['ip'] + '\0' + event['ua']).encode(), hashlib.sha256)
        grouped[key].append(event['at'])
    sessions = pages_sum = duration_sum = 0
    for times in grouped.values():
        times.sort()
        start = last = times[0]
        pages = 1
        for at in times[1:]:
            if at - last > timedelta(minutes=30):
                sessions += 1
                pages_sum += pages
                duration_sum += int((last - start).total_seconds())
                start = at
                pages = 0
            pages += 1
            last = at
        sessions += 1
        pages_sum += pages
        duration_sum += int((last - start).total_seconds())
    return len(grouped), sessions, pages_sum, duration_sum
