"""Normalize YCLIENTS identifiers and names used for safe matching."""


def yclients_id(value):
    identifier = str(value).strip() if value is not None else ''
    return identifier if identifier not in {'', '-', '—'} else None


def staff_name(value):
    return ' '.join((value or '').split()).casefold()
