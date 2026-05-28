"""Cache invalidation signals for /my-schedule/.

When a student enrolls (or drops), invalidate their schedule cache for the
window of weeks that the enrollment might affect — we use a 9-week window
(prev week + current + 7 future) which covers everything they would scroll
through in normal use. 30s-5min caches can also expire naturally; this just
makes the change instant.
"""
from datetime import timedelta

from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import Enrollment


@receiver(post_save, sender=Enrollment)
@receiver(post_delete, sender=Enrollment)
def invalidate_schedule_cache_on_enrollment(sender, instance, **kwargs):
    today = timezone.localdate()
    monday = today - timedelta(days=today.weekday())
    keys = [
        f'schedule_{instance.student_profile_id}_{monday + timedelta(days=w * 7)}'
        for w in range(-1, 8)
    ]
    cache.delete_many(keys)


@receiver(post_save, sender=Enrollment)
@receiver(post_delete, sender=Enrollment)
def invalidate_sidebar_pending_ratings_on_enrollment(sender, instance, **kwargs):
    """When an enrollment is created, dropped, or transitions to COMPLETED, the
    student's sidebar pending-rating count must be recomputed on next request."""
    try:
        user_id = instance.student_profile.user_id
    except Exception:
        return
    cache.delete(f'sidebar_pending_ratings_{user_id}')
