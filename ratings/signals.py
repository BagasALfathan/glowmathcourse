"""Cache invalidation when ratings change.

Keeps the sidebar's "Beri Rating" badge in sync — when a student finally rates
a COMPLETED enrollment, their unrated-count must drop on the next request.
"""
from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import TeacherRating


@receiver(post_save, sender=TeacherRating)
@receiver(post_delete, sender=TeacherRating)
def invalidate_sidebar_rating_cache(sender, instance, **kwargs):
    try:
        user_id = instance.enrollment.student_profile.user_id
    except Exception:
        return
    cache.delete(f'sidebar_pending_ratings_{user_id}')
