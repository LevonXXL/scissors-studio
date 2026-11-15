"""Conservative mapping of YCLIENTS staff roles to Excel price levels."""

import re
import unicodedata

from services.price_levels import MASTER_PRICE_LEVEL_CHOICES


def normalize_role(value):
    text = unicodedata.normalize('NFKC', str(value or '')).casefold().replace('ё', 'е')
    return ' '.join(re.sub(r'[^\w]+', ' ', text).split())


ROLE_LEVELS = {
    'мастер универсал': 'universal',
    'мастер модельер': 'modeler',
    'стилист': 'stylist',
    'мастер стилист': 'stylist',
    'топ стилист': 'top_stylist',
    'nail мастер': 'nail_master',
    'нейл мастер': 'nail_master',
    'неил мастер': 'nail_master',
    'мастер маникюра': 'nail_master',
    'мастер маникюра и педикюра': 'nail_master',
    'мастер маникюра педикюра': 'nail_master',
    'старший нейл мастер': 'top_nail_master',
    'старший неил мастер': 'top_nail_master',
}


def inferred_price_level(staff_entry):
    """Return a supported level only for an exact staff role match."""
    position = staff_entry.get('position')
    title = position.get('title') if isinstance(position, dict) else position
    role = normalize_role(title or staff_entry.get('specialization'))
    level = ROLE_LEVELS.get(role)
    if level and level in dict(MASTER_PRICE_LEVEL_CHOICES):
        return level
    return None


def is_founder(master):
    return normalize_role(master.name) == 'михаил стець'
