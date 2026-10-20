"""Idempotently copy existing site copy into Page records; run manually after migration."""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.html import format_html

from core_utils.slugify_ru import slugify_ru
from masters.models import Master
from pages.models import Page
from salons.models import Salon
from services.models import Service, ServiceCategory


HOME_CONTENT = '''
<div class="text-overline text-primary text-weight-bold">ПРОСТРАНСТВО НЕЗАВИСИМЫХ МАСТЕРОВ SCISSORS STUDIO</div>
<h1 class="text-h3 text-weight-bold q-mt-sm">Стратегический подход к вашему образу</h1>
<p class="text-body1 q-mt-md text-grey-8">У нас можно полностью довериться профессионалам: персональная бьюти-стратегия,
современный подход и точность исполнения гарантируют естественный, уверенный
и безупречный результат.</p>
'''.strip()

TEAM_CONTENT = '''
<p>Категория мастера отражает его опыт, уровень самостоятельности и глубину работы с образом.
Рост категории определяется временем работы в Scissors, регулярным обучением,
подтверждённой квалификацией и вкладом в развитие команды.</p>
<p>Все мастера работают на высоком профессиональном уровне. Разница — в скорости,
опыте и умении выстраивать долгосрочную стратегию работы с клиентом.</p>
'''.strip()

LEGACY_PRIVACY_CONTENT = '''
<p>Настоящая политика обработки персональных данных составлена в соответствии
с требованиями Федерального закона от 27.07.2006 № 152-ФЗ «О персональных
данных» и определяет порядок обработки персональных данных и меры по
обеспечению безопасности персональных данных, предпринимаемые
ИП Стець М. О. (далее — Оператор).</p>
<p>1.1. Оператор ставит своей важнейшей целью и условием осуществления своей
деятельности соблюдение прав и свобод человека и гражданина при обработке
его персональных данных, в том числе защиты прав на неприкосновенность
частной жизни, личную и семейную тайну.</p>
<div class="q-mt-lg bg-grey-2 q-pa-md">Полный текст политики (~26 000 символов на исходном сайте)
переносится отдельным шагом bulk-миграции контента — см. план в README,
раздел «Что дальше». Здесь — реальное начало документа для визуальной проверки
вёрстки страницы.</div>
'''.strip()

PRIVACY_CONTENT = (Path(__file__).resolve().parents[2] / 'content' / 'privacy_policy.html').read_text(
    encoding='utf-8',
).strip()

SERVICES_CONTENT = '''
<p>Стоимость услуг состоит из сервисного обслуживания и услуги мастера.
Категорию мастера смотрите в его карточке — цена зависит от уровня
выбранного специалиста (Универсал/Модельер, Топ-стилист, Арт-директор).</p>
'''.strip()

ABOUT_CONTENT = '''
<p>Привет! Я Михаил Стець, владелец, идейный вдохновитель и арт-директор сети
салонов красоты Scissors.</p>
<p>Scissors — это пространство, где собрана команда партнёров-профессионалов.
Наш общий подход строится на синергии высокого профессионализма и
безупречного сервиса: здесь нет случайных людей, а есть общая цель дарить
вам гармонию и мастерство высшего уровня.</p>
<p>Наша задача — создать тот образ, который будет соответствовать вашему
мироощущению и восприятию себя, вашему образу жизни и задачам.</p>
<p>Приходите в Scissors. Позвольте себе себя.</p>
<p>Михаил Стець</p>
'''.strip()


def find_existing(path, slug, legacy_titles):
    page = Page.objects.filter(url_path=path).first()
    if page:
        return page

    candidates = Page.objects.filter(parent__isnull=True, url=slug)
    if not candidates.exists():
        candidates = Page.objects.filter(parent__isnull=True, title__in=legacy_titles)
    if candidates.count() > 1:
        raise CommandError(f'Несколько страниц подходят для пути «{path}»; требуется ручной выбор.')
    return candidates.first()


