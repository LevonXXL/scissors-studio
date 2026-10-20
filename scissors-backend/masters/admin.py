from django.contrib import admin
from django import forms
from django.db import transaction
from django_ckeditor_5.widgets import CKEditor5Widget

from pages.admin_links import RelatedPageFormMixin, align_page, root_page

from .models import Master, MasterSalon


class MasterAdminForm(RelatedPageFormMixin, forms.ModelForm):
    class Meta:
        model = Master
        fields = '__all__'
        widgets = {'bio': CKEditor5Widget(config_name='default')}

    def page_parent(self, cleaned):
        return root_page('team')


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
    form = MasterAdminForm
    autocomplete_fields = ('page',)
    list_display = (
        'name', 'yclients_user_id', 'salon_staff_ids', 'salons_display',
        'category', 'status', 'is_active', 'position', 'last_synced_at',
    )
    list_editable = ('position', 'is_active')
    list_filter = ('salons', 'category', 'status', 'is_active')
    search_fields = ('name', 'specialization')
    prepopulated_fields = {}
    inlines = (MasterSalonInline,)
    fieldsets = (
        (None, {'fields': ('name', 'specialization', 'category', 'photo', 'bio')}),
        ('Статус мастера', {'fields': ('status', 'inn')}),
        ('Отображение', {'fields': ('slug', 'page', 'is_active', 'position')}),
        ('Интеграция с YCLIENTS', {
            'fields': ('yclients_user_id', 'last_synced_at'),
            'description': (
                'yclients_user_id — кросс-салонный ID (одинаковый во всех филиалах). '
                # 'yclients_staff_id — legacy, per-salon ID теперь в таблице «Салоны» ниже.'
            ),
        }),
    )
    readonly_fields = ('slug', 'yclients_user_id', 'last_synced_at')

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('master_salons__salon')

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.page_id:
            align_page(obj.page, root_page('team'))

    @admin.display(description='Салоны')
    def salons_display(self, obj):
        return ', '.join(link.salon.name for link in obj.master_salons.all())

    @admin.display(description='YCLIENTS staff ID по салонам')
    def salon_staff_ids(self, obj):
        return ', '.join(
            f'{link.salon.name}: {link.yclients_staff_id or "—"}'
            for link in obj.master_salons.all()
        ) or '—'
