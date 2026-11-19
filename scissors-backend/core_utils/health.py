from django.apps import apps
from django.http import HttpResponse


def health(_request):
    return _response(200, 'ok')


def ready(_request):
    if not apps.ready:
        return _response(503, 'not ready')
    return _response(200, 'ready')


def _response(status, body):
    response = HttpResponse(body, status=status, content_type='text/plain; charset=utf-8')
    response['Cache-Control'] = 'no-store'
    return response
