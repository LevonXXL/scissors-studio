from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from filer.models import Image as FilerImage

from core_utils.public_cache import invalidate_public_data
from masters.models import Master
from pages.models import Page, PagePicture
from salons.models import Salon

from .models import Service, ServiceCategory, ServicePrice, ServiceSalon, ServiceStaffPrice


def _invalidate(*domains, using):
    transaction.on_commit(lambda: invalidate_public_data(*domains), using=using)


@receiver((post_save, post_delete), sender=ServiceCategory)
def service_category_changed(sender, using, **kwargs):
    _invalidate('service-menu', 'service-catalog', using=using)


@receiver((post_save, post_delete), sender=Page)
@receiver((post_save, post_delete), sender=PagePicture)
def service_page_content_changed(sender, using, **kwargs):
    _invalidate('service-menu', 'service-catalog', using=using)


@receiver((post_save, post_delete), sender=Service)
@receiver((post_save, post_delete), sender=ServiceSalon)
@receiver((post_save, post_delete), sender=ServicePrice)
@receiver((post_save, post_delete), sender=ServiceStaffPrice)
@receiver((post_save, post_delete), sender=Salon)
@receiver((post_save, post_delete), sender=Master)
@receiver((post_save, post_delete), sender=FilerImage)
def service_catalog_data_changed(sender, using, **kwargs):
    _invalidate('service-catalog', 'service-catalog-salons', 'service-menu', using=using)
