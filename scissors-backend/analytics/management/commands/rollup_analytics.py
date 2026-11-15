"""Move old hour counters into day counters, exactly once per hour row."""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from analytics.aggregation import MOSCOW, increment, moscow_day_start
from analytics.management.commands.aggregate_angie_logs import rebuild_visitor_day
from analytics.models import TrafficAggregate


class Command(BaseCommand):
    help = 'Roll up hourly counters older than seven days and finalize yesterday’s visitors.'

    def add_arguments(self, parser):
        parser.add_argument('--beacon-log', default='/var/log/angie/scissors-beacon.access')

    def handle(self, *args, **options):
        today = timezone.now().astimezone(MOSCOW).date()
        yesterday = today - timedelta(days=1)
        rebuild_visitor_day(options['beacon_log'], yesterday)
        # Keep exactly the seven Moscow calendar days shown by the hourly report.
        cutoff = moscow_day_start(today - timedelta(days=6))
        rolled = 0
        with transaction.atomic():
            rows = list(TrafficAggregate.objects.select_for_update().filter(
                granularity='hour', period_start__lt=cutoff,
            ))
            for row in rows:
                day = row.period_start.astimezone(MOSCOW).date()
                increment('day', moscow_day_start(day), row.event_type, row.path,
                          row.count, row.errors_4xx, row.errors_5xx)
                row.delete()
                rolled += 1
        self.stdout.write(f'Rolled up {rolled} hourly rows')