def upsert_page(
    *, path, slug, parent, title, content, meta_title='', meta_description='',
    legacy_titles=(), overwrite_content=True, overwrite_title=True, replace_content_if=None,
):
    page = find_existing(path, slug, legacy_titles)
    is_new = page is None
    before = None
    if page is None:
        page = Page(title=title, url=slug, parent=parent)
    else:
        before = (page.url, page.parent_id, page.title, page.content, page.meta_title, page.meta_description)
        page.url = slug
        page.parent = parent
        if overwrite_title or not page.title:
            page.title = title
    if content and (
        overwrite_content or not page.content
        or (replace_content_if is not None and page.content.strip() == replace_content_if.strip())
    ):
        page.content = content
    if meta_title and (overwrite_content or not page.meta_title):
        page.meta_title = meta_title
    if meta_description and (overwrite_content or not page.meta_description):
        page.meta_description = meta_description
    after = (page.url, page.parent_id, page.title, page.content, page.meta_title, page.meta_description)
    if is_new or before != after or page.url_path != path:
        page.save()
    return page


def claimed_by_another(page, model, instance):
    return any(
        (
            related.objects.filter(page=page).exclude(pk=instance.pk).exists()
            if related is model else related.objects.filter(page=page).exists()
        )
        for related in (Master, ServiceCategory, Service)
    )


def available_page(parent, title, model, instance):
    base = slugify_ru(title)[:200] or f'item-{instance.pk}'
    suffix = 0
    while True:
        if suffix == 0:
            slug = base
        elif suffix == 1:
            slug = f'{base}-{instance.pk}'
        else:
            slug = f'{base}-{instance.pk}-{suffix}'
        page = Page.objects.filter(parent=parent, url=slug).first()
        if page is None:
            return page, slug
        if page.title == title[:255] and not claimed_by_another(page, model, instance):
            return page, slug
        suffix += 1


def category_page(category, services_root):
    if category.page_id:
        page = category.page
        if claimed_by_another(page, ServiceCategory, category):
            raise CommandError(f'Страница «{page.url_path}» уже связана с другой записью.')
        expected_path = f'{services_root.url_path}/{page.url}'.strip('/')
        if page.parent_id != services_root.pk or page.url_path != expected_path:
            page.parent = services_root
            page.save()
        return False

    page, slug = available_page(services_root, category.title, ServiceCategory, category)
    created = page is None
    if created:
        page = Page(title=category.title, url=slug, parent=services_root)
    else:
        page.parent = services_root
    page.save()
    category.page = page
    category.save(update_fields=['page'])
    return created


def service_page(service):
    parent = service.category.page
    if service.page_id:
        page = service.page
        if claimed_by_another(page, Service, service):
            raise CommandError(f'Страница «{page.url_path}» уже связана с другой записью.')
        expected_path = f'{parent.url_path}/{page.url}'.strip('/')
        if page.parent_id != parent.pk or page.url_path != expected_path:
            page.parent = parent
            page.save()
        return False

    page, slug = available_page(parent, service.title, Service, service)
    created = page is None
    if created:
        page = Page(
            title=service.title[:255], url=slug, parent=parent,
            content=format_html('<p>{}</p>', service.description) if service.description else '',
        )
    else:
        page.parent = parent
        if not page.content and service.description:
            page.content = format_html('<p>{}</p>', service.description)
    page.save()
    service.page = page
    service.save(update_fields=['page'])
    return created


def salon_page(salon, salons_root):
    if not salon.slug:
        raise CommandError(f'У салона {salon.pk} не заполнен slug; сначала примените миграции.')

    path = f'{salons_root.url_path}/{salon.slug}'
    linked = salon.page
    by_path = Page.objects.filter(url_path=path).first()
    if linked and by_path and linked.pk != by_path.pk:
        raise CommandError(f'Адрес «{path}» занят другой страницей.')

    page = linked or by_path or Page.objects.filter(parent=salons_root, url=salon.slug).first()
    if page is None:
        candidates = [
            candidate for candidate in Page.objects.filter(parent=salons_root, title=salon.name)
            if not Salon.objects.filter(page=candidate).exclude(pk=salon.pk).exists()
            and not claimed_by_another(candidate, Salon, salon)
        ]
        if len(candidates) > 1:
            raise CommandError(f'Несколько страниц подходят для салона {salon.pk}; требуется ручной выбор.')
        page = candidates[0] if candidates else None
    if page is None:
        page = Page(title=salon.name, url=salon.slug, parent=salons_root)
        created = True
    else:
        created = False
        if Salon.objects.filter(page=page).exclude(pk=salon.pk).exists() or claimed_by_another(
            page, Salon, salon,
        ):
            raise CommandError(f'Страница «{page.url_path}» уже связана с другой записью.')
        before = (page.parent_id, page.url, page.title)
        page.parent = salons_root
        page.url = salon.slug
        if not page.title:
            page.title = salon.name

    if created or before != (page.parent_id, page.url, page.title) or page.url_path != path:
        page.save()
    if salon.page_id != page.pk:
        salon.page = page
        salon.save(update_fields=['page'])
    return created


