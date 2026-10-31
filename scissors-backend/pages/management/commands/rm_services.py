from collections import Counter

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django.utils.text import slugify

from pages.models import Page


LEGACY_ROOT = "services"
NEW_ROOT = "uslugi"

# Эти связи будут перенесены на новые страницы, а не удалены.
CATALOG_RELATIONS = {
    ("services.Service", "page"),
    ("services.ServiceCategory", "page"),
}

# Переносим только незаполненные редакционные поля:
# существующий контент целевой страницы имеет приоритет.
CONTENT_FIELDS = (
    "content",
    "meta_title",
    "meta_description",
    "description",
    "h1",
)


class Command(BaseCommand):
    help = (
        "Переносит страницы услуг из services в uslugi, "
        "перепривязывает каталог и удаляет старое дерево."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Выполнить перенос и удаление.",
        )

    def models(self):
        return (
            apps.get_model("services", "Service"),
            apps.get_model("services", "ServiceCategory"),
        )

    def get_legacy_pages(self):
        """
        Находит старую ветку по url_path и дополнительно
        собирает потомков через parent, не полагаясь на MPTT.
        """
        pages = Page.objects.filter(
            Q(url_path=LEGACY_ROOT)
            | Q(url_path__startswith=f"{LEGACY_ROOT}/")
        )

        page_ids = set(pages.values_list("pk", flat=True))
        frontier = set(page_ids)

        while frontier:
            children = set(
                Page.objects.filter(parent_id__in=frontier)
                .exclude(pk__in=page_ids)
                .values_list("pk", flat=True)
            )
            page_ids.update(children)
            frontier = children

        return Page.objects.filter(pk__in=page_ids).order_by("pk")

    def get_uslugi_root(self):
        root = Page.objects.filter(url_path=NEW_ROOT).first()

        if root is None:
            root = Page.objects.filter(
                parent__isnull=True,
                url=NEW_ROOT,
            ).first()

        if root is None:
            raise CommandError(
                "Не найдена корневая Page /uslugi. "
                "Создай её перед переносом."
            )

        return root

    @staticmethod
    def is_under_root(page, root):
        """Проверяет реальную цепочку parent, а не сохранённый путь."""
        current = page

        while current is not None:
            if current.pk == root.pk:
                return page.pk != root.pk

            current = current.parent

        return False

    @staticmethod
    def copy_missing_content(source, target):
        """
        Переносит SEO-текст из старой страницы только в пустые поля.
        Названия, URL и уже заполненный целевой контент не затирает.
        """
        changed = []

        for field_name in CONTENT_FIELDS:
            field_names = {
                field.name for field in target._meta.concrete_fields
            }

            if field_name not in field_names:
                continue

            if field_name not in {
                field.name for field in source._meta.concrete_fields
            }:
                continue

            old_value = getattr(source, field_name, None)
            new_value = getattr(target, field_name, None)

            if old_value and not new_value:
                setattr(target, field_name, old_value)
                changed.append(field_name)

        if changed:
            target.save(update_fields=changed)

    def create_page(self, parent, url, title, source=None):
        fields = {
            field.name
            for field in Page._meta.concrete_fields
        }

        kwargs = {
            "parent": parent,
            "url": url,
        }

        if "title" in fields:
            kwargs["title"] = title

        if source is not None:
            for name in CONTENT_FIELDS:
                if name in fields and name in {
                    field.name
                    for field in source._meta.concrete_fields
                }:
                    kwargs[name] = getattr(source, name, None)

        return Page.objects.create(**kwargs)

    def ensure_category_page(
        self, category, root, legacy_ids, ServiceCategory
    ):
        """
        Находит или создаёт страницу категории непосредственно
        под /uslugi и обновляет ServiceCategory.page.
        """
        old_page = category.page

        if (
            old_page is not None
            and old_page.pk not in legacy_ids
            and self.is_under_root(old_page, root)
        ):
            return old_page

        code = getattr(category, "code", None)
        title = getattr(category, "title", None) or str(category)
        base_slug = slugify(code or title) or f"category-{category.pk}"

        slug = base_slug

        while True:
            target = Page.objects.filter(
                parent_id=root.pk,
                url=slug,
            ).first()

            if target is None:
                break

            used_by_another_category = (
                ServiceCategory.objects.filter(page_id=target.pk)
                .exclude(pk=category.pk)
                .exists()
            )

            if not used_by_another_category:
                break

            slug = f"{base_slug}-{category.pk}"

        if target is None:
            target = self.create_page(
                root,
                slug,
                title,
                source=old_page,
            )
        elif old_page is not None:
            self.copy_missing_content(old_page, target)

        if category.page_id != target.pk:
            category.page = target
            category.save(update_fields=["page"])

        return target

    def ensure_service_page(
        self, service, source, category_page, legacy_ids, Service
    ):
        """
        Находит или создаёт страницу услуги внутри страницы категории.
        Сама запись Service и её цены остаются прежними.
        """
        base_slug = (
            getattr(source, "url", None)
            or slugify(service.title)
            or f"service-{service.pk}"
        )

        slug = base_slug

        while True:
            target = Page.objects.filter(
                parent_id=category_page.pk,
                url=slug,
            ).first()

            if target is None:
                break

            # Не присваиваем страницу, уже занятую другой услугой.
            used_by_another_service = (
                Service.objects.filter(page_id=target.pk)
                .exclude(pk=service.pk)
                .exists()
            )

            if not used_by_another_service:
                break

            slug = f"{base_slug}-{service.pk}"

        if target is None:
            title = (
                getattr(source, "title", None)
                or service.title
            )
            target = self.create_page(
                category_page,
                slug,
                title,
                source=source,
            )
        else:
            self.copy_missing_content(source, target)

        if service.page_id != target.pk:
            service.page = target
            service.save(update_fields=["page"])

        return target

    def find_external_references(self, pages):
        """
        Ищет ссылки на удаляемые страницы, кроме двух связей каталога,
        которые команда должна предварительно перепривязать.
        """
        page_ids = list(pages.values_list("pk", flat=True))
        references = []

        external_children = (
            Page.objects.exclude(pk__in=page_ids)
            .filter(parent_id__in=page_ids)
            .count()
        )

        if external_children:
            references.append(
                (
                    "pages.Page",
                    "parent",
                    external_children,
                )
            )

        for relation in Page._meta.related_objects:
            model = relation.related_model
            field = relation.field

            if model is Page:
                continue

            key = (model._meta.label, field.name)

            if key in CATALOG_RELATIONS:
                continue

            count = (
                model._base_manager.filter(
                    **{f"{field.name}__in": page_ids}
                )
                .distinct()
                .count()
            )

            if count:
                references.append(
                    (model._meta.label, field.name, count)
                )

        return references

    def show_references(self, references):
        for model, field, count in references:
            self.stdout.write(
                self.style.ERROR(
                    f"  {model}.{field}: {count}"
                )
            )

    def handle(self, *args, **options):
        apply = options["apply"]
        Service, ServiceCategory = self.models()

        if apply:
            # Восстанавливаем MPTT перед изменением дерева.
            with transaction.atomic():
                Page.objects.rebuild()
                self.apply_migration(Service, ServiceCategory)
            return

        # Режим предварительного просмотра ничего не изменяет.
        pages = self.get_legacy_pages()

        if not pages.exists():
            self.stdout.write(
                self.style.WARNING("Старая ветка services не найдена.")
            )
            return

        root = self.get_uslugi_root()
        page_ids = list(pages.values_list("pk", flat=True))

        services = Service.objects.filter(
            page_id__in=page_ids
        ).select_related("category")

        categories = ServiceCategory.objects.filter(
            page_id__in=page_ids
        )

        self.stdout.write("Предварительный план переноса:")
        self.stdout.write(f"  Старая ветка Page: {len(page_ids)}")
        self.stdout.write(
            f"  Услуги с привязкой к старым страницам: {services.count()}"
        )
        self.stdout.write(
            f"  Категории со ссылкой на старые страницы: "
            f"{categories.count()}"
        )
        self.stdout.write(f"  Новая корневая страница: #{root.pk} /uslugi")

        actions = Counter()

        for service in services:
            source = service.page
            category_page = service.category.page

            if (
                category_page is not None
                and category_page.pk not in page_ids
                and self.is_under_root(category_page, root)
            ):
                target = Page.objects.filter(
                    parent_id=category_page.pk,
                    url=source.url,
                ).first()

                actions["переиспользовать страницу услуги" if target else
                        "создать страницу услуги"] += 1
            else:
                actions["нужна страница категории под /uslugi"] += 1
                actions["нужна новая страница услуги"] += 1

        for action, count in actions.items():
            self.stdout.write(f"  {action}: {count}")

        references = self.find_external_references(pages)

        if references:
            self.stdout.write(
                self.style.ERROR(
                    "\nОбнаружены дополнительные ссылки, "
                    "не относящиеся к каталогу:"
                )
            )
            self.show_references(references)
            raise CommandError(
                "Сначала нужно разобрать дополнительные ссылки."
            )

        self.stdout.write(
            self.style.WARNING(
                "\nПредпросмотр завершён. Данные не изменены."
            )
        )
        self.stdout.write(
            "Для переноса страниц и удаления старой ветки "
            "запусти команду с --apply."
        )

    def apply_migration(self, Service, ServiceCategory):
        pages = self.get_legacy_pages()

        if not pages.exists():
            self.stdout.write(
                self.style.WARNING("Ветка services уже отсутствует.")
            )
            return

        root = self.get_uslugi_root()
        page_ids = set(pages.values_list("pk", flat=True))

        # Сохраняем контент старой корневой страницы, если целевая пустая.
        old_root = pages.filter(url_path=LEGACY_ROOT).first()
        if old_root is not None:
            self.copy_missing_content(old_root, root)

        services = list(
            Service.objects.filter(
                page_id__in=page_ids
            ).select_related("category")
        )

        categories = list(
            ServiceCategory.objects.filter(page_id__in=page_ids)
        )

        # Сначала переносим ссылки категорий, если они есть.
        for category in categories:
            self.ensure_category_page(
                category,
                root,
                page_ids,
                ServiceCategory,
            )

        # Затем обеспечиваем страницы категорий для всех услуг
        # из старого дерева и перепривязываем Service.page.
        migrated = 0
        created_or_reused_pages = set()

        for service in services:
            source = Page.objects.get(pk=service.page_id)

            category_page = self.ensure_category_page(
                service.category,
                root,
                page_ids,
                ServiceCategory,
            )

            target = self.ensure_service_page(
                service,
                source,
                category_page,
                page_ids,
                Service,
            )

            created_or_reused_pages.add(target.pk)
            migrated += 1

        # Все ссылки каталога должны уже указывать на новые страницы.
        still_linked = Service.objects.filter(
            page_id__in=page_ids
        ).count()

        category_links = ServiceCategory.objects.filter(
            page_id__in=page_ids
        ).count()

        if still_linked or category_links:
            raise CommandError(
                "Не все ссылки каталога перенесены: "
                f"услуги={still_linked}, категории={category_links}. "
                "Транзакция будет отменена."
            )

        references = self.find_external_references(pages)

        if references:
            self.show_references(references)
            raise CommandError(
                "На старое дерево всё ещё ссылаются другие записи. "
                "Транзакция будет отменена."
            )

        # Удаляем только старые страницы. Услуги, категории, цены
        # и назначения мастеров уже перепривязаны и остаются в БД.
        deleted_count, details = pages.delete()

        Page.objects.rebuild()

        if not Page.objects.filter(url_path=NEW_ROOT).exists():
            raise CommandError(
                "После удаления не найдена страница /uslugi. "
                "Транзакция будет отменена."
            )

        self.stdout.write(self.style.SUCCESS("\nПеренос завершён."))
        self.stdout.write(f"  Перепривязано услуг: {migrated}")
        self.stdout.write(
            f"  Новых/переиспользованных страниц услуг: "
            f"{len(created_or_reused_pages)}"
        )
        self.stdout.write(f"  Удалено страниц старого дерева: {deleted_count}")

        for model, count in details.items():
            self.stdout.write(f"  {model}: {count}")

        self.stdout.write("  Каталог Service и цены не удалялись.")
        self.stdout.write("  Корневая страница /uslugi сохранена.")
