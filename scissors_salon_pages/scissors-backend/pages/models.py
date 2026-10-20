from django.db import models
from django_ckeditor_5.fields import CKEditor5Field
from mptt.fields import TreeForeignKey
from mptt.models import MPTTModel

from core_utils.slugify_ru import slugify_ru


class Page(MPTTModel):
    """
    Статическая страница с древовидной структурой (разделы/подразделы).

    Упрощённая версия модели из chinese-russian: там она заточена под
    мультиязычность (title/_en/_cn, PageContent на каждый язык, поиск через
    Sphinx, теги, рейтинги, закладки) — для одноязычного сайта Scissors
    Studio всё это лишний вес, оставлена только нужная часть.
    """

    class MPTTMeta:
        order_insertion_by = ('position',)

    class Meta:
        verbose_name = 'Страница'
        verbose_name_plural = 'Страницы'
        ordering = ('position',)

    title = models.CharField('Заголовок', max_length=255)
    content = CKEditor5Field('Содержание', config_name='default', blank=True)

    meta_title = models.CharField(
        'Заголовок для <title>, хлебных крошек и меню',
        max_length=255, blank=True,
        help_text='Если не заполнено — используется Заголовок.',
    )
    meta_description = models.CharField(
        'Meta description', max_length=255, blank=True,
        help_text=(
            'Тег meta-description для поисковиков. Также используется как '
            'краткое описание страницы в списках/карточках на сайте.'
        ),
    )

    url = models.SlugField('Адрес (slug)', max_length=255, blank=True, unique=True)
    url_path = models.CharField(max_length=1024, unique=True, db_index=True, editable=False)

    parent = TreeForeignKey(
        'self', verbose_name='Родительская страница',
        null=True, blank=True, related_name='children', on_delete=models.SET_NULL,
    )

    is_published = models.BooleanField('Опубликовано', default=True)
    position = models.IntegerField('Порядок отображения', default=0, blank=True)

    def __str__(self):
        return self.title or self.url

    @property
    def title_tag(self):
        """Для <title>, хлебных крошек и меню — с фолбэком на title."""
        return self.meta_title or self.title

    def save(self, *args, **kwargs):
        if not self.url:
            base_slug = slugify_ru(self.title) or 'page'
            slug = base_slug
            i = 1
            while Page.objects.filter(url=slug).exclude(pk=self.pk).exists():
                i += 1
                slug = f'{base_slug}-{i}'
            self.url = slug

        if self.parent:
            self.url_path = f'{self.parent.url_path}/{self.url}'.strip('/')
        else:
            self.url_path = self.url

        super().save(*args, **kwargs)

        # Каскадно пересчитываем url_path у прямых потомков — их save()
        # рекурсивно пересчитает своих собственных потомков.
        for child in self.get_children():
            new_path = f'{self.url_path}/{child.url}'.strip('/')
            if child.url_path != new_path:
                child.url_path = new_path
                child.save()


class PagePicture(models.Model):
    """Изображение, прикреплённое к странице. Обычный ImageField — Filer
    здесь избыточен, галерея на несколько картинок на страницу не требует
    медиатеки с переиспользованием файлов между страницами."""

    page = models.ForeignKey(Page, verbose_name='Страница', related_name='pictures', on_delete=models.CASCADE)
    image = models.ImageField('Изображение', upload_to='pages/pictures/')
    alt = models.CharField('Alt-текст', max_length=255, blank=True, help_text='Для доступности и SEO.')
    position = models.PositiveIntegerField('Сортировка', default=0)

    class Meta:
        verbose_name = 'Изображение страницы'
        verbose_name_plural = 'Изображения страницы'
        ordering = ('position', 'id')

    def __str__(self):
        return f'Изображение для «{self.page}»'
