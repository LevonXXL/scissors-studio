from django.urls import path

from .views import beacon

urlpatterns = [path('beacon/', beacon, name='analytics-beacon')]
