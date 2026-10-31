from django.contrib import admin
from django import forms
from django.db import transaction
from django.db.models import Max
from django_ckeditor_5.widgets import CKEditor5Widget
from django.urls import reverse
from django.utils.html import format_html, format_html_join
from filer.models import Image as FilerImage

from pages.admin_links import RelatedPageFormMixin, align_page, root_page
from pages.models import PagePicture

from .models import Master, MasterSalon


class MultipleImageInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
    def clean(self, data, initial=None):
        if not data:
            return []
        return [super(MultipleImageField, self).clean(upload, initial) for upload in data]


class MasterAdminForm(RelatedPageFormMixin, forms.ModelForm):
    page_title = forms.CharField(label='Заголовок страницы', max_length=255, required=False)
    page_content = forms.CharField(label='Содержание страницы', required=False,
                                   widget=CKEditor5Widget(config_name='default'))
    page_meta_title = forms.CharField(label='Заголовок для поиска', max_length=255, required=False)
    page_meta_description = forms.CharField(label='Описание для поиска', max_length=255,
                                            required=False)
    page_is_published = forms.BooleanField(label='Страница опубликована', required=False)
    work_photos = MultipleImageField(label='Добавить фотографии работ', required=False,
                                     widget=MultipleImageInput)

    class Meta:
        model = Master
        fields = '__all__'
        widgets = {'bio': CKEditor5Widget(config_name='default')}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.page_id:
            page = self.instance.page
            self.fields['page_title'].initial = page.title
            self.fields['page_content'].initial = page.content
            self.fields['page_meta_title'].initial = page.meta_title
            self.fields['page_meta_description'].initial = page.meta_description
            self.fields['page_is_published'].initial = page.is_published

    def page_parent(self, cleaned):
        return root_page('team')

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('work_photos') and not (cleaned.get('page') or self.instance.page_id):
            self.add_error('work_photos', 'Сначала создайте страницу мастера.')
        return cleaned