def populate_privacy_page():
    return upsert_page(
        path='privacy', slug='privacy', parent=None,
        title='Политика обработки персональных данных', content=PRIVACY_CONTENT,
        meta_title='Политика обработки персональных данных — Scissors Studio',
        legacy_titles=('Политика конфиденциальности', 'Политика обработки персональных данных'),
        overwrite_content=False, overwrite_title=False,
        replace_content_if=LEGACY_PRIVACY_CONTENT,
    )


class Command(BaseCommand):
    help = 'Создаёт корневые страницы и связывает страницы салонов, мастеров, категорий и услуг без дубликатов.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--only-privacy', action='store_true',
            help='Обновить только страницу политики обработки персональных данных.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options['only_privacy']:
            populate_privacy_page()
            self.stdout.write(self.style.SUCCESS('Страница политики проверена.'))
            return

        upsert_page(
            path='', slug='', parent=None, title='Главная', content=HOME_CONTENT,
            meta_title='Scissors Studio — пространство независимых мастеров',
            meta_description=(
                'Scissors Studio — пространство независимых мастеров-партнёров. '
                'Стратегический подход к вашему образу в Москве и Зеленограде.'
            ),
            legacy_titles=('Главная',),
        )
        team = upsert_page(
            path='team', slug='team', parent=None, title='Команда и портфолио',
            content=TEAM_CONTENT,
            meta_title='Команда и портфолио — Scissors Studio',
            meta_description=(
                'Познакомьтесь с командой мастеров Scissors Studio. Опытные специалисты, '
                'тренеры и арт-директора с международным опытом.'
            ),
            legacy_titles=('Команда', 'Команда и портфолио'),
        )
        populate_privacy_page()
        services_root = upsert_page(
            path='services', slug='services', parent=None,
            title='Услуги и цены', content=SERVICES_CONTENT,
            meta_title='Прайс — Scissors Studio',
            legacy_titles=('Услуги и цены',),
        )
        salons_root = upsert_page(
            path='salons', slug='salons', parent=None,
            title='Салоны', content='', meta_title='Салоны — Scissors Studio',
            legacy_titles=('Салоны',),
            overwrite_content=False, overwrite_title=False,
        )
        upsert_page(
            path='about', slug='about', parent=None,
            title='О нас', content=ABOUT_CONTENT,
            meta_title='О нас — Scissors Studio',
            meta_description='Scissors Studio — пространство, где собрана команда партнёров-профессионалов.',
            legacy_titles=('О нас',),
        )

        salons_added = 0
        for salon in Salon.objects.select_related('page').order_by('pk'):
            salons_added += salon_page(salon, salons_root)

        masters_added = 0
        for master in Master.objects.filter(is_active=True, is_system=False).exclude(slug=''):
            path = f'team/{master.slug}'
            page = master.page or Page.objects.filter(url_path=path).first() or Page.objects.filter(
                parent=team, url=master.slug,
            ).first()
            if page and claimed_by_another(page, Master, master):
                raise CommandError(f'Страница «{path}» уже связана с другой записью.')
            before = (page.parent_id, page.url, page.content, page.url_path) if page else None
            if page is None:
                page = Page(
                    title=master.name, url=master.slug, parent=team,
                    content=format_html('<p>{}</p>', master.bio) if master.bio else '',
                )
                masters_added += 1
            else:
                page.parent = team
                page.url = master.slug
                if not page.content and master.bio:
                    page.content = format_html('<p>{}</p>', master.bio)
            if before is None or before[:3] != (page.parent_id, page.url, page.content) or page.url_path != path:
                page.save()
            if master.page_id != page.pk:
                master.page = page
                master.save(update_fields=['page'])

        categories_added = 0
        for category in ServiceCategory.objects.select_related('page').order_by('pk'):
            categories_added += category_page(category, services_root)

        services_added = 0
        for service in Service.objects.select_related('page', 'category__page').order_by('pk'):
            services_added += service_page(service)

        self.stdout.write(self.style.SUCCESS(
            f'Корневые страницы проверены; новых страниц салонов: {salons_added}; '
            f'мастеров: {masters_added}; '
            f'категорий услуг: {categories_added}; услуг: {services_added}.'
        ))
