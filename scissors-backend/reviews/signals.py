from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from filer.models import Image as FilerImage

from core_utils.public_cache import invalidate_public_data
from salons.models import Salon

from .models import Review, ReviewImage


@receiver((post_save, post_delete), sender=Review)
@receiver((post_save, post_delete), sender=ReviewImage)
@receiver((post_save, post_delete), sender=Salon)
@receiver((post_save, post_delete), sender=FilerImage)
def public_reviews_changed(sender, using, **kwargs):
    transaction.on_commit(
        lambda: invalidate_public_data('reviews'),
        using=using,
    )
