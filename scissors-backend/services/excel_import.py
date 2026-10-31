"""Read-only XLSX parsing and explicit application of an approved price preview."""
from decimal import Decimal, InvalidOperation
from difflib import get_close_matches
from hashlib import sha256
from io import BytesIO
import re
import unicodedata
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from django.db import transaction

from .models import Service, ServiceCategory, ServicePrice, ServiceSalon
from .price_sync import sync_offer_prices

NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
LEVELS = {
    'hair': [('B', 'universal'), ('C', 'modeler'), ('D', 'stylist'), ('E', 'top_stylist'), ('F', 'art_director')],
    'nails': [('B', 'nail_master'), ('C', 'top_nail_master')],
    'fixed': [('C', '')],
}
LABELS = dict((key, label) for key, label in [
    ('universal', 'Универсал'), ('modeler', 'Модельер'), ('stylist', 'Стилист'),
    ('top_stylist', 'Топ-стилист'), ('art_director', 'Арт-директор'),
    ('nail_master', 'Мастер'), ('top_nail_master', 'Топ-мастер'), ('', 'Единая цена'),
])
CATEGORIES = {
    'hair': ('Для волос', '/img/home/service-hair.png'),
    'nails': ('Для ногтей', '/img/home/service-nails.png'),
    'browlashes': ('Брови и ресницы', '/img/home/service-brows.png'),
    'cosmetology': ('Косметология', '/img/home/service-cosmetology.png'),
    'epilation': ('Эпиляция', '/img/home/service-epilation.png'),
    'forman': ('Для мужчин', '/img/home/service-men.png'),
}


def _text(cell, strings):
    value = cell.find(NS + 'v')
    if value is not None:
        return strings[int(value.text)] if cell.get('t') == 's' else value.text or ''
    inline = cell.find(NS + 'is')
    return ''.join(t.text or '' for t in inline.iter(NS + 't')) if inline is not None else ''


def _normal(value):
    return ' '.join(unicodedata.normalize('NFKC', value).casefold().split())


def capitalize_description(value):
    """Uppercase the first letter without changing brand names later in the text."""
    if value is None:
        return None
    for index, char in enumerate(value):
        if char.isalpha():
            return value[:index] + char.upper() + value[index + 1:]
    return value


def salon_matches_city(preview, salon):
    name = salon.name.casefold()
    city = ('zelenograd' if 'зеленоград' in name else
            'moscow' if 'моск' in name or 'красные' in name else None)
    return not preview['city'] or city == preview['city']


def validate_salon(preview, salon):
    if ('krasnye-vorota' in (salon.slug or '') or 'красные ворота' in salon.name.casefold()) and any(
        item['category'] not in ('hair', 'forman') for item in preview['rows']
    ):
        raise ValueError('В салоне «Красные Ворота» доступен только парикмахерский зал.')


