from datetime import timedelta

from django.contrib import admin
from django.contrib import messages
from django import forms
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django_ckeditor_5.widgets import CKEditor5Widget
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.template.loader import render_to_string
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe
from filer.models import Image as FilerImage

from pages.admin_links import RelatedPageFormMixin, align_page, root_page
from pages.models import PagePicture
from services.models import Service, ServiceSalon, ServiceStaffPrice
from services.master_offers import priced_offers_for_master
from .bot import create_pairing_code

from .models import Master, MasterSalon, MasterServiceWorkPhoto, MasterMessengerAccount


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


class ServiceWorkPhotoUploadForm(forms.Form):
    service = forms.ModelChoiceField(label='Услуга', queryset=Service.objects.none())
    image = forms.ImageField(label='Фотография')
    caption = forms.CharField(label='Подпись', max_length=255, required=False)

    def __init__(self, *args, master, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['service'].queryset = Service.objects.filter(
            staff_prices__master=master, is_active=True, category__is_active=True,
        ).distinct().order_by('title')

    def clean_image(self):
        image = self.cleaned_data['image']
        if image.size > 10_000_000:
            raise ValidationError('Фотография должна быть не больше 10 МБ.')
        return image


class MasterSalonInlineForm(forms.ModelForm):
    class Meta:
        model = MasterSalon
        fields = ('salon', 'yclients_staff_id', 'yclients_booking_url')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['salon'].label = 'Салон'
        self.fields['salon'].help_text = (
            'Выберите салон, в котором работает мастер. После сохранения мастер сможет '
            'добавлять услуги этого салона в своём кабинете.'
        )
        self.fields['yclients_staff_id'].label = 'ID сотрудника в YCLIENTS'
        self.fields['yclients_staff_id'].help_text = (
            'Идентификатор мастера в этом салоне в YCLIENTS. Заполняется при синхронизации; '
            'для ручной привязки оставьте пустым.'
        )
        self.fields['yclients_staff_id'].disabled = True
        self.fields['yclients_booking_url'].label = 'Ссылка на онлайн-запись'
        self.fields['yclients_booking_url'].help_text = (
            'Необязательная прямая ссылка на запись к этому мастеру в выбранном салоне. '
            'Автоматически из YCLIENTS не обновляется.'
        )
        if self.instance.pk:
            self.fields['salon'].disabled = True


class MasterSalonInline(admin.StackedInline):
    model = MasterSalon
    form = MasterSalonInlineForm
    extra = 1
    fields = ('salon', 'yclients_staff_id', 'yclients_booking_url')

    def has_add_permission(self, request, obj=None):
        return request.user.is_superuser


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
        ('Услуги', {'fields': ('service_assignments_link',)}),
        ('Мессенджеры', {'fields': ('messenger_link',)}),
        ('Отображение', {'fields': ('slug', 'page', 'user', 'is_active', 'is_booking_placeholder', 'position')}),
        ('Интеграция с YCLIENTS', {
            'fields': ('yclients_user_id', 'last_synced_at'),
            'description': (
                'yclients_user_id — кросс-салонный ID (одинаковый во всех филиалах). '
                # 'yclients_staff_id — legacy, per-salon ID теперь в таблице «Салоны» ниже.'
            ),
        }),
        ('Примеры работ', {'fields': ('work_photo_gallery', 'work_photos',
                                    'service_work_photo_link')}),
    )
    readonly_fields = ('slug', 'yclients_user_id', 'last_synced_at')

    def get_urls(self):
        return [
            path('<path:object_id>/services/', self.admin_site.admin_view(self.edit_services),
                 name='masters_master_services'),
            path('<path:object_id>/service-work/', self.admin_site.admin_view(self.edit_service_work),
                 name='masters_master_service_work'),
            path('<path:object_id>/messenger/', self.admin_site.admin_view(self.edit_messenger),
                 name='masters_master_messenger'),
        ] + super().get_urls()

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
                ('Услуги', {'fields': ('service_assignments_link',)}),
                ('Мессенджеры', {'fields': ('messenger_link',)}),
                ('Страница мастера', {'fields': (
                    'page_title', 'page_content', 'page_meta_title',
                    'page_meta_description', 'page_is_published', 'master_page_link',
                )}),
                ('Примеры работ', {'fields': ('work_photo_gallery', 'work_photos',
                                            'service_work_photo_link')}),
            )
        return super().get_fieldsets(request, obj)

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        if self.is_own_profile(request):
            return (*fields, 'master_page_link', 'work_photo_gallery',
                    'service_assignments_link', 'service_work_photo_link',
                    'messenger_link')
        return (*fields, 'work_photo_gallery', 'service_assignments_link',
                'service_work_photo_link', 'messenger_link')

    def get_inlines(self, request, obj=None):
        return [] if self.is_own_profile(request) else super().get_inlines(request, obj)

    @admin.display(description='Назначения услуг')
    def service_assignments_link(self, obj):
        if not obj or not obj.pk:
            return 'Сохраните профиль, чтобы назначать услуги.'
        count = ServiceStaffPrice.objects.filter(master=obj).count()
        return format_html('<a href="{}">Редактировать услуги и длительность</a> · назначений: {}',
                           reverse('admin:masters_master_services', args=[obj.pk]), count)

    @admin.display(description='Работы по услугам')
    def service_work_photo_link(self, obj):
        if not obj or not obj.pk:
            return 'Сохраните профиль, чтобы загрузить работы.'
        count = MasterServiceWorkPhoto.objects.filter(master=obj).count()
        return format_html('<a href="{}">Открыть галерею по услугам</a> · фотографий: {}',
                           reverse('admin:masters_master_service_work', args=[obj.pk]), count)

    @admin.display(description='Бот для мастера')
    def messenger_link(self, obj):
        if not obj or not obj.pk:
            return 'Сохраните профиль, чтобы подключить бота.'
        return mark_safe(render_to_string('admin/masters/master/messenger_link.html', {
            'url': reverse('admin:masters_master_messenger', args=[obj.pk]),
        }))

    def edit_messenger(self, request, object_id):
        master = get_object_or_404(self.get_queryset(request), pk=object_id)
        if not self.has_change_permission(request, master):
            raise PermissionDenied
        code = None
        code_lifetime = None
        if request.method == 'POST':
            if request.POST.get('action') == 'generate':
                code = create_pairing_code(master)
                code_lifetime = '15 минут'
            elif request.POST.get('action') == 'generate_daily':
                code = create_pairing_code(master, validity=timedelta(days=1))
                code_lifetime = '24 часа'
            elif request.POST.get('action') == 'disconnect':
                account = get_object_or_404(MasterMessengerAccount,
                                            pk=request.POST.get('account_id'), master=master)
                account.delete()
                messages.success(request, 'Мессенджер отключён.')
                return redirect('admin:masters_master_messenger', object_id=master.pk)
        return render(request, 'admin/masters/master/messenger.html', {
            **self.admin_site.each_context(request),
            'title': f'Мессенджеры мастера {master.name}', 'master': master,
            'code': code, 'code_lifetime': code_lifetime,
            'accounts': master.messenger_accounts.all(), 'opts': self.model._meta,
        })

    def edit_service_work(self, request, object_id):
        master = get_object_or_404(self.get_queryset(request), pk=object_id)
        if not self.has_change_permission(request, master):
            raise PermissionDenied
        form = ServiceWorkPhotoUploadForm(master=master)
        if request.method == 'POST':
            if request.POST.get('action') == 'upload':
                form = ServiceWorkPhotoUploadForm(request.POST, request.FILES, master=master)
                if form.is_valid():
                    with transaction.atomic():
                        upload = form.cleaned_data['image']
                        image = FilerImage.objects.create(
                            original_filename=upload.name,
                            name=f'{master.name}: {form.cleaned_data["service"].title}'[:255],
                            file=upload, owner=request.user,
                        )
                        photo = MasterServiceWorkPhoto(
                            master=master, service=form.cleaned_data['service'], image=image,
                            caption=form.cleaned_data['caption'],
                        )
                        photo.full_clean()
                        photo.save()
                    messages.success(request, 'Фотография работы добавлена.')
                    return redirect('admin:masters_master_service_work', object_id=master.pk)
            elif request.POST.get('action') == 'delete':
                photo = get_object_or_404(MasterServiceWorkPhoto, pk=request.POST.get('photo_id'),
                                          master=master)
                photo.delete()
                messages.success(request, 'Фотография удалена из галереи.')
                return redirect('admin:masters_master_service_work', object_id=master.pk)
        photos = MasterServiceWorkPhoto.objects.filter(master=master).select_related('service', 'image')
        return render(request, 'admin/masters/master/service_work.html', {
            **self.admin_site.each_context(request), 'title': f'Работы мастера {master.name}',
            'master': master, 'form': form, 'photos': photos, 'opts': self.model._meta,
        })

    def edit_services(self, request, object_id):
        master = get_object_or_404(self.get_queryset(request), pk=object_id)
        if not self.has_change_permission(request, master):
            raise PermissionDenied
        salon_ids = list(master.master_salons.values_list('salon_id', flat=True))
        offers = list(priced_offers_for_master(master, salon_ids).select_related(
            'salon', 'service', 'service__category').order_by(
            'salon__name', 'service__category__title', 'service__title'))
        offers_by_key = {(offer.salon_id, offer.service_id): offer for offer in offers}
        if request.method == 'POST':
            try:
                action = request.POST.get('action')
                salon_id = int(request.POST.get('salon_id', ''))
                service_id = int(request.POST.get('service_id', ''))
                if salon_id not in salon_ids:
                    raise ValueError('Мастер не работает в выбранном салоне.')
                if action in ('add', 'update') and (salon_id, service_id) not in offers_by_key:
                    raise ValueError('Услуга недоступна в салоне или для уровня мастера нет цены.')
                if action in ('add', 'update'):
                    raw_minutes = request.POST.get('duration_minutes', '').strip()
                    if raw_minutes and (not raw_minutes.isdecimal() or int(raw_minutes) < 1):
                        raise ValueError('Длительность должна быть положительным числом минут.')
                    duration = int(raw_minutes) * 60 if raw_minutes else None
                    with transaction.atomic():
                        assignment, created = ServiceStaffPrice.objects.get_or_create(
                            master=master, salon_id=salon_id, service_id=service_id)
                        if action == 'update' and created:
                            raise ValueError('Назначение не найдено.')
                        assignment.duration_seconds = duration
                        assignment.full_clean()
                        assignment.save(update_fields=['duration_seconds'])
                    messages.success(request, 'Назначение услуги сохранено.')
                elif action == 'remove':
                    deleted, _ = ServiceStaffPrice.objects.filter(
                        master=master, salon_id=salon_id, service_id=service_id).delete()
                    if not deleted:
                        raise ValueError('Назначение не найдено.')
                    messages.success(request, 'Назначение услуги удалено.')
                else:
                    raise ValueError('Неизвестное действие.')
                return redirect('admin:masters_master_services', object_id=master.pk)
            except (TypeError, ValueError, ValidationError) as exc:
                messages.error(request, str(exc))
        assignments = {(item.salon_id, item.service_id): item for item in
                       ServiceStaffPrice.objects.filter(master=master, salon_id__in=salon_ids)
                       .select_related('service', 'salon')}
        for assignment in assignments.values():
            assignment.admin_duration_minutes = (
                assignment.duration_seconds // 60 if assignment.duration_seconds is not None
                and assignment.duration_seconds % 60 == 0 else None
            )
            assignment.admin_can_update = (assignment.salon_id, assignment.service_id) in offers_by_key
        salons = []
        for link in master.master_salons.select_related('salon').order_by('salon__name'):
            salon_offers = [offer for offer in offers if offer.salon_id == link.salon_id]
            salons.append({
                'salon': link.salon,
                'available': [offer for offer in salon_offers
                              if (offer.salon_id, offer.service_id) not in assignments],
                'assigned': sorted((assignment for assignment in assignments.values()
                                    if assignment.salon_id == link.salon_id),
                                   key=lambda assignment: assignment.service.title),
            })
        return render(request, 'admin/masters/master/services.html', {
            **self.admin_site.each_context(request),
            'title': f'Услуги мастера {master.name}', 'master': master,
            'salons': salons, 'opts': self.model._meta,
        })

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


@admin.register(MasterServiceWorkPhoto)
class MasterServiceWorkPhotoAdmin(admin.ModelAdmin):
    list_display = ('master', 'service', 'caption', 'position', 'created_at')
    list_filter = ('service__category',)
    search_fields = ('master__name', 'service__title', 'caption')
    autocomplete_fields = ('master', 'service')


@admin.register(MasterMessengerAccount)
class MasterMessengerAccountAdmin(admin.ModelAdmin):
    list_display = ('master', 'platform', 'external_user_id', 'linked_at')
    search_fields = ('master__name', 'external_user_id')
    list_filter = ('platform',)
