"""Conservative matches from the downloaded Tilda service cards to the Excel catalogue."""

import json
import re
import unicodedata
from pathlib import Path


MANIFEST = Path(__file__).with_name('tilda_service_images.json')

# Background images of the six linked category cards in index__66e40b94.html.
# The names in tilda_assets are opaque, so keep the verified link → file map.
CATEGORY_IMAGES = {
    'hair': 'tild3631-6361-4436-a432-623262326339/Frame_137.png',
    'nails': 'tild3761-3237-4434-a530-623537343833/Frame_1000005494.png',
    'cosmetology': 'tild3731-6565-4131-a135-353739646364/Frame_1000005497.png',
    'epilation': 'tild3639-6430-4335-b533-343830663931/Frame_137.png',
    'forman': 'tild3362-6639-4332-b630-333334336434/Frame_1000005496.png',
    'browlashes': 'tild3863-6635-4931-a164-646439316633/Frame_1000005495.png',
}

# The nails page uses photos for groups of services, not individual Excel rows.
NAIL_GROUP_IMAGES = {
    'Маникюр': 'Маникюр',
    'Комплексы для рук': 'Комплекс Маникюр +  покрытие лаком или PLEX',
    'Покрытие и снятие': 'Покрытие и снятие',
    'Ремонт и укрепление': 'Ремонт и укрепление',
    'Дизайн': 'Дизайн',
    'Уход для рук и ног': 'Питание и уход',
    'Педикюр': 'Педикюр',
    'Подотерапия': 'Подология',
}


def normalize(value):
    value = unicodedata.normalize('NFKC', value).casefold().replace('ё', 'е')
    return re.sub(r'[^a-zа-я0-9]+', ' ', value).strip()


def load_images():
    entries = json.loads(MANIFEST.read_text(encoding='utf-8'))['images']
    result = {code: [] for code in ('hair', 'forman', 'nails', 'browlashes', 'cosmetology', 'epilation')}
    for entry in entries:
        result.setdefault(entry['category'], []).append({**entry, 'normalized': normalize(entry['title'])})
    return result


def nail_group_card(group_title, images):
    old_title = NAIL_GROUP_IMAGES.get(group_title)
    if old_title:
        return next((card for card in images.get('nails', [])
                     if card['normalized'] == normalize(old_title)), None)
    return None


def old_nail_service_card(service, images):
    """Identify photos previously copied from a Tilda group to every service."""
    group = normalize(service.group_title)
    old_group = {normalize(name): old for name, old in NAIL_GROUP_IMAGES.items()}.get(group)
    title = normalize(service.title)
    if group == normalize('Комплексы для рук'):
        if 'наращиван' in title or 'моделирован' in title:
            old_group = 'Комплексы Наращивание'
        elif 'укрепление гелем' in title:
            old_group = 'Комплексы с Гелем'
        elif 'гель лак' in title:
            old_group = 'Комплексы с Гель-лаком'
    if old_group:
        return next((card for card in images.get('nails', [])
                     if card['normalized'] == normalize(old_group)), None)
    return None


def match_image(service, images):
    """Return (manifest entry, reason), or (None, reason) for uncertain matches."""
    category = service.category.code
    title = normalize(service.title)
    cards = images.get(category, [])

    if category == 'nails':
        return None, 'на старой странице фотографии относятся к группам, а не к услугам'

    exact = [card for card in cards if card['normalized'] == title]
    if len(exact) == 1:
        return exact[0], 'точное название'

    # Variants in Excel often append hair length or a signed condition to the
    # old service name. A card must have a reasonably specific name.
    prefix = [card for card in cards if len(card['normalized']) >= 12 and
              title.startswith(card['normalized'] + ' ')]
    if prefix:
        longest = max(len(card['normalized']) for card in prefix)
        best = [card for card in prefix if len(card['normalized']) == longest]
        if len(best) == 1:
            return best[0], 'вариант услуги из Excel'
        return None, 'несколько карточек подходят по названию'

    aliases = {
        'hair': {
            'бережная смывка': 'Бережная смывка. 1-2 тона',
            'эйр тач': 'Air Touch',
            'лиссинг': 'Лиссинг - Долговременное выпрямление',
        },
        'forman': {
            'камуфляж седины': 'Камуфляж седины / бороды',
            'камуфляж бороды': 'Камуфляж седины / бороды',
        },
        'browlashes': {
            'ламинирование бровей': 'Ламинирование бровей и ресниц',
            'ламинирование ресниц': 'Ламинирование бровей и ресниц',
        },
    }.get(category, {})
    for lead, old_title in aliases.items():
        if title == lead or title.startswith(lead + ' '):
            card = next((item for item in cards if item['normalized'] == normalize(old_title)), None)
            if card:
                return card, 'подтверждённое соответствие названий'

    return None, 'на старой странице нет однозначной фотографии услуги'