def read_xlsx(data):
    if not data.startswith(b'PK'):
        raise ValueError('Ожидается файл XLSX.')
    with ZipFile(BytesIO(data)) as archive:
        names = archive.namelist()
        if 'xl/workbook.xml' not in names:
            raise ValueError('В файле нет книги Excel.')
        book = ET.fromstring(archive.read('xl/workbook.xml'))
        sheets = book.find(NS + 'sheets')
        if len(sheets) != 1 or sheets[0].get('state', 'visible') != 'visible':
            raise ValueError('Ожидается один видимый лист; выберите и подготовьте лист вручную.')
        rel_root = ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))
        rels = {item.get('Id'): item.get('Target') for item in rel_root}
        sheet_rel = sheets[0].get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
        target = rels[sheet_rel].lstrip('/')
        sheet_path = target if target.startswith('xl/') else 'xl/' + target
        strings = []
        if 'xl/sharedStrings.xml' in names:
            strings = [''.join(t.text or '' for t in item.iter(NS + 't'))
                       for item in ET.fromstring(archive.read('xl/sharedStrings.xml'))]
        sheet = ET.fromstring(archive.read(sheet_path))
        merges = {m.get('ref').split(':')[0] for m in sheet.findall('.//' + NS + 'mergeCell')}
        rows = []
        formula_errors = []
        for row in sheet.findall('.//' + NS + 'sheetData/' + NS + 'row'):
            cells = {}
            for cell in row.findall(NS + 'c'):
                ref = cell.get('r')
                cells[re.match(r'[A-Z]+', ref).group()] = _text(cell, strings).strip()
                if cell.find(NS + 'f') is not None:
                    formula_errors.append((int(row.get('r')),
                                           f'Ячейка {ref} содержит формулу; сохраните рассчитанное значение как число или текст.'))
            rows.append({'number': int(row.get('r')), 'cells': cells,
                         'hidden': row.get('hidden') == '1'})
        comments = []
        for name in names:
            if re.match(r'xl/comments\d*\.xml$', name):
                root = ET.fromstring(archive.read(name))
                comments += [''.join(t.text or '' for t in item.iter(NS + 't'))
                             for item in root.findall('.//' + NS + 'comment')]
    if len(rows) < 5:
        raise ValueError('Лист не содержит прайса.')
    header_index = None
    kind = None
    for index, row in enumerate(rows[:20]):
        header = {_normal(v) for v in row['cells'].values()}
        if {'универсал', 'модельер', 'стилист', 'топ-стилист', 'арт-директор'} <= header:
            kind, header_index = 'hair', index
        elif {'мастер', 'топ-мастер'} <= header:
            kind, header_index = 'nails', index
        elif {'название услуги', 'описание', 'цена', 'время'} <= header:
            kind, header_index = 'fixed', index
        if kind:
            break
    if kind is None:
        raise ValueError('Не найдены известные заголовки уровней или цены в первых 20 строках.')
    header_cells = {_normal(value): column for column, value in rows[header_index]['cells'].items()}
    title_column = header_cells.get('название услуги', 'A')
    level_columns = ([(header_cells[LABELS[level].casefold()], level) for _, level in LEVELS[kind]]
                     if kind != 'fixed' else [(header_cells['цена'], '')])
    description_column = header_cells.get('описание')
    duration_column = header_cells.get('время', 'D')

    evidence = ' '.join([sheets[0].get('name', '')] +
                        [v for row in rows for v in row['cells'].values()] + comments)
    cities = set()
    if re.search('зеленоград', evidence, re.I):
        cities.add('zelenograd')
    if re.search(r'москва|красные ворота', evidence, re.I):
        cities.add('moscow')
    city = next(iter(cities)) if len(cities) == 1 else None

    parsed = []
    errors = []
    issues = []

    def add_error(message, affected_rows):
        errors.append(message)
        issues.append({'message': message, 'rows': list(affected_rows)})

    for error_row, message in formula_errors:
        add_error(message, [error_row])
    group = ''
    subgroup = ''
    section_rows = []
    for row in rows[header_index + 1:]:
        number, cells = row['number'], row['cells']
        title = cells.get(title_column, '')
        if row['hidden']:
            add_error(f'Строка {number} скрыта в Excel; подтвердите, следует ли её импортировать.', [number])
            continue
        if not title:
            continue
        values = [cells.get(col, '') for col, _ in level_columns]
        if title and re.match(r'^\d{2}\s*[·.]', title) and not any(values):
            group = re.sub(r'^\d{2}\s*[·.]\s*', '', title).strip()
            subgroup, section_rows = '', []
            continue
        if f'{title_column}{number}' in merges and not any(values):
            if re.search(r'\+\s*\d|%|оплач|доплат|только вместе|такси|не выполня', title, re.I):
                for item in section_rows:
                    item['conditions'] = '\n'.join(filter(None, [item['conditions'], title]))
            else:
                subgroup = title
            continue
        if not any(values):
            add_error(f'Строка {number}: текст без цен и без объединения — требуется классификация: {title[:100]}', [number])
            continue
        prices = []
        for col, level in level_columns:
            raw = cells.get(col, '')
            if raw == '—':
                status, amount = 'dash', None
            elif raw == '':
                status, amount = 'blank', None
            else:
                try:
                    amount = Decimal(raw.replace(' ', '').replace(',', '.'))
                    status = 'amount'
                except InvalidOperation:
                    add_error(f'Строка {number}, {col}: непонятная цена «{raw}».', [number])
                    continue
            prices.append({'level': level, 'status': status, 'amount': str(amount) if amount is not None else None})
        if kind == 'fixed':
            group_name = _normal(group)
            category_code = ('epilation' if 'удаление волос' in group_name else
                             'browlashes' if 'бров' in group_name or 'ресниц' in group_name else
                             'cosmetology')
            if category_code == 'browlashes':
                for price in prices:
                    price['level'] = 'modeler'
            description = capitalize_description(cells.get(description_column, '')) if description_column else None
            duration = cells.get(duration_column, '')
            try:
                duration_seconds = int(Decimal(duration) * 60)
            except (InvalidOperation, ValueError):
                add_error(f'Строка {number}, {duration_column}: непонятная длительность «{duration}».', [number])
                duration_seconds = None
        else:
            category_code = ('forman' if kind == 'hair' and re.match(
                r'^(Мужская стрижка|Камуфляж|Оформление бороды)', title, re.I) else kind)
            description = capitalize_description(cells.get(description_column, '')) if description_column else None
            duration_seconds = None
        item = dict(row=number, category=category_code, group=group, subgroup=subgroup,
                    title=title, description=description, duration_seconds=duration_seconds,
                    conditions='', prices=prices)
        parsed.append(item)
        section_rows.append(item)
    seen = {}
    for item in parsed:
        key = (item['category'], _normal(item['title']))
        if key in seen:
            add_error(f'Строки {seen[key]} и {item["row"]}: одинаковое название в одной категории; требуется различить варианты.',
                      [seen[key], item['row']])
        else:
            seen[key] = item['row']
    return {'kind': kind, 'city': city, 'city_evidence': sorted(cities), 'rows': parsed,
            'errors': errors, 'issues': issues, 'digest': sha256(data).hexdigest()}


