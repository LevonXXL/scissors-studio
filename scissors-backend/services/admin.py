from django.contrib import admin
from django.contrib import messages
from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import path, reverse
import base64
from collections import Counter
import re

from pages.admin_links import RelatedPageFormMixin, align_page, root_page
from salons.models import Salon

from .models import Service, ServiceCategory, ServiceStaffPrice, ServiceSalon, ServicePrice
from .excel_import import (read_xlsx, preview_candidates, describe_change, apply_preview,
                           describe_details, validate_salon, salon_matches_city,
                           LABELS, CATEGORIES)
from .unified_excel_import import (apply_unified_preview, candidate_services,
                                   describe_unified_details, is_unified_workbook,
                                   read_unified_xlsx, resolve_unified_match,
                                   salons_for_unified_import,
                                   suggested_services)


class ServiceCategoryAdminForm(RelatedPageFormMixin, forms.ModelForm):
    class Meta:
        model = ServiceCategory
        fields = '__all__'
        exclude = ('image_path',)

    def page_parent(self, cleaned):
        return root_page('uslugi')


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


class ServiceSalonInline(admin.TabularInline):
    model = ServiceSalon
    extra = 0
    autocomplete_fields = ('salon',)


class ServicePriceInline(admin.TabularInline):
    model = ServicePrice
    extra = 0


