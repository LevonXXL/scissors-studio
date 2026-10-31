"""Read the accepted edition of the two-salon SCISSORS price workbook."""

from datetime import datetime
from decimal import Decimal, InvalidOperation
from difflib import get_close_matches
from hashlib import sha256
from io import BytesIO
import re
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile

from django.db import transaction
from django.db.models import Q

from .excel_import import CATEGORIES, NS, _normal, _text, capitalize_description
from .models import Service, ServiceCategory, ServicePrice, ServiceSalon
from .price_sync import sync_offer_prices
from salons.models import Salon

REL = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'
DIRECTIONS = {
    'Волосы': 'hair',
    'Брови и ресницы': 'browlashes',
    'Ногтевой сервис': 'nails',
    'Косметология лица': 'cosmetology',
    'Кожа головы': 'cosmetology',
    'Тело и SPA': 'cosmetology',
    'Удаление волос': 'epilation',
}
HAIR_LEVELS = ('universal', 'modeler', 'stylist', 'top_stylist', 'art_director')
NAIL_LEVELS = ('nail_master', 'top_nail_master')
LEVEL_LABELS = {
    'universal': 'Универсал', 'modeler': 'Модельер', 'stylist': 'Стилист',
    'top_stylist': 'Топ-стилист', 'art_director': 'Арт-директор',
    'nail_master': 'Мастер', 'top_nail_master': 'Топ-мастер', '': 'Единая цена',
}


def _cells(row, strings):
    result = {}
    formulas = []
    for cell in row.findall(NS + 'c'):
        address = cell.get('r')
        column = re.match(r'[A-Z]+', address).group()
        result[column] = _text(cell, strings).strip()
        if cell.find(NS + 'f') is not None:
            formulas.append(address)
    return result, formulas


def _price(raw, address):
    if raw == '—':
        return {'status': 'dash', 'amount': None}
    if raw == '':
        return {'status': 'blank', 'amount': None}
    try:
        amount = Decimal(raw.replace(' ', '').replace(',', '.'))
    except InvalidOperation as exc:
        raise ValueError(f'Ячейка {address}: некорректная цена «{raw}».') from exc
    if amount < 0:
        raise ValueError(f'Ячейка {address}: цена не может быть отрицательной.')
    return {'status': 'amount', 'amount': str(amount)}


def _choose_sheet(archive, workbook, relationships, strings):
    accepted = []
    for sheet in workbook.find(NS + 'sheets'):
        name = sheet.get('name', '')
        match = re.fullmatch(r'Единый прайс (\d{2}\.\d{2}\.\d{4})(?: ред\. (\d+))?', name)
        if not match or sheet.get('state', 'visible') != 'visible':
            continue
        target = relationships[sheet.get(REL)].lstrip('/')
        path = target if target.startswith('xl/') else f'xl/{target}'
        root = ET.fromstring(archive.read(path))
        first = root.find('.//' + NS + 'sheetData/' + NS + 'row')
        cells, _ = _cells(first, strings)
        if _normal(cells.get('Y', '')) == 'принятая редакция':
            accepted.append((datetime.strptime(match.group(1), '%d.%m.%Y'), int(match.group(2) or 1), name, root))
    if not accepted:
        raise ValueError('Нет видимого листа «Единый прайс» с отметкой «Принятая редакция» в Y1.')
    accepted.sort(key=lambda item: (item[0], item[1]))
    return accepted[-1][2:]


def is_unified_workbook(data):
    if not data.startswith(b'PK'):
        return False
    try:
        with ZipFile(BytesIO(data)) as archive:
            workbook = ET.fromstring(archive.read('xl/workbook.xml'))
            return any(sheet.get('name', '').startswith('Единый прайс ')
                       for sheet in workbook.find(NS + 'sheets'))
    except (BadZipFile, KeyError, ET.ParseError, OSError):
        return False


