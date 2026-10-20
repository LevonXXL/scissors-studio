from django.contrib import admin

from .models import Salon, SalonPhoto


class SalonPhotoInline(admin.TabularInline):
    model = SalonPhoto
    extra = 0
    fields = ('image', 'position')


@admin.register(Salon)
class SalonAdmin(admin.ModelAdmin):
    list_display = ('name', 'address', 'phone', 'working_hours', 'is_active', 'position', 'last_synced_at')
    list_editable = ('position', 'is_active')
    search_fields = ('name', 'address')
    readonly_fields = ('last_synced_at',)
    inlines = (SalonPhotoInline,)
    fieldsets = (
        (None, {'fields': ('name', 'slug', 'address', 'phone', 'working_hours', 'description', 'logo', 'is_active', 'position')}),
        ('Координаты для Яндекс.Карт', {
            'fields': ('latitude', 'longitude'),
            'description': (
                'Кликните правой кнопкой по нужной точке на yandex.ru/maps '
                'и выберите «Что здесь» — координаты появятся внизу карты. '
                'Заполняются автоматически при синхронизации с YCLIENTS.'
            ),
        }),
        ('Интеграция с YCLIENTS', {'fields': ('yclients_company_id', 'last_synced_at')}),
        ('Интеграция с REWIO', {'fields': ('yandex_maps_url', 'twogis_url', 'zoon_url', 'rewio_object_id')}),
    )
