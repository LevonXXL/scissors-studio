from django.core.exceptions import ValidationError
from django.db import models, transaction
from django_ckeditor_5.fields import CKEditor5Field
from filer.fields.image import FilerImageField
from mptt.fields import TreeForeignKey
from mptt.models import MPTTModel


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

    url = models.SlugField(
        'Адрес (slug)', max_length=255, blank=True,
        help_text='Оставьте пустым только для главной; у вложенной страницы укажите один сегмент пути.',
    )
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

    def _expected_url_path(self):
        if not self.parent_id:
            return self.url
        parent_path = Page.objects.values_list('url_path', flat=True).get(pk=self.parent_id)
        return f'{parent_path}/{self.url}'.strip('/')

    def clean(self):
        super().clean()
        if self.parent_id and not self.url:
            raise ValidationError({'url': 'У вложенной страницы должен быть адрес.'})
        path = self._expected_url_path()
        if Page.objects.filter(url_path=path).exclude(pk=self.pk).exists():
            raise ValidationError({'url': 'Страница с таким путём уже существует.'})

    def save(self, *args, **kwargs):
        if self.parent_id and not self.url:
            raise ValidationError({'url': 'У вложенной страницы должен быть адрес.'})
        if self.url:
            self._meta.get_field('url').run_validators(self.url)

        with transaction.atomic():
            previous = (
                Page.objects.filter(pk=self.pk).values('url', 'parent_id', 'url_path').first()
                if self.pk else None
            )
            previous_path = previous['url_path'] if previous else None
            self.url_path = self._expected_url_path()
            if kwargs.get('update_fields') is not None and previous:
                update_fields = set(kwargs['update_fields'])
                if self.url != previous['url']:
                    update_fields.add('url')
                if self.parent_id != previous['parent_id']:
                    update_fields.add('parent')
                if self.url_path != previous_path:
                    update_fields.add('url_path')
                kwargs['update_fields'] = update_fields
            super().save(*args, **kwargs)

            if previous_path != self.url_path:
                paths = {self.pk: self.url_path}
                for descendant in self.get_descendants().order_by('level', 'lft'):
                    path = f'{paths[descendant.parent_id]}/{descendant.url}'.strip('/')
                    if descendant.url_path != path:
                        Page.objects.filter(pk=descendant.pk).update(url_path=path)
                    paths[descendant.pk] = path

    def move_to(self, target, position='first-child'):
        with transaction.atomic():
            return super().move_to(target, position)


class PagePicture(models.Model):
    """Изображение страницы; старые загрузки доступны до переноса в Filer."""

    page = models.ForeignKey(Page, verbose_name='Страница', related_name='pictures', on_delete=models.CASCADE)
    image = FilerImageField(verbose_name='Изображение в Filer', null=True, blank=True,
                            on_delete=models.SET_NULL, related_name='+')
    legacy_image = models.ImageField('Прежнее изображение', upload_to='pages/pictures/', blank=True)
    alt = models.CharField('Alt-текст', max_length=255, blank=True, help_text='Для доступности и SEO.')
    position = models.PositiveIntegerField('Сортировка', default=0)

    class Meta:
        verbose_name = 'Изображение страницы'
        verbose_name_plural = 'Изображения страницы'
        ordering = ('position', 'id')

    def __str__(self):
        return f'Изображение для «{self.page}»'

    @property
    def image_url(self):
        if self.image_id:
            return self.image.url
        if self.legacy_image:
            return self.legacy_image.url
        return ''
