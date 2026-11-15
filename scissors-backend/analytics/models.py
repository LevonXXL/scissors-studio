from django.db import models


class TrafficAggregate(models.Model):
    HOUR = 'hour'
    DAY = 'day'
    PAGE_VIEW = 'page_view'
    API_CALL = 'api_call'

    granularity = models.CharField(max_length=4, choices=((HOUR, 'Час'), (DAY, 'День')))
    period_start = models.DateTimeField()
    event_type = models.CharField(max_length=9, choices=((PAGE_VIEW, 'Просмотр'), (API_CALL, 'API')))
    path = models.CharField(max_length=255)
    count = models.PositiveBigIntegerField(default=0)
    errors_4xx = models.PositiveBigIntegerField(default=0)
    errors_5xx = models.PositiveBigIntegerField(default=0)
    pk = models.CompositePrimaryKey('granularity', 'period_start', 'event_type', 'path')

    class Meta:
        indexes = [models.Index(fields=('granularity', 'period_start'))]


class DailyVisitorMetrics(models.Model):
    day = models.DateField(primary_key=True)
    visitors = models.PositiveBigIntegerField(default=0)
    sessions = models.PositiveBigIntegerField(default=0)
    pages_sum = models.PositiveBigIntegerField(default=0)
    duration_sum = models.PositiveBigIntegerField(default=0, help_text='Сумма длительностей сессий в секундах')


class BeaconEvent(models.Model):
    path = models.CharField(max_length=255)
    occurred_at = models.DateTimeField()
    received_at = models.DateTimeField(db_index=True)
    pk = models.CompositePrimaryKey('path', 'occurred_at')


class AngieLogCursor(models.Model):
    source = models.CharField(max_length=32, primary_key=True)
    inode = models.PositiveBigIntegerField(default=0)
    offset = models.PositiveBigIntegerField(default=0)
