"""Increment API counters from Angie and recompute today's anonymous visits."""

import gzip
from collections import Counter
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from analytics.aggregation import MOSCOW, endpoint_name, hour_start, increment, parse_angie_line, visitor_totals
from analytics.models import AngieLogCursor, DailyVisitorMetrics


def log_files(base):
    """The current and rotated files; historical visitor totals require raw logs."""
    path = Path(base)
    return sorted(path.parent.glob(path.name + '*'))


def accepted_beacons(base, day):
    events = []
    for path in log_files(base):
        if not path.is_file():
            continue
        opener = gzip.open if path.suffix == '.gz' else open
        with opener(path, 'rt', encoding='utf-8', errors='replace') as source:
            for line in source:
                if 'POST /analytics/beacon/' not in line:
                    continue
                event = parse_angie_line(line)
                if (event and event['status'] == 204 and event['method'] == 'POST' and
                        event['at'].astimezone(MOSCOW).date() == day):
                    events.append(event)
    return events


def rebuild_visitor_day(base, day):
    events = accepted_beacons(base, day)
    if not events:
        return False
    visitors, sessions, pages_sum, duration_sum = visitor_totals(events, day)
    DailyVisitorMetrics.objects.update_or_create(day=day, defaults={
        'visitors': visitors, 'sessions': sessions,
        'pages_sum': pages_sum, 'duration_sum': duration_sum,
    })
    return True


class Command(BaseCommand):
    help = 'Read fresh Angie API lines exactly once and rebuild today’s in-memory visitor totals.'

    def add_arguments(self, parser):
        parser.add_argument('--api-log', default='/var/log/angie/scissors-api-analytics.access')
        parser.add_argument('--beacon-log', default='/var/log/angie/scissors-beacon.access')

    def handle(self, *args, **options):
        api_log = Path(options['api_log'])
        if not api_log.exists():
            raise CommandError(f'API log not found: {api_log}')
        with transaction.atomic():
            cursor, _ = AngieLogCursor.objects.select_for_update().get_or_create(source='scissors-api')
            inode = api_log.stat().st_ino
            sources = []
            if cursor.inode and cursor.inode != inode:
                rotated = next((p for p in log_files(api_log) if p.stat().st_ino == cursor.inode), None)
                if rotated:
                    sources.append((rotated, cursor.offset))
                else:
                    self.stderr.write('Previous API log inode missing after rotation; check for a collection gap.')
            sources.append((api_log, cursor.offset if cursor.inode == inode else 0))
            totals = Counter()
            end_offset = 0
            for path, offset in sources:
                with path.open('rb') as source:
                    source.seek(min(offset, path.stat().st_size))
                    while True:
                        before = source.tell()
                        raw = source.readline()
                        if not raw:
                            break
                        if not raw.endswith(b'\n'):
                            source.seek(before)
                            break
                        event = parse_angie_line(raw.decode('utf-8', errors='replace'))
                        if event:
                            route = endpoint_name(event['uri'])
                            if route:
                                key = (hour_start(event['at']), route)
                                totals[(key, 'count')] += 1
                                if 400 <= event['status'] < 500:
                                    totals[(key, '4xx')] += 1
                                if event['status'] >= 500:
                                    totals[(key, '5xx')] += 1
                    if path == api_log:
                        end_offset = source.tell()
            for period, route in {key for key, metric in totals}:
                increment('hour', period, 'api_call', route,
                          totals[((period, route), 'count')],
                          totals[((period, route), '4xx')],
                          totals[((period, route), '5xx')])
            cursor.inode = inode
            cursor.offset = end_offset
            cursor.save(update_fields=('inode', 'offset'))
        day = timezone.now().astimezone(MOSCOW).date()
        if Path(options['beacon_log']).exists():
            rebuild_visitor_day(options['beacon_log'], day)
        self.stdout.write(f'Processed {sum(v for (key, metric), v in totals.items() if metric == "count")} API lines')
