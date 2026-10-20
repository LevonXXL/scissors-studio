"""Validate and align pages linked to catalogue records in Django Admin."""

from django import forms
from django.core.exceptions import ValidationError

from pages.models import Page


def page_owners(page):
    from masters.models import Master
    from salons.models import Salon
    from services.models import Service, ServiceCategory

    owners = []
    for model in (Master, Salon, ServiceCategory, Service):
        owner_id = model.objects.filter(page_id=page.pk).values_list('pk', flat=True).first()
        if owner_id is not None:
            owners.append((model, owner_id))
    return owners


def root_page(path):
    page = Page.objects.filter(url_path=path, parent__isnull=True).first()
    if page is None:
        raise ValidationError(f'Сначала создайте корневую страницу «{path}» через populate_site_pages.')
    return page


def validate_page_parent(page, parent):
    if parent is None:
        raise ValidationError('Сначала привяжите страницу к категории услуг.')
    if page.pk == parent.pk or parent.is_descendant_of(page):
        raise ValidationError('Страница не может быть родителем самой себя или своего предка.')
    path = f'{parent.url_path}/{page.url}'.strip('/')
    if Page.objects.filter(url_path=path).exclude(pk=page.pk).exists():
        raise ValidationError(f'Адрес «{path}» уже занят другой страницей.')


def align_page(page, parent):
    validate_page_parent(page, parent)
    if page.parent_id != parent.pk:
        page.parent = parent
        page.save(update_fields=['parent'])


class RelatedPageFormMixin:
    def clean(self):
        cleaned = super().clean()
        page = cleaned.get('page')
        if page:
            try:
                if any(
                    model != self._meta.model or owner_id != self.instance.pk
                    for model, owner_id in page_owners(page)
                ):
                    raise ValidationError('Страница уже связана с другой записью.')
                validate_page_parent(page, self.page_parent(cleaned))
            except ValidationError as exc:
                self.add_error('page', exc)
        return cleaned


def linked_parent(page_id):
    from masters.models import Master
    from salons.models import Salon
    from services.models import Service, ServiceCategory

    owners = page_owners(Page(pk=page_id))
    if len(owners) > 1:
        raise ValidationError('Страница связана с несколькими записями; исправьте связи перед сохранением.')
    if not owners:
        return None
    model, owner_id = owners[0]
    if model is Master:
        return root_page('team')
    if model is Salon:
        return root_page('salons')
    if model is ServiceCategory:
        return root_page('services')
    service = Service.objects.select_related('category__page').get(pk=owner_id)
    if service.category.page_id is None:
        raise ValidationError('Сначала привяжите страницу к категории услуг.')
    return service.category.page


class PageAdminForm(forms.ModelForm):
    class Meta:
        model = Page
        fields = '__all__'

    def clean(self):
        cleaned = super().clean()
        if self.instance.pk:
            try:
                parent = linked_parent(self.instance.pk)
                if parent:
                    cleaned['parent'] = parent
                from salons.models import Salon
                salon = Salon.objects.filter(page_id=self.instance.pk).first()
                if salon and cleaned.get('url') != salon.slug:
                    self.add_error('url', 'Адрес страницы должен совпадать со slug салона; измените slug в карточке салона.')
            except ValidationError as exc:
                self.add_error('parent', exc)
        return cleaned
