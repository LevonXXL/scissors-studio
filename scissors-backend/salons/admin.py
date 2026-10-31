from django import forms
from django.contrib import admin
from django.db import transaction
from django.urls import reverse
from django.utils.html import format_html
from django_ckeditor_5.widgets import CKEditor5Widget

from pages.admin_links import RelatedPageFormMixin, root_page
from pages.models import Page

from .models import Salon, SalonPhoto


class SalonAdminForm(RelatedPageFormMixin, forms.ModelForm):
    class Meta:
        model = Salon
        fields = '__all__'
        widgets = {'description': CKEditor5Widget(config_name='default')}

    def page_parent(self, cleaned):
        return root_page('salons')

    def clean(self):
        cleaned = super().clean()
        page = cleaned.get('page')
        slug = cleaned.get('slug')
        if page and page.pk != self.instance.page_id and page.parent_id != root_page('salons').pk:
            self.add_error('page', 'Выберите страницу внутри раздела «Салоны».')
        if page and slug and Page.objects.filter(url_path=f'salons/{slug}').exclude(pk=page.pk).exists():
            self.add_error('slug', 'Адрес страницы салона уже занят.')
        return cleaned


class SalonPhotoInline(admin.TabularInline):
    model = SalonPhoto
    extra = 0
    fields = ('image', 'position')


@admin.register(Salon)
class SalonAdmin(admin.ModelAdmin):
    form = SalonAdminForm
    autocomplete_fields = ('page',)
    list_display = ('name', 'address', 'phone', 'working_hours', 'is_active', 'position', 'last_synced_at')
    list_editable = ('position', 'is_active')
    search_fields = ('name', 'address')
    readonly_fields = ('last_synced_at', 'page_edit_link')
    inlines = (SalonPhotoInline,)
    fieldsets = (
        (None, {'fields': ('name', 'address', 'phone', 'working_hours', 'description', 'logo', 'is_active', 'position')}),
        ('Страница салона', {'fields': ('slug', 'page', 'page_edit_link')}),
        ('Координаты для Яндекс.Карт', {
            'fields': ('latitude', 'longitude'),
            'description': (
                'Кликните правой кнопкой по нужной точке на yandex.ru/maps '
                'и выберите «Что здесь» — координаты появятся внизу карты. '
                'Заполняются автоматически при синхронизации с YCLIENTS.'
            ),
        }),
        ('Интеграция с YCLIENTS', {'fields': ('yclients_company_id', 'yclients_booking_url', 'last_synced_at')}),
        ('Интеграция с REWIO', {'fields': ('yandex_maps_url', 'twogis_url', 'zoon_url', 'rewio_object_id')}),
    )

    @admin.display(description='Редактировать страницу')
    def page_edit_link(self, obj):
        if not obj or not obj.page_id:
            return 'Страница не привязана'
        url = reverse('admin:pages_page_change', args=(obj.page_id,))
        return format_html('<a href="{}">Редактировать «{}»</a>', url, obj.page.title)

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.page_id:
            page = obj.page
            parent = root_page('salons')
            if page.parent_id != parent.pk or page.url != obj.slug:
                page.parent = parent
                page.url = obj.slug
                page.save(update_fields=['parent', 'url'])
