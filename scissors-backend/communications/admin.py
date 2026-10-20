from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import FeedbackRequest


@admin.register(FeedbackRequest)
class FeedbackRequestAdmin(ModelAdmin):
    list_display = ('created_at', 'name', 'phone', 'user')
    search_fields = ('name', 'phone', 'message')
    list_filter = ('created_at',)
    readonly_fields = ('name', 'phone', 'message', 'created_at', 'user')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_staff

    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_staff