class MasterSalonInline(admin.TabularInline):
    model = MasterSalon
    extra = 0
    readonly_fields = ('salon', 'yclients_staff_id')
    fields = ('salon', 'yclients_staff_id', 'yclients_booking_url')
    # salon выбирается автоматически при синхронизации,
    # ручное добавление через inline не нужно
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Master)
class MasterAdmin(admin.ModelAdmin):
    form = MasterAdminForm
    autocomplete_fields = ('page', 'user')
    list_display = (
        'name', 'yclients_user_id', 'salon_staff_ids', 'salons_display',
        'price_level', 'is_booking_placeholder', 'status', 'is_active', 'position', 'last_synced_at',
    )
    list_filter = ('salons', 'price_level', 'is_booking_placeholder', 'status', 'is_active')
    search_fields = ('name',)
    prepopulated_fields = {}
    inlines = (MasterSalonInline,)
    fieldsets = (
        (None, {'fields': ('name', 'price_level', 'photo', 'bio')}),
        ('Статус мастера', {'fields': ('status', 'inn')}),
        ('Отображение', {'fields': ('slug', 'page', 'user', 'is_active', 'is_booking_placeholder', 'position')}),
        ('Интеграция с YCLIENTS', {
            'fields': ('yclients_user_id', 'last_synced_at'),
            'description': (
                'yclients_user_id — кросс-салонный ID (одинаковый во всех филиалах). '
                # 'yclients_staff_id — legacy, per-salon ID теперь в таблице «Салоны» ниже.'
            ),
        }),
        ('Примеры работ', {'fields': ('work_photo_gallery', 'work_photos')}),
    )
    readonly_fields = ('slug', 'yclients_user_id', 'last_synced_at')

    def is_own_profile(self, request):
        return (request.user.is_staff and
                Master.objects.filter(user_id=request.user.pk).exists())

    def has_module_permission(self, request):
        return self.is_own_profile(request) or super().has_module_permission(request)

    def has_view_permission(self, request, obj=None):
        if self.is_own_profile(request):
            return obj is None or obj.user_id == request.user.pk
        return super().has_view_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        if self.is_own_profile(request):
            return obj is None or obj.user_id == request.user.pk
        return super().has_change_permission(request, obj)

    def has_add_permission(self, request):
        if self.is_own_profile(request):
            return False
        return super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        if self.is_own_profile(request):
            return False
        return super().has_delete_permission(request, obj)

    def get_fieldsets(self, request, obj=None):
        if self.is_own_profile(request):
            return (
                (None, {'fields': ('name', 'price_level', 'photo', 'bio')}),
                ('Статус мастера', {'fields': ('status', 'inn')}),
                ('Страница мастера', {'fields': (
                    'page_title', 'page_content', 'page_meta_title',
                    'page_meta_description', 'page_is_published', 'master_page_link',
                )}),
                ('Примеры работ', {'fields': ('work_photo_gallery', 'work_photos')}),
            )
        return super().get_fieldsets(request, obj)

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        if self.is_own_profile(request):
            return (*fields, 'master_page_link', 'work_photo_gallery')
        return (*fields, 'work_photo_gallery')

    def get_inlines(self, request, obj=None):
        return [] if self.is_own_profile(request) else super().get_inlines(request, obj)

    @admin.display(description='Страница')
    def master_page_link(self, obj):
        if not obj or not obj.page_id:
            return 'Страница ещё не создана'
        return format_html('<a href="{}">Редактировать свою страницу</a>',
                           reverse('admin:pages_page_change', args=[obj.page_id]))

    @admin.display(description='Фотографии на странице')
    def work_photo_gallery(self, obj):
        if not obj or not obj.page_id:
            return 'Пока нет фотографий'
        pictures = [(picture.image_url, picture.alt or obj.name)
                    for picture in obj.page.pictures.select_related('image').all()
                    if picture.image_url]
        if not pictures:
            return 'Пока нет фотографий'
        return format_html('<div style="display:flex; flex-wrap:wrap; gap:12px">{}</div>',
                           format_html_join('', '<a href="{}" target="_blank" rel="noopener">'
                                            '<img src="{}" alt="{}" style="width:120px;height:90px;object-fit:cover"></a>',
                                            ((url, url, alt) for url, alt in pictures)))

    def get_queryset(self, request):
        queryset = super().get_queryset(request).prefetch_related('master_salons__salon')
        return queryset.filter(user_id=request.user.pk) if self.is_own_profile(request) else queryset

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.page_id:
            align_page(obj.page, root_page('team'))
            if self.is_own_profile(request):
                page = obj.page
                page.title = form.cleaned_data['page_title'] or obj.name
                page.content = form.cleaned_data['page_content']
                page.meta_title = form.cleaned_data['page_meta_title']
                page.meta_description = form.cleaned_data['page_meta_description']
                page.is_published = form.cleaned_data['page_is_published']
                page.save(update_fields=['title', 'content', 'meta_title',
                                         'meta_description', 'is_published'])
            page = obj.page
            last_position = page.pictures.aggregate(value=Max('position'))['value']
            position = last_position if last_position is not None else -1
            for upload in form.cleaned_data.get('work_photos') or []:
                position += 1
                image = FilerImage.objects.create(
                    original_filename=upload.name, name=f'{obj.name}: работа {position}'[:255],
                    file=upload, owner=request.user,
                )
                PagePicture.objects.create(page=page, image=image,
                                           alt=f'Работа мастера {obj.name}'[:255],
                                           position=position)

    @admin.display(description='Салоны')
    def salons_display(self, obj):
        return ', '.join(link.salon.name for link in obj.master_salons.all())

    @admin.display(description='YCLIENTS staff ID по салонам')
    def salon_staff_ids(self, obj):
        return ', '.join(
            f'{link.salon.name}: {link.yclients_staff_id or "—"}'
            for link in obj.master_salons.all()
        ) or '—'