@admin.register(ServiceCategory)
class ServiceCategoryAdmin(admin.ModelAdmin):
    change_list_template = 'admin/services/servicecategory/change_list.html'
    form = ServiceCategoryAdminForm
    autocomplete_fields = ('page',)
    list_display = ('title', 'code', 'weight', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('title',)

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.page_id:
            align_page(obj.page, root_page('uslugi'))

    def get_urls(self):
        return [path('import-excel/', self.admin_site.admin_view(self.import_excel),
                     name='services_servicecategory_import_excel')] + super().get_urls()

    def import_excel(self, request):
        if not self.has_change_permission(request):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        if request.method == 'POST' and 'file' in request.FILES:
            uploaded = request.FILES['file']
            data = uploaded.read()
            uploaded.seek(0)
            if is_unified_workbook(data):
                return self.import_unified_excel(request)
            for key in ('service_unified_excel_data', 'service_unified_excel_digest',
                        'service_unified_excel_matches', 'service_unified_excel_reviewed'):
                request.session.pop(key, None)
        elif request.session.get('service_unified_excel_data') or not request.session.get('service_excel_data'):
            return self.import_unified_excel(request)
        preview = None
        session_keys = ('service_excel_data', 'service_excel_digest', 'service_excel_salon_id',
                        'service_excel_matches', 'service_excel_reviewed')
        if request.method == 'POST' and 'file' in request.FILES:
            uploaded = request.FILES['file']
            try:
                for key in session_keys:
                    request.session.pop(key, None)
                salon_id = request.POST.get('salon')
                salon = Salon.objects.filter(pk=salon_id, is_active=True).first()
                if salon is None:
                    raise ValueError('Выберите салон для загрузки прайса.')
                data = uploaded.read()
                if len(data) > 5_000_000:
                    raise ValueError('Файл больше 5 МБ.')
                preview = read_xlsx(data)
                validate_salon(preview, salon)
                request.session['service_excel_data'] = base64.b64encode(data).decode('ascii')
                request.session['service_excel_digest'] = preview['digest']
                request.session['service_excel_salon_id'] = salon.pk
                if not salon_matches_city(preview, salon):
                    messages.warning(request, 'В файле указан другой город. Цены будут записаны только '
                                     f'для выбранного салона «{salon.name}».')
            except (ValueError, KeyError, IndexError, OSError) as exc:
                messages.error(request, str(exc))
        elif request.session.get('service_excel_data'):
            try:
                preview = read_xlsx(base64.b64decode(request.session['service_excel_data']))
                if preview['digest'] != request.session.get('service_excel_digest'):
                    raise ValueError('Файл предпросмотра изменился; загрузите его снова.')
            except (ValueError, KeyError, IndexError, OSError) as exc:
                messages.error(request, str(exc))
                preview = None
        selected_salon = (Salon.objects.filter(pk=request.session.get('service_excel_salon_id'),
                                              is_active=True).first() if preview else None)
        action = (request.POST.get('review_matches') or
                  request.POST.get('apply_selected')) if request.method == 'POST' else None
        submitted_matches = {}
        checked_rows = request.POST.getlist('selected_rows') if action else []
        if preview and action:
            try:
                if selected_salon is None:
                    raise ValueError('Сначала выберите салон.')
                validate_salon(preview, selected_salon)
                submitted_matches = {
                    str(row['row']): (request.POST.get(f'match_id_{row["row"]}', '').strip()
                                      or request.POST.get(f'match_{row["row"]}', '').strip())
                    for row in preview['rows']
                }
                for row in preview['rows']:
                    selected = submitted_matches[str(row['row'])]
                    if selected:
                        if not Service.objects.filter(pk=int(selected),
                                                      category__code=row['category']).exists():
                            raise ValueError(f'Строка {row["row"]}: выбранная услуга не найдена в категории.')
                if request.POST.get('review_matches'):
                    request.session['service_excel_matches'] = submitted_matches
                    request.session['service_excel_reviewed'] = True
                else:
                    if not request.session.get('service_excel_reviewed'):
                        raise ValueError('Сначала проверьте сопоставления и изменения.')
                    if submitted_matches != request.session.get('service_excel_matches'):
                        request.session['service_excel_reviewed'] = False
                        raise ValueError('Сопоставления изменились. Обновите предпросмотр перед применением.')
                    selected_rows = checked_rows
                    if not selected_rows:
                        raise ValueError('Отметьте строки для применения.')
                    count = apply_preview(preview, selected_salon, submitted_matches, selected_rows)
                    for key in session_keys:
                        request.session.pop(key, None)
                    messages.success(request, f'Импорт в «{selected_salon.name}» завершён. Изменений: {count}.')
                    return HttpResponseRedirect(reverse('admin:services_servicecategory_changelist'))
            except (ValueError, Service.DoesNotExist) as exc:
                if request.POST.get('review_matches'):
                    request.session.pop('service_excel_reviewed', None)
                messages.error(request, str(exc))
        rows = []
        changes = Counter()
        if preview:
            reviewed = request.session.get('service_excel_reviewed', False)
            matches = (request.session.get('service_excel_matches', {}) if reviewed else submitted_matches)
            for row in preview['rows']:
                matched_id = matches.get(str(row['row']), '')
                suggestions = preview_candidates(row)
                try:
                    change = (describe_change(row, selected_salon, matched_id)
                              if selected_salon else 'Выберите салон')
                    details = describe_details(row, selected_salon, matched_id) if selected_salon else []
                except (ValueError, Service.DoesNotExist):
                    change = 'Неверное сопоставление'
                    details = ['Выберите существующую услугу этой категории.']
                changes[change] += 1
                rows.append({**row, 'candidates': suggestions,
                             'category_title': CATEGORIES[row['category']][0],
                             'matched_id': matched_id,
                             'manual_match_id': (matched_id if matched_id and
                                                 not any(str(c['id']) == matched_id for c in suggestions) else ''),
                             'change': change,
                             'details': details,
                             'checked': str(row['row']) in checked_rows,
                             'price_lines': [
                                 {'label': LABELS[price['level']],
                                  'value': (f'{price["amount"]} ₽' if price['status'] == 'amount' else
                                            '—' if price['status'] == 'dash' else 'пусто')}
                                 for price in row['prices']
                             ]})
        return render(request, 'admin/services/import_excel.html', {
            **self.admin_site.each_context(request), 'title': 'Импорт Excel-прайса',
            'preview': preview, 'rows': rows, 'salons': Salon.objects.filter(is_active=True),
            'selected_salon': selected_salon, 'reviewed': request.session.get('service_excel_reviewed', False),
            'city_mismatch': selected_salon and not salon_matches_city(preview, selected_salon) if preview else False,
            'changes': changes.items(),
            'has_checked_rows': bool(checked_rows),
            'disabled_button_attrs': {'disabled': True},
            'opts': self.model._meta,
        })

    def import_unified_excel(self, request):
        session_keys = ('service_unified_excel_data', 'service_unified_excel_digest')
        preview = None
        apply_error = ''
        failed_row = None
        if request.method == 'POST' and 'file' in request.FILES:
            try:
                for key in (*session_keys, 'service_unified_excel_matches',
                            'service_unified_excel_reviewed'):
                    request.session.pop(key, None)
                for key in ('service_excel_data', 'service_excel_digest', 'service_excel_salon_id',
                            'service_excel_matches', 'service_excel_reviewed'):
                    request.session.pop(key, None)
                data = request.FILES['file'].read()
                if len(data) > 5_000_000:
                    raise ValueError('Файл больше 5 МБ.')
                preview = read_unified_xlsx(data)
                request.session['service_unified_excel_data'] = base64.b64encode(data).decode('ascii')
                request.session['service_unified_excel_digest'] = preview['digest']
            except (ValueError, KeyError, IndexError, OSError) as exc:
                messages.error(request, str(exc))
        elif request.session.get('service_unified_excel_data'):
            try:
                preview = read_unified_xlsx(base64.b64decode(request.session['service_unified_excel_data']))
                if preview['digest'] != request.session.get('service_unified_excel_digest'):
                    raise ValueError('Файл предпросмотра изменился; загрузите его снова.')
            except (ValueError, KeyError, IndexError, OSError) as exc:
                messages.error(request, str(exc))
        action = (request.POST.get('review_matches') or request.POST.get('apply_selected')) if request.method == 'POST' else None
        checked_rows = request.POST.getlist('selected_rows') if action else []
        submitted_matches = {}
        if preview and action:
            try:
                submitted_matches = {
                    str(item['row']): request.POST.get(f'match_{item["row"]}', '').strip()
                    for item in preview['rows']
                }
                if request.POST.get('apply_selected'):
                    count = apply_unified_preview(preview, submitted_matches, checked_rows)
                    for key in session_keys:
                        request.session.pop(key, None)
                    messages.success(request, f'Единый прайс применён для двух салонов. Изменений: {count}.')
                    return HttpResponseRedirect(reverse('admin:services_servicecategory_changelist'))
            except (ValueError, Service.DoesNotExist) as exc:
                if request.POST.get('apply_selected'):
                    apply_error = str(exc)
                    match = re.search(r'Строка (\d+)', apply_error)
                    failed_row = int(match.group(1)) if match else None
                messages.error(request, str(exc))
        rows = []
        if preview:
            try:
                salons = salons_for_unified_import()
            except ValueError as exc:
                messages.error(request, str(exc))
                salons = {}
            matches = submitted_matches
            for item in preview['rows']:
                suggestions = suggested_services(item)
                automatic = candidate_services(item)
                selected = matches.get(str(item['row']), '')
                matched_service, match_error = resolve_unified_match(item, selected, automatic)
                errors = [issue['message'] for issue in preview['issues']
                          if item['row'] in issue['rows']]
                if match_error:
                    errors.append(match_error)
                rows.append({
                    **item, 'candidates': suggestions,
                    'automatic': automatic[0] if len(automatic) == 1 else None,
                    'ambiguous': len(automatic) > 1,
                    'selected_match': selected,
                    'checked': str(item['row']) in checked_rows if action else not errors,
                    'errors': errors,
                    'matched_service_id': matched_service.pk if matched_service else None,
                    'details': describe_unified_details(item, matched_service, salons) if salons else [],
                })
            match_counts = Counter(row['matched_service_id'] for row in rows
                                   if row['matched_service_id'])
            for row in rows:
                if row['matched_service_id'] and match_counts[row['matched_service_id']] > 1:
                    row['errors'].append('Другая строка прайса сопоставлена с этой же услугой.')
                    if not action:
                        row['checked'] = False
            problem_rows = [row for row in rows if row['errors']]
        else:
            problem_rows = []
        return render(request, 'admin/services/import_unified_excel.html', {
            **self.admin_site.each_context(request), 'title': 'Импорт единого Excel-прайса',
            'preview': preview, 'rows': rows, 'problem_rows': problem_rows,
            'ready_count': len(rows) - len(problem_rows),
            'selected_count': sum(row['checked'] for row in rows),
            'apply_error': apply_error, 'failed_row': failed_row,
            'opts': self.model._meta,
        })


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    change_list_template = 'admin/services/service/change_list.html'
    form = ServiceAdminForm
    autocomplete_fields = ('page',)
    list_display = ('title', 'price_code', 'category', 'group_title', 'price_internal_category',
                    'duration_display', 'is_active', 'last_synced_at')
    list_filter = ('category', 'is_active')
    search_fields = ('title', 'price_code')
    readonly_fields = ('yclients_service_id', 'last_synced_at')
    inlines = (ServiceSalonInline, ServiceStaffPriceInline)

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.page_id:
            align_page(obj.page, obj.category.page)


@admin.register(ServiceSalon)
class ServiceSalonAdmin(admin.ModelAdmin):
    list_display = ('service', 'salon', 'is_active', 'position')
    list_filter = ('salon', 'is_active')
    search_fields = ('service__title',)
    autocomplete_fields = ('service', 'salon')
    inlines = (ServicePriceInline,)