def blocking_errors(preview, selected_rows=None):
    if selected_rows is None:
        return preview['errors']
    selected = set(selected_rows)
    return [issue['message'] for issue in preview.get('issues', [])
            if not issue['rows'] or selected.intersection(issue['rows'])]


def candidates(item):
    category = ServiceCategory.objects.filter(code=item['category']).first()
    if not category:
        return []
    return list(Service.objects.filter(category=category, title__iexact=item['title']).values('id', 'title'))


def preview_candidates(item):
    exact = candidates(item)
    if exact:
        return exact
    category = ServiceCategory.objects.filter(code=item['category']).first()
    if not category:
        return []
    entries = list(Service.objects.filter(category=category).values('id', 'title'))
    names = get_close_matches(item['title'], [entry['title'] for entry in entries], n=8, cutoff=0.45)
    return [entry for entry in entries if entry['title'] in names]


def describe_change(item, salon, matched_id=None):
    if matched_id:
        service = Service.objects.get(pk=matched_id, category__code=item['category'])
    else:
        exact = candidates(item)
        if len(exact) > 1:
            return 'Неоднозначно: несколько услуг с этим названием'
        if not exact:
            return 'Создать услугу, назначение салону и цены'
        service = Service.objects.get(pk=exact[0]['id'])
    offer = ServiceSalon.objects.filter(service=service, salon=salon).first()
    if not offer:
        return 'Добавить услугу в салон и установить цены'
    changed = any(item[value] is not None and (value != 'conditions' or item[value]) and
                  getattr(service, field) != item[value] for field, value in [
        ('title', 'title'),
        ('description', 'description'), ('duration_seconds', 'duration_seconds'),
        ('group_title', 'group'), ('subgroup_title', 'subgroup'),
        ('conditions', 'conditions'), ('weight', 'row'),
    ]) or offer.position != item['row'] or not offer.is_active
    old_prices = {price.level: price for price in offer.prices.all()}
    source_prices = {price['level']: Decimal(price['amount']) for price in item['prices']
                     if price['status'] == 'amount'}
    if set(old_prices) != set(source_prices):
        changed = True
    for level, amount in source_prices.items():
        old = old_prices.get(level)
        if old is None or old.amount != amount:
            changed = True
    return 'Обновить импортируемые поля/цены' if changed else 'Без изменений'


