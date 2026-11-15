import json
from datetime import timedelta
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from pages.models import Page

from .aggregation import MOSCOW, hour_start, visitor_totals
from .models import AngieLogCursor, BeaconEvent, DailyVisitorMetrics, TrafficAggregate
from .reports import report_data


def log_line(at, method, path, status, ip='192.0.2.1', ua='ExampleBrowser'):
    return (f'{ip} - - [{at.strftime("%d/%b/%Y:%H:%M:%S %z")}] '
            f'"{method} {path} HTTP/2.0" {status} 0 "-" "{ua}"\n')


class AnonymousAnalyticsTests(TestCase):
    def test_schemas_have_no_client_identifiers(self):
        for model in (TrafficAggregate, DailyVisitorMetrics, BeaconEvent, AngieLogCursor):
            fields = {field.name for field in model._meta.fields}
            self.assertFalse(fields & {'ip', 'user_agent', 'visitor_hash', 'session_hash', 'token', 'cookie'})
        self.assertEqual({field.name for field in DailyVisitorMetrics._meta.fields},
                         {'day', 'visitors', 'sessions', 'pages_sum', 'duration_sum'})

    def test_beacon_accepts_only_path_and_timestamp_and_deduplicates(self):
        Page.objects.create(title='Команда', url='team')
        payload = {'path': '/team', 'ts': int(timezone.now().timestamp() * 1000)}
        first = self.client.post('/analytics/beacon/', data=json.dumps(payload), content_type='text/plain')
        second = self.client.post('/analytics/beacon/', data=json.dumps(payload), content_type='text/plain')
        self.assertEqual((first.status_code, second.status_code), (204, 208))
        self.assertEqual(BeaconEvent.objects.count(), 1)
        self.assertEqual(TrafficAggregate.objects.get(event_type='page_view').count, 1)
        payload['visitor_id'] = 'forbidden'
        self.assertEqual(self.client.post('/analytics/beacon/', data=json.dumps(payload),
                                          content_type='text/plain').status_code, 400)

    def test_api_log_cursor_and_rollup_are_idempotent(self):
        now = timezone.now().replace(microsecond=0)
        with TemporaryDirectory() as directory:
            api = Path(directory) / 'api.log'
            beacon = Path(directory) / 'beacon.log'
            api.write_text(log_line(now, 'GET', '/api/v1/pages/by-path/team/', 200, ip='-', ua='-') +
                           log_line(now, 'GET', '/api/v1/pages/by-path/missing/', 404, ip='-', ua='-'))
            beacon.write_text(log_line(now, 'POST', '/analytics/beacon/', 204))
            for _ in range(2):
                call_command('aggregate_angie_logs', '--api-log', str(api),
                             '--beacon-log', str(beacon), stdout=StringIO())
            self.assertEqual(TrafficAggregate.objects.filter(event_type='api_call').aggregate(
                total=models_sum('count'))['total'], 2)
            self.assertEqual(TrafficAggregate.objects.filter(event_type='api_call').aggregate(
                total=models_sum('errors_4xx'))['total'], 1)
            self.assertEqual(DailyVisitorMetrics.objects.get().visitors, 1)
            self.assertEqual(DailyVisitorMetrics.objects.get().sessions, 1)
            self.assertEqual(AngieLogCursor.objects.get().offset, api.stat().st_size)

            old = now - timedelta(days=8)
            TrafficAggregate.objects.create(granularity='hour', period_start=hour_start(old),
                                            event_type='page_view', path='/team', count=3)
            for _ in range(2):
                call_command('rollup_analytics', '--beacon-log', str(beacon), stdout=StringIO())
            daily = TrafficAggregate.objects.get(granularity='day', event_type='page_view')
            self.assertEqual(daily.count, 3)

    def test_session_window_and_day_salt(self):
        at = timezone.now().astimezone(MOSCOW).replace(hour=11, minute=0, second=0, microsecond=0)
        day = at.date()
        events = [
            {'at': at, 'ip': '192.0.2.1', 'ua': 'A', 'status': 204, 'method': 'POST'},
            {'at': at + timedelta(minutes=20), 'ip': '192.0.2.1', 'ua': 'A', 'status': 204, 'method': 'POST'},
            {'at': at + timedelta(minutes=51), 'ip': '192.0.2.1', 'ua': 'A', 'status': 204, 'method': 'POST'},
        ]
        self.assertEqual(visitor_totals(events, day), (1, 2, 3, 1200))
        self.assertEqual(visitor_totals(events, day + timedelta(days=1)), (0, 0, 0, 0))

    def test_rotated_api_log_tail_is_read_once(self):
        now = timezone.now().replace(microsecond=0)
        with TemporaryDirectory() as directory:
            api = Path(directory) / 'api.log'
            beacon = Path(directory) / 'beacon.log'
            beacon.write_text('')
            api.write_text(log_line(now, 'GET', '/api/v1/pages/', 200, ip='-', ua='-'))
            call_command('aggregate_angie_logs', '--api-log', str(api),
                         '--beacon-log', str(beacon), stdout=StringIO())
            api.rename(Path(directory) / 'api.log.1')
            with (Path(directory) / 'api.log.1').open('a') as old:
                old.write(log_line(now, 'GET', '/api/v1/pages/', 503, ip='-', ua='-'))
            api.write_text(log_line(now, 'GET', '/api/v1/pages/', 200, ip='-', ua='-'))
            for _ in range(2):
                call_command('aggregate_angie_logs', '--api-log', str(api),
                             '--beacon-log', str(beacon), stdout=StringIO())
            aggregate = TrafficAggregate.objects.get(event_type='api_call')
            self.assertEqual((aggregate.count, aggregate.errors_5xx), (3, 1))

    def test_purge_keeps_long_lived_daily_counters(self):
        old = timezone.now() - timedelta(days=91)
        BeaconEvent.objects.create(path='/team', occurred_at=old, received_at=old)
        DailyVisitorMetrics.objects.create(day=old.astimezone(MOSCOW).date(), visitors=1)
        TrafficAggregate.objects.create(granularity='day', period_start=hour_start(old),
                                        event_type='page_view', path='/team', count=4)
        call_command('purge_analytics_events', stdout=StringIO())
        self.assertFalse(BeaconEvent.objects.exists())
        self.assertFalse(DailyVisitorMetrics.objects.exists())
        self.assertEqual(TrafficAggregate.objects.get().count, 4)

    def test_report_fills_traffic_gaps_and_is_staff_only(self):
        today = timezone.now().astimezone(MOSCOW).date()
        data = report_data(today - timedelta(days=1), today)
        self.assertEqual(data['traffic']['page_views'], [0, 0])
        self.assertEqual(data['visitors']['visitors'], [None, None])
        self.assertEqual(self.client.get('/analytics/report/').status_code, 302)
        user = get_user_model().objects.create_user(username='staff-analytics', password='password', is_staff=True)
        self.client.force_login(user)
        self.assertEqual(self.client.get('/analytics/report/').status_code, 200)


def models_sum(field):
    from django.db.models import Sum
    return Sum(field)
