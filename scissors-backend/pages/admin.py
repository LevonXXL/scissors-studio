from django.contrib import admin
from django_ckeditor_5.widgets import CKEditor5Widget
from mptt.admin import DraggableMPTTAdmin

from .admin_links import PageAdminForm
from .models import Page, PagePicture
from masters.models import Master


def own_master_page_id(request):
    if not request.user.is_staff:
        return None
    master = Master.objects.filter(user_id=request.user.pk).values('page_id').first()
    return (master['page_id'] or 0) if master else None


class PagePictureInline(admin.TabularInline):
    model = PagePicture
    extra = 1
    fields = ('image', 'legacy_image', 'alt', 'position')
    readonly_fields = ('legacy_image',)

    def has_add_permission(self, request, obj=None):
        page_id = own_master_page_id(request)
        if page_id is not None:
            return obj is not None and obj.pk == page_id
        return super().has_add_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        page_id = own_master_page_id(request)
        if page_id is not None:
            return obj is not None and obj.pk == page_id
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        page_id = own_master_page_id(request)
        if page_id is not None:
            return obj is not None and obj.pk == page_id
        return super().has_delete_permission(request, obj)


@admin.register(Page)
class PageAdmin(DraggableMPTTAdmin):
    form = PageAdminForm
    list_display = ('tree_actions', 'indented_title', 'url_path', 'is_published', 'position')
    list_display_links = ('indented_title',)
    search_fields = ('title', 'url', 'url_path')
    readonly_fields = ('url_path',)
    inlines = (PagePictureInline,)
    fieldsets = (
        (None, {'fields': ('parent', 'title', 'content', 'is_published', 'position')}),
        ('SEO', {'fields': ('meta_title', 'meta_description', 'url', 'url_path')}),
    )
    widgets = {
        "content": CKEditor5Widget(config_name="default"),
    }

    def has_module_permission(self, request):
        return own_master_page_id(request) is not None or super().has_module_permission(request)

    def has_view_permission(self, request, obj=None):
        page_id = own_master_page_id(request)
        if page_id is not None:
            return obj is None or obj.pk == page_id
        return super().has_view_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        page_id = own_master_page_id(request)
        if page_id is not None:
            return obj is None or obj.pk == page_id
        return super().has_change_permission(request, obj)

    def has_add_permission(self, request):
        if own_master_page_id(request) is not None:
            return False
        return super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        if own_master_page_id(request) is not None:
            return False
        return super().has_delete_permission(request, obj)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        page_id = own_master_page_id(request)
        return queryset.filter(pk=page_id) if page_id is not None else queryset

    def get_fieldsets(self, request, obj=None):
        if own_master_page_id(request) is not None:
            return (
                (None, {'fields': ('title', 'content', 'is_published')}),
                ('SEO', {'fields': ('meta_title', 'meta_description')}),
            )
        return super().get_fieldsets(request, obj)
