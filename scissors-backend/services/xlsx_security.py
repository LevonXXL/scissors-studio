"""Limits for untrusted XLSX archives before XML expansion."""

from pathlib import PurePosixPath
from functools import wraps
from xml.etree import ElementTree as ET
from zipfile import BadZipFile


MAX_XLSX_BYTES = 5_000_000
MAX_ARCHIVE_ENTRIES = 500
MAX_EXPANDED_BYTES = 40_000_000
MAX_MEMBER_BYTES = 20_000_000


def reject_malformed_xlsx(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except (BadZipFile, ET.ParseError, KeyError, IndexError,
                AttributeError, RuntimeError) as exc:
            raise ValueError('Повреждённый или неподдерживаемый XLSX.') from exc
    return wrapper


def validate_xlsx_archive(archive, input_size):
    if input_size > MAX_XLSX_BYTES:
        raise ValueError('Файл больше 5 МБ.')
    members = archive.infolist()
    if len(members) > MAX_ARCHIVE_ENTRIES:
        raise ValueError('Слишком много файлов внутри XLSX.')
    if any(item.file_size > MAX_MEMBER_BYTES for item in members):
        raise ValueError('В XLSX есть слишком большой файл.')
    if sum(item.file_size for item in members) > MAX_EXPANDED_BYTES:
        raise ValueError('Распакованный XLSX превышает лимит размера.')


def worksheet_path(target):
    if not isinstance(target, str) or '\\' in target:
        raise ValueError('Некорректный путь листа XLSX.')
    relative = target.lstrip('/')
    path = PurePosixPath(relative if relative.startswith('xl/') else f'xl/{relative}')
    if (len(path.parts) < 3 or path.parts[:2] != ('xl', 'worksheets')
            or any(part in ('.', '..') for part in path.parts)):
        raise ValueError('Некорректный путь листа XLSX.')
    return str(path)
