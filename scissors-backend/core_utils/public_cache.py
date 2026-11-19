"""Small, bounded cache helpers for public API representations."""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Callable, TypeVar

from django.conf import settings
from django.core.cache import caches
from redis.exceptions import RedisError
from rest_framework.response import Response

logger = logging.getLogger(__name__)

T = TypeVar('T')
CACHE_ALIAS = 'public_content'


def is_authenticated_request(request) -> bool:
    user = getattr(request, 'user', None)
    return bool(request.headers.get('Authorization') or getattr(user, 'is_authenticated', False))


def _cache_key(domain: str, key: str) -> str:
    digest = hashlib.sha256(key.encode('utf-8')).hexdigest()
    return f'{domain}:v1:{digest}'


def remember_public_data(domain: str, key: str, loader: Callable[[], T], timeout: int) -> T:
    """Read/write JSON-compatible public data; Redis outages fall through to the DB."""
    if settings.DEBUG:
        return loader()
    cache = caches[CACHE_ALIAS]
    version_key = f'public-data:generation:{domain}'

    try:
        version = cache.get(version_key, 1)
        cached = cache.get(_cache_key(domain, f'{version}:{key}'))
    except RedisError:
        logger.warning('Public data cache unavailable; loading %s from the database.', domain)
        return loader()

    if cached is not None:
        return cached

    value = loader()
    try:
        cache.set(_cache_key(domain, f'{version}:{key}'), value, timeout)
    except RedisError:
        logger.warning('Public data cache write failed for %s.', domain)
    return value


def invalidate_public_data(*domains: str) -> None:
    """Advance cache generations so a committed model change makes old data unreachable."""
    cache = caches[CACHE_ALIAS]
    for domain in domains:
        key = f'public-data:generation:{domain}'
        try:
            if not cache.add(key, 2, timeout=None):
                try:
                    cache.incr(key)
                except ValueError:
                    cache.set(key, 2, timeout=None)
        except RedisError:
            logger.warning('Could not invalidate public data cache for %s.', domain)


def json_compatible(value):
    """Convert DRF serializer output to plain JSON values before storing it."""
    from rest_framework.renderers import JSONRenderer

    return json.loads(JSONRenderer().render(value))


def cached_public_response(domain: str, key: str, request, loader, timeout: int):
    """Cache a successful public DRF response, bypassing authenticated requests."""
    if is_authenticated_request(request):
        return loader()

    uncached_response = None

    def load_json():
        nonlocal uncached_response
        response = loader()
        if response.status_code != 200:
            uncached_response = response
            return None
        return json_compatible(response.data)

    data = remember_public_data(domain, key, load_json, timeout)
    if data is None:
        return uncached_response
    return Response(data)
