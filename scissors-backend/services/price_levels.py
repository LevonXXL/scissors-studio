"""Price levels shared by the Excel import and master profiles."""

HAIR_LEVELS = ('universal', 'modeler', 'stylist', 'top_stylist', 'art_director')
NAIL_LEVELS = ('nail_master', 'top_nail_master')
LEVEL_LABELS = {
    'universal': 'Универсал',
    'modeler': 'Модельер',
    'stylist': 'Стилист',
    'top_stylist': 'Топ-стилист',
    'art_director': 'Арт-директор',
    'nail_master': 'Мастер',
    'top_nail_master': 'Топ-мастер',
    '': 'Единая цена',
}
MASTER_PRICE_LEVEL_CHOICES = tuple(
    (level, LEVEL_LABELS[level]) for level in (*HAIR_LEVELS, *NAIL_LEVELS)
)
SERVICE_PRICE_LEVEL_CHOICES = (('', LEVEL_LABELS['']), *MASTER_PRICE_LEVEL_CHOICES)