def read_unified_xlsx(data):
    if not data.startswith(b'PK'):
        raise ValueError('Ожидается файл XLSX.')
    with ZipFile(BytesIO(data)) as archive:
        workbook = ET.fromstring(archive.read('xl/workbook.xml'))
        relationships = {
            item.get('Id'): item.get('Target')
            for item in ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))
        }
        strings = []
        if 'xl/sharedStrings.xml' in archive.namelist():
            strings = [
                ''.join(t.text or '' for t in item.iter(NS + 't'))
                for item in ET.fromstring(archive.read('xl/sharedStrings.xml'))
            ]
        sheet_name, root = _choose_sheet(archive, workbook, relationships, strings)
        excel_rows = root.findall('.//' + NS + 'sheetData/' + NS + 'row')
        header = next((row for row in excel_rows if row.get('r') == '3'), None)
        if header is None:
            raise ValueError('В принятом листе отсутствует строка заголовков 3.')
        headers, _ = _cells(header, strings)
        expected = {'A': 'Название услуги', 'B': 'Краткое описание',
                    'D': 'Универсал', 'E': 'Модельер', 'F': 'Стилист',
                    'G': 'Топ-стилист', 'H': 'Арт-директор',
                    'R': 'Код услуги', 'S': 'Направление', 'T': 'Подблок',
                    'U': 'Внутренняя категория'}
        if any(headers.get(column) != value for column, value in expected.items()):
            raise ValueError('Заголовки принятого листа не соответствуют формату единого прайса.')
        raw_rows = []
        errors = []
        for excel_row in excel_rows:
            number = int(excel_row.get('r'))
            if number <= 3:
                continue
            cells, formulas = _cells(excel_row, strings)
            if not cells.get('R'):
                continue
            if excel_row.get('hidden') == '1':
                errors.append(f'Строка {number} скрыта в Excel.')
            if formulas:
                errors.append(f'Строка {number} содержит формулы: {", ".join(formulas)}.')
            if not cells.get('A'):
                errors.append(f'Строка {number}: нет названия услуги.')
            if not cells.get('S') in DIRECTIONS:
                errors.append(f'Строка {number}: неизвестное направление «{cells.get("S", "")}».')
            raw_rows.append((number, cells))
    code_counts = {}
    name_counts = {}
    for number, cells in raw_rows:
        code_counts[cells['R']] = code_counts.get(cells['R'], 0) + 1
        name = _normal(cells.get('A', ''))
        name_counts[name] = name_counts.get(name, 0) + 1
    rows = []
    for number, cells in raw_rows:
        code = cells['R']
        if code_counts[code] > 1:
            errors.append(f'Строка {number}: код {code} повторяется.')
        direction = cells.get('S', '')
        if direction not in DIRECTIONS or not cells.get('A'):
            continue
        category = DIRECTIONS[direction]
        if category == 'hair' and re.match(r'^(Мужская стрижка|Камуфляж|Оформление бороды)', cells['A'], re.I):
            category = 'forman'
        title = cells['A']
        if name_counts[_normal(title)] > 1:
            variant = cells.get('V', '')
            if not variant:
                errors.append(f'Строка {number}: одинаковое название без различающего варианта в V.')
            else:
                title = f'{title} — {variant}'
        if category in ('hair', 'forman'):
            if cells.get('T') == 'Доплаты за Lux-бренды':
                columns = [('D', 'I')] * 5
            else:
                columns = [('D', 'I'), ('E', 'J'), ('F', 'K'), ('G', 'L'), ('H', 'M')]
            levels = HAIR_LEVELS
        elif category == 'nails':
            columns = [('D', None), ('E', None)]
            levels = NAIL_LEVELS
        elif category == 'browlashes':
            columns = [('D', None), ('E', None), ('F', None), ('G', None), ('H', None)]
            levels = HAIR_LEVELS
        else:
            columns = [('D', None)]
            levels = ('',)
        prices = {'zelenograd': [], 'moscow': []}
        for (z_column, m_column), level in zip(columns, levels):
            for city, column in (('zelenograd', z_column), ('moscow', m_column)):
                if column:
                    try:
                        price = _price(cells.get(column, ''), f'{column}{number}')
                        if price['status'] == 'amount':
                            prices[city].append({'level': level, **price})
                    except ValueError as exc:
                        errors.append(str(exc))
        duration = cells.get('N', '')
        try:
            duration_seconds = int(Decimal(duration) * 60) if duration else None
        except InvalidOperation:
            errors.append(f'Строка {number}: некорректная длительность в N.')
            duration_seconds = None
        rows.append({
            'row': number, 'price_code': code, 'title': title,
            'description': capitalize_description(cells.get('B', '')),
            'category': category, 'direction': direction, 'group': cells.get('T', ''),
            'internal_category': cells.get('U', ''), 'variant': cells.get('V', ''),
            'duration_seconds': duration_seconds, 'prices_by_city': prices,
            'work_comment': cells.get('Q', ''),
        })
    return {'kind': 'unified', 'sheet': sheet_name, 'digest': sha256(data).hexdigest(),
            'rows': rows, 'errors': errors, 'issues': [
                {'message': error, 'rows': [int(match.group(1))] if (match := re.search(r'Строка (\d+)', error)) else []}
                for error in errors
            ]}


