"""Optional periodic refresh using the project's existing Celery workers."""

import logging

from celery import shared_task

from .manticore import index_all


logger = logging.getLogger(__name__)


@shared_task
def refresh_manticore_index():
    return index_all(lambda line: logger.info('Manticore: %s', line))
