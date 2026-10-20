import os

from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'scissors_studio.settings')

app = Celery('scissors_studio')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
