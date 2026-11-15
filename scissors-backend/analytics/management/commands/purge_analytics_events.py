from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from analytics.aggregation import MOSCOW
from analytics.models import BeaconEvent, DailyVisitorMetrics


class Command(BaseCommand):
    help = 'Delete raw beacons and visitor summaries after 90 days.'

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=90)
        events, _ = BeaconEvent.objects.filter(received_at__lt=cutoff).delete()
        visitors, _ = DailyVisitorMetrics.objects.filter(
            day__lt=cutoff.astimezone(MOSCOW).date(),
        ).delete()
        self.stdout.write(f'Deleted {events} raw events and {visitors} visitor summaries')
