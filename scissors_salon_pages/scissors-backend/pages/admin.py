from django.contrib import admin
from mptt.admin import DraggableMPTTAdmin

from .models import Page, PagePicture


class PagePictureInline(admin.TabularInline):
    model = PagePicture
    extra = 1
    fields = ('image', 'alt', 'position')


@admin.register(Page)
class PageAdmin(DraggableMPTTAdmin):
    list_display = ('tree_actions', 'indented_title', 'url_path', 'is_published', 'position')
    list_display_links = ('indented_title',)
    search_fields = ('title', 'url', 'url_path')
    readonly_fields = ('url_path',)
    inlines = (PagePictureInline,)
    fieldsets = (
        (None, {'fields': ('parent', 'title', 'content', 'is_published', 'position')}),
        ('SEO', {'fields': ('meta_title', 'meta_description', 'url', 'url_path')}),
    )
