from django.contrib import admin

from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('author', 'salon', 'source_display', 'rating', 'review_date', 'has_images', 'has_videos', 'is_approved')
    list_editable = ('is_approved',)
    list_filter = ('is_approved', 'salon', 'source', 'rating', 'has_images')
    search_fields = ('author', 'text')
    readonly_fields = (
        'rewio_review_id', 'rewio_link_id', 'source', 'salon',
        'review_date', 'review_url', 'reply_date',
        'has_images', 'has_videos', 'created_at', 'updated_at',
    )
    date_hierarchy = 'review_date'

    @admin.display(description='Площадка', ordering='source')
    def source_display(self, obj):
        return obj.get_source_display()

    fieldsets = (
        (None, {
            'fields': ('salon', 'author', 'rating', 'review_date', 'review_url', 'is_approved'),
        }),
        ('Текст отзыва', {
            'fields': ('text',),
        }),
        ('Ответ заведения', {
            'fields': ('reply_text', 'reply_date'),
        }),
        ('Медиа', {
            'fields': ('has_images', 'images', 'has_videos', 'videos'),
        }),
        ('Rewio', {
            'fields': ('rewio_review_id', 'rewio_link_id', 'source'),
            'classes': ('collapse',),
        }),
    )
