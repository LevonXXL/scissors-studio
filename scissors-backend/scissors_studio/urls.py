from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from communications.views import admin_push_service_worker, admin_push_settings
from core_utils.thumbnails import thumbnail
from core_utils.ckeditor_upload import staff_image_upload
from masters.bot_views import max_webhook, telegram_webhook
from masters.telegram_admin import telegram_webhook_settings
from analytics.admin import analytics_report
from core_utils.health import health, ready

urlpatterns = [
    path('health/', health, name='health'),
    path('ready/', ready, name='ready'),
    path('analytics/', include('analytics.urls')),
    path('webhooks/staff/telegram/', telegram_webhook, name='staff-telegram-webhook'),
    path('webhooks/staff/max/', max_webhook, name='staff-max-webhook'),
    path('ckeditor5/image_upload/', staff_image_upload, name='ck_editor_5_upload_file'),
    path('ckeditor5/', include('django_ckeditor_5.urls')),
    path('api/v1/', include('pages.urls')),
    path('api/v1/', include('salons.urls')),
    path('api/v1/', include('masters.urls')),
    path('api/v1/', include('services.urls')),
    path('api/v1/', include('booking.urls')),
    path('api/v1/', include('reviews.urls')),
    path('api/v1/auth/', include('client_auth.urls')),
    path('api/v1/', include('communications.urls')),
    path('api/v1/', include('search.urls')),

    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    path('thumbnail/<int:width>/<path:source_path>', thumbnail, name='thumbnail'),
    path('push-settings/', admin.site.admin_view(admin_push_settings), name='admin-push-settings'),
    path('telegram-webhook/', admin.site.admin_view(telegram_webhook_settings),
         name='admin-telegram-webhook-settings'),
    path('analytics/report/', admin.site.admin_view(analytics_report), name='admin-analytics-report'),
    path('push-sw.js', admin_push_service_worker, name='admin-push-sw'),
]

if settings.DEBUG and settings.MEDIA_URL.startswith('/'):
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Django Admin has a catch-all route, so it must come after local media URLs.
urlpatterns += [path('', admin.site.urls)]
