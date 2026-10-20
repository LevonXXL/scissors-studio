from django.contrib import admin

from .models import Master, MasterSalon


class MasterSalonInline(admin.TabularInline):
    model = MasterSalon
    extra = 0
    readonly_fields = ('salon', 'yclients_staff_id')
    # salon выбирается автоматически при синхронизации,
    # ручное добавление через inline не нужно
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Master)
class MasterAdmin(admin.ModelAdmin):
    list_display = ('name', 'salons_display', 'category', 'status', 'is_active', 'position', 'last_synced_at')
    list_editable = ('position', 'is_active')
    list_filter = ('salons', 'category', 'status', 'is_active')
    search_fields = ('name', 'specialization')
    prepopulated_fields = {}
    inlines = (MasterSalonInline,)
    fieldsets = (
        (None, {'fields': ('name', 'specialization', 'category', 'photo', 'bio')}),
        ('Статус мастера', {'fields': ('status', 'inn')}),
        ('Отображение', {'fields': ('slug', 'is_active', 'position')}),
        ('Интеграция с YCLIENTS', {
            'fields': ('yclients_user_id', 'last_synced_at'),
            'description': (
                'yclients_user_id — кросс-салонный ID (одинаковый во всех филиалах). '
                # 'yclients_staff_id — legacy, per-salon ID теперь в таблице «Салоны» ниже.'
            ),
        }),
    )
    readonly_fields = ('slug', 'yclients_user_id', 'last_synced_at')

    @admin.display(description='Салоны')
    def salons_display(self, obj):
        return ', '.join(s.name for s in obj.salons.all())
