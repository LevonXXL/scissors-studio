from django.contrib import admin

from .models import Service, ServiceCategory, ServiceStaffPrice


class ServiceStaffPriceInline(admin.TabularInline):
    model = ServiceStaffPrice
    extra = 0
    autocomplete_fields = ('master',)


@admin.register(ServiceCategory)
class ServiceCategoryAdmin(admin.ModelAdmin):
    list_display = ('title', 'salon', 'weight', 'is_chain', 'is_active', 'last_synced_at')
    list_filter = ('salon', 'is_chain', 'is_active')
    search_fields = ('title',)
    readonly_fields = ('yclients_category_id', 'last_synced_at')


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'price_min', 'price_max', 'duration_display', 'is_active', 'last_synced_at')
    list_filter = ('category__salon', 'category', 'is_active')
    search_fields = ('title',)
    readonly_fields = ('yclients_service_id', 'last_synced_at')
    inlines = (ServiceStaffPriceInline,)
