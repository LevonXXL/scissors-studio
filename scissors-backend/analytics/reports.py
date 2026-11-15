from collections import Counter
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from dateutil.relativedelta import relativedelta
from django.utils import timezone

from .models import DailyVisitorMetrics, TrafficAggregate


MOSCOW = ZoneInfo('Europe/Moscow')


def report_data(start_day, end_day, hourly=False):
    """Fill missing traffic buckets with zero; missing visitor days stay unknown."""
    start = datetime.combine(start_day, datetime.min.time(), tzinfo=MOSCOW)
    end = datetime.combine(end_day + timedelta(days=1), datetime.min.time(), tzinfo=MOSCOW)
    rows = TrafficAggregate.objects.filter(period_start__gte=start, period_start__lt=end)
    counts = Counter()
    page_paths = Counter()
    api_paths = Counter()
    for row in rows.iterator():
        local = row.period_start.astimezone(MOSCOW)
        bucket = local.strftime('%Y-%m-%d %H:00') if hourly else local.date().isoformat()
        if row.event_type == TrafficAggregate.PAGE_VIEW:
            counts[(bucket, 'page_views')] += row.count
            page_paths[row.path] += row.count
        else:
            counts[(bucket, 'api_calls')] += row.count
            counts[(bucket, 'errors_4xx')] += row.errors_4xx
            counts[(bucket, 'errors_5xx')] += row.errors_5xx
            api_paths[row.path] += row.count
    labels = []
    cursor = start
    step = timedelta(hours=1) if hourly else timedelta(days=1)
    while cursor < end:
        labels.append(cursor.strftime('%Y-%m-%d %H:00') if hourly else cursor.date().isoformat())
        cursor += step
    metrics = ('page_views', 'api_calls', 'errors_4xx', 'errors_5xx')
    traffic = {metric: [counts[(label, metric)] for label in labels] for metric in metrics}
    visitor_rows = {row.day: row for row in DailyVisitorMetrics.objects.filter(
        day__gte=start_day, day__lte=end_day,
    )}
    day_labels = []
    visitors = {'visitors': [], 'sessions': [], 'pages_per_session': [], 'duration_seconds': []}
    day = start_day
    while day <= end_day:
        day_labels.append(day.isoformat())
        row = visitor_rows.get(day)
        visitors['visitors'].append(row.visitors if row else None)
        visitors['sessions'].append(row.sessions if row else None)
        visitors['pages_per_session'].append(round(row.pages_sum / row.sessions, 2) if row and row.sessions else None)
        visitors['duration_seconds'].append(round(row.duration_sum / row.sessions, 1) if row and row.sessions else None)
        day += timedelta(days=1)
    return {
        'labels': labels, 'traffic': traffic,
        'day_labels': day_labels, 'visitors': visitors,
        'top_pages': page_paths.most_common(10),
        'top_api': api_paths.most_common(10),
    }


def selected_range(params):
    today = timezone.now().astimezone(MOSCOW).date()
    period = params.get('period', '7d')
    if period == '30d':
        return today - timedelta(days=29), today, False, period
    if period == '6m':
        return today - relativedelta(months=6) + timedelta(days=1), today, False, period
    if period == 'custom':
        try:
            start = date.fromisoformat(params['from'])
            end = date.fromisoformat(params['to'])
            if start <= end and end <= today and end - start <= timedelta(days=730):
                return start, end, False, period
        except (KeyError, ValueError):
            pass
    return today - timedelta(days=6), today, True, '7d'