def salons_for_unified_import():
    result = {}
    for key, query in {
        'zelenograd': Q(slug__icontains='zelenograd') | Q(name__icontains='Зеленоград'),
        'moscow': Q(slug__icontains='krasnye-vorota') | Q(name__icontains='Красные Ворота'),
    }.items():
        matches = list(Salon.objects.filter(query, is_active=True))
        if len(matches) != 1:
            raise ValueError(f'Для {key} найдено {len(matches)} активных салонов; ожидается один.')
        result[key] = matches[0]
    return result


def candidate_services(item):
    """Match by stable price code first, then by title within public categories."""
    by_code = list(Service.objects.filter(price_code=item['price_code']).select_related('category'))
    if by_code:
        return by_code
    allowed = {'hair', 'forman'} if item['category'] in ('hair', 'forman') else {item['category']}
    services = list(Service.objects.filter(category__code__in=allowed).select_related('category'))
    name = _normal(item['title'])
    exact = [service for service in services if _normal(service.title) == name]
    if exact:
        return exact
    base = [service for service in services if _normal(service.title.split(' | ')[0]) == name]
    if base:
        return base
    if item['price_code'] == 'H-044':
        return [service for service in services
                if _normal(service.title) == _normal('Экспресс коррекция Желтого')]
    return []


def suggested_services(item):
    exact = candidate_services(item)
    if exact:
        return exact
    allowed = {'hair', 'forman'} if item['category'] in ('hair', 'forman') else {item['category']}
    services = list(Service.objects.filter(category__code__in=allowed).select_related('category'))
    names = {service.title: service for service in services}
    close = get_close_matches(item['title'], names, n=5, cutoff=0.4)
    return [names[name] for name in close]


def resolve_unified_match(item, choice, automatic=None):
    """Return the selected service and a user-facing matching error, if any."""
    automatic = candidate_services(item) if automatic is None else automatic
    if choice == 'new':
        if automatic:
            return None, 'Услуга уже найдена; выберите её вместо создания новой.'
        return None, None
    if choice:
        if not str(choice).isdigit():
            return None, 'Некорректное сопоставление.'
        service = Service.objects.select_related('category').filter(pk=int(choice)).first()
        if service is None:
            return None, 'Выбранная услуга больше не существует.'
    elif len(automatic) == 1:
        service = automatic[0]
    elif len(automatic) > 1:
        return None, 'Найдено несколько услуг; выберите нужную.'
    else:
        return None, 'Выберите существующую услугу или «Создать новую».'
    category_code = item['category']
    if category_code in ('hair', 'forman') and service.category.code in ('hair', 'forman'):
        category_code = service.category.code
    if service.category.code != category_code:
        return None, 'Категория выбранной услуги не совпадает с направлением прайса.'
    if service.price_code and service.price_code != item['price_code']:
        return None, 'Выбранная услуга уже связана с другим кодом прайса.'
    return service, None


def describe_unified_details(item, service, salons):
    if service is None:
        return ['Создать новую услугу и цены по представленным салонам.']
    details = []
    for field, new, label in (
        ('title', item['title'], 'Название'),
        ('price_code', item['price_code'], 'Код прайса'),
        ('description', item['description'], 'Описание'),
        ('group_title', item['group'], 'Раздел'),
        ('price_internal_category', item['internal_category'], 'Внутренняя категория'),
    ):
        old = getattr(service, field)
        if old != new:
            details.append(f'{label}: {old or "—"} → {new or "—"}')
    existing = {}
    for price in ServicePrice.objects.filter(salon_service__service=service).select_related('salon_service'):
        existing[(price.salon_service.salon_id, price.level)] = price
    for city, salon in salons.items():
        for source in item['prices_by_city'][city]:
            old = existing.get((salon.pk, source['level']))
            amount = Decimal(source['amount']) if source['amount'] is not None else None
            if old is None or old.amount != amount:
                old_label = 'нет' if old is None else f'{old.amount} ₽'
                new_label = f'{amount} ₽'
                details.append(f'{salon.name}, {LEVEL_LABELS[source["level"]]}: {old_label} → {new_label}')
        source_levels = {source['level'] for source in item['prices_by_city'][city]}
        for (salon_id, level), old in existing.items():
            if salon_id == salon.pk and level not in source_levels:
                details.append(f'{salon.name}, {LEVEL_LABELS.get(level, level)}: {old.amount} ₽ → нет')
    return details or ['Без изменений']


