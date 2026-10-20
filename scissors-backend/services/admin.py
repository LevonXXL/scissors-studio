from django.contrib import admin
from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction

from pages.admin_links import RelatedPageFormMixin, align_page, root_page

from .models import Service, ServiceCategory, ServiceStaffPrice


class ServiceCategoryAdminForm(RelatedPageFormMixin, forms.ModelForm):
    class Meta:
        model = ServiceCategory
        fields = '__all__'

    def page_parent(self, cleaned):
        return root_page('services')


class ServiceAdminForm(RelatedPageFormMixin, forms.ModelForm):
    class Meta:
        model = Service
        fields = '__all__'

    def page_parent(self, cleaned):
        category = cleaned.get('category')
        if category is None:
            return None
        if not category.page_id:
            raise ValidationError('Сначала привяжите страницу к категории услуг.')
        return category.page


class ServiceStaffPriceInline(admin.TabularInline):
    model = ServiceStaffPrice
    extra = 0
    autocomplete_fields = ('master',)


@admin.register(ServiceCategory)
class ServiceCategoryAdmin(admin.ModelAdmin):
    form = ServiceCategoryAdminForm
    autocomplete_fields = ('page',)
    list_display = ('title', 'salon', 'weight', 'is_chain', 'is_active', 'last_synced_at')
    list_filter = ('salon', 'is_chain', 'is_active')
    search_fields = ('title',)
    readonly_fields = ('yclients_category_id', 'last_synced_at')

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.page_id:
            align_page(obj.page, root_page('services'))


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    form = ServiceAdminForm
    autocomplete_fields = ('page',)
    list_display = ('title', 'category', 'price_min', 'price_max', 'duration_display', 'is_active', 'last_synced_at')
    list_filter = ('category__salon', 'category', 'is_active')
    search_fields = ('title',)
    readonly_fields = ('yclients_service_id', 'last_synced_at')
    inlines = (ServiceStaffPriceInline,)

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.page_id:
            align_page(obj.page, obj.category.page)
