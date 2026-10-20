from django.contrib import admin

from .models import SyncedImage


@admin.register(SyncedImage)
class SyncedImageAdmin(admin.ModelAdmin):
    list_display = ('source_url', 'image', 'downloaded_at')
    search_fields = ('source_url',)
    readonly_fields = ('source_url', 'image', 'downloaded_at')