def _selected_items(preview, selected_rows):
    available = {item['row']: item for item in preview['rows']}
    selected = {int(row) for row in selected_rows}
    if not selected or not selected <= available.keys():
        raise ValueError('Отметьте существующие строки прайса для применения.')
    errors = [issue['message'] for issue in preview['issues']
              if not issue['rows'] or selected.intersection(issue['rows'])]
    if errors:
        raise ValueError('Ошибки выбранных строк: ' + '; '.join(errors[:3]))
    return [available[row] for row in sorted(selected)]


@transaction.atomic
def apply_unified_preview(preview, matches, selected_rows):
    """Update both salons together; preserve editorial pages and staff assignments."""
    items = _selected_items(preview, selected_rows)
    salons = salons_for_unified_import()
    categories = {}
    touched = []
    used_services = set()
    changed = 0
    for item in items:
        choice = matches.get(str(item['row']), '')
        service, issue = resolve_unified_match(item, choice)
        if issue:
            raise ValueError(f'Строка {item["row"]}: {issue}')
        category_code = item['category']
        if service and category_code in ('hair', 'forman') and service.category.code in ('hair', 'forman'):
            category_code = service.category.code
        if service and service.pk in used_services:
            raise ValueError(f'Строка {item["row"]}: услуга сопоставлена с несколькими строками.')
        if category_code not in categories:
            title, image = CATEGORIES[category_code]
            category, _ = ServiceCategory.objects.get_or_create(
                code=category_code,
                defaults={'title': title, 'image_path': image,
                          'is_active': True, 'weight': list(CATEGORIES).index(category_code)},
            )
            categories[category_code] = category
        category = categories[category_code]
        if service is None:
            stable_code = f'{category_code}-{sha256(item["price_code"].encode()).hexdigest()[:16]}'
            service = Service(category=category, code=stable_code, title=item['title'])
        updates = {
            'price_code': item['price_code'], 'title': item['title'],
            'description': item['description'], 'group_title': item['group'],
            'price_internal_category': item['internal_category'], 'weight': item['row'],
        }
        if item['duration_seconds'] is not None:
            updates['duration_seconds'] = item['duration_seconds']
        if service.pk and not service.is_active:
            updates = {'price_code': item['price_code'],
                       'price_internal_category': item['internal_category']}
        dirty = not service.pk
        for field, value in updates.items():
            if getattr(service, field) != value:
                setattr(service, field, value)
                dirty = True
        if dirty:
            service.save()
            changed += 1
        touched.append(service)
        used_services.add(service.pk)
        for city, salon in salons.items():
            city_prices = item['prices_by_city'][city]
            if not city_prices:
                offer = ServiceSalon.objects.filter(service=service, salon=salon).first()
                if offer:
                    changed += sync_offer_prices(offer, [])
                    if offer.is_active:
                        offer.is_active = False
                        offer.save(update_fields=['is_active'])
                        changed += 1
                continue
            offer, created = ServiceSalon.objects.get_or_create(
                service=service, salon=salon,
                defaults={'position': item['row'], 'is_active': service.is_active},
            )
            if created:
                changed += 1
            elif offer.position != item['row'] or (service.is_active and not offer.is_active):
                offer.position = item['row']
                if service.is_active:
                    offer.is_active = True
                offer.save(update_fields=['position', 'is_active'])
                changed += 1
            if category_code == 'browlashes':
                old_fixed = offer.prices.filter(level='')
                if old_fixed.exists():
                    if offer.prices.filter(level='modeler').exists():
                        changed += old_fixed.count()
                        old_fixed.delete()
                    else:
                        changed += old_fixed.update(level='modeler')
            changed += sync_offer_prices(offer, city_prices)
    from .catalog_pages import ensure_catalog_pages
    ensure_catalog_pages(categories.values(), touched)
    return changed
