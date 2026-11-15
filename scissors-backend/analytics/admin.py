from django.contrib import admin
from django.shortcuts import render

from .reports import report_data, selected_range


def analytics_report(request):
    start, end, hourly, period = selected_range(request.GET)
    return render(request, 'analytics/report.html', {
        **admin.site.each_context(request),
        'title': 'Внутренняя статистика',
        'report': report_data(start, end, hourly),
        'start': start.isoformat(), 'end': end.isoformat(), 'period': period,
    })
