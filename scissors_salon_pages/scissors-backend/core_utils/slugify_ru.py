"""
Небольшая замена внешней либы транслитерации (в chinese-russian использовался
`libs.translit.slugify`, здесь зависимости нет — пишем сами, благо логика
тривиальная: побуквенная транслитерация кириллицы + стандартный slugify).
"""

from django.utils.text import slugify as django_slugify

_TRANSLIT_MAP = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
}


def slugify_ru(value: str) -> str:
    """Транслитерирует кириллицу в латиницу и прогоняет через обычный slugify."""
    if not value:
        return ''
    lowered = value.lower()
    transliterated = ''.join(_TRANSLIT_MAP.get(ch, ch) for ch in lowered)
    return django_slugify(transliterated)
