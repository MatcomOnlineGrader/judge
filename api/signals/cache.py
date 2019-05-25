from django.core.cache import cache
from django.db.models import signals
from django.dispatch import receiver

from api.lib import constants
from api.models import Contest, Post, Submission


@receiver(signals.post_delete, sender=Post)
@receiver(signals.post_save, sender=Post)
def clean_ten_most_recent_posts(*args, **kwargs):
    cache.delete(constants.CACHE_KEY_TEN_MOST_RECENT_POSTS)


@receiver(signals.post_delete, sender=Contest)
@receiver(signals.post_delete, sender=Submission)
@receiver(signals.post_save, sender=Contest)
@receiver(signals.post_save, sender=Submission)
def clean_five_top_rated_profiles(*args, **kwargs):
    cache.delete(constants.CACHE_KEY_FIVE_TOP_RATED_PROFILES)
