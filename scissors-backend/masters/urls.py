from rest_framework.routers import DefaultRouter

from .views import MasterViewSet
from .mini_app import (TelegramMiniAppBio, TelegramMiniAppContent,
                       TelegramMiniAppPhoto, TelegramMiniAppProfile,
                       TelegramMiniAppServices)
from django.urls import path

router = DefaultRouter()
router.register('masters', MasterViewSet, basename='master')

urlpatterns = [
    path('staff/telegram/me/', TelegramMiniAppProfile.as_view(), name='telegram-mini-app-profile'),
    path('staff/telegram/bio/', TelegramMiniAppBio.as_view(), name='telegram-mini-app-bio'),
    path('staff/telegram/content/', TelegramMiniAppContent.as_view(), name='telegram-mini-app-content'),
    path('staff/telegram/services/', TelegramMiniAppServices.as_view(), name='telegram-mini-app-services'),
    path('staff/telegram/services/<int:assignment_id>/', TelegramMiniAppServices.as_view(),
         name='telegram-mini-app-service-detail'),
    path('staff/telegram/photo/', TelegramMiniAppPhoto.as_view(), name='telegram-mini-app-photo'),
    *router.urls,
]