def describe_details(item, salon, matched_id=None):
    """Human-readable differences for a single Excel row and selected salon."""
    if matched_id:
        service = Service.objects.get(pk=int(matched_id), category__code=item['category'])
    else:
        exact = candidates(item)
        if len(exact) > 1:
            return ['Несколько услуг с таким названием: выберите соответствие.']
        service = Service.objects.get(pk=exact[0]['id']) if exact else None
    if service is None:
        return ['Новая общая услуга', 'Новая цена для выбранного салона']
    details = []
    for field, value, label in [
        ('title', 'title', 'Название'), ('description', 'description', 'Описание'),
        ('duration_seconds', 'duration_seconds', 'Длительность'),
        ('group_title', 'group', 'Раздел'), ('subgroup_title', 'subgroup', 'Подгруппа'),
        ('conditions', 'conditions', 'Условия'), ('weight', 'row', 'Порядок'),
    ]:
        new = item[value]
        old = getattr(service, field)
        if new is not None and (value != 'conditions' or new) and old != new:
            details.append(f'{label}: {old or "—"} → {new or "—"}')
    offer = ServiceSalon.objects.filter(service=service, salon=salon).first()
    if offer is None:
        details.append('Добавить услугу в выбранный салон')
        old_prices = {}
    else:
        if not offer.is_active:
            details.append('Сделать услугу доступной в выбранном салоне')
        if offer.position != item['row']:
            details.append(f'Порядок в салоне: {offer.position} → {item["row"]}')
        old_prices = {price.level: price for price in offer.prices.all()}
    source_prices = {price['level']: Decimal(price['amount']) for price in item['prices']
                     if price['status'] == 'amount'}
    for level, amount in source_prices.items():
        old = old_prices.get(level)
        if old is None or old.amount != amount:
            details.append(f'{LABELS[level]}: {old.amount if old else "нет"} → {amount} ₽')
    for level, old in old_prices.items():
        if level not in source_prices:
            details.append(f'{LABELS[level]}: {old.amount} ₽ → нет')
    return details or ['Без изменений']


@transaction.atomic
def apply_preview(preview, salon, matches, selected_rows=None):
    """Only Excel-owned fields are updated. Assignments and Page copy are untouched."""
    available_rows = {item['row'] for item in preview['rows']}
    if selected_rows is not None:
        selected_rows = {int(row) for row in selected_rows}
        if not selected_rows <= available_rows:
            raise ValueError('Выбрана строка, которой нет в загруженном файле.')
    errors = blocking_errors(preview, selected_rows)
    if errors:
        raise ValueError('Ошибки выбранных строк: ' + '; '.join(errors[:3]))
    validate_salon(preview, salon)
    changed = 0
    categories = {}
    used_service_ids = set()
    applied_services = []
    for item in preview['rows']:
        if selected_rows is not None and item['row'] not in selected_rows:
            continue
        code = item['category']
        if code not in categories:
            title, image = CATEGORIES[code]
            category, _ = ServiceCategory.objects.get_or_create(code=code, defaults={
                'title': title, 'image_path': image, 'is_active': True,
                'weight': list(CATEGORIES).index(code),
            })
            if not category.image_path:
                category.image_path = image
                category.save(update_fields=['image_path'])
            categories[code] = category
        category = categories[code]
        selected = matches.get(str(item['row']))
        if selected:
            service = Service.objects.get(pk=int(selected), category=category)
        else:
            existing = candidates(item)
            if len(existing) > 1:
                raise ValueError(f'Строка {item["row"]}: несколько совпадений, выберите услугу вручную.')
            service = Service.objects.get(pk=existing[0]['id']) if existing else Service(
                category=category, title=item['title'],
                code=f'{code}-{sha256(_normal(item["title"]).encode()).hexdigest()[:16]}',
            )
        if service.pk and service.pk in used_service_ids:
            raise ValueError(f'Строка {item["row"]}: одна услуга сопоставлена с несколькими строками.')
        if service.pk:
            used_service_ids.add(service.pk)
        updates = {
            'title': item['title'],
            'group_title': item['group'], 'subgroup_title': item['subgroup'],
            'weight': item['row'],
        }
        if item.get('price_code'):
            updates['price_code'] = item['price_code']
        if item['description'] is not None:
            updates['description'] = item['description']
        if item['duration_seconds'] is not None:
            updates['duration_seconds'] = item['duration_seconds']
        if item['conditions']:
            updates['conditions'] = item['conditions']
        dirty = not service.pk
        for key, value in updates.items():
            if getattr(service, key) != value:
                setattr(service, key, value)
                dirty = True
        if dirty:
            service.save()
            changed += 1
        used_service_ids.add(service.pk)
        applied_services.append(service)
        offer, made = ServiceSalon.objects.get_or_create(service=service, salon=salon,
                                                        defaults={'position': item['row']})
        if not made and (offer.position != item['row'] or not offer.is_active):
            offer.position = item['row']
            offer.is_active = True
            offer.save(update_fields=['position', 'is_active'])
            changed += 1
        changed += sync_offer_prices(offer, item['prices'])
    from .catalog_pages import ensure_catalog_pages
    ensure_catalog_pages(categories.values(), applied_services)
    return changed
