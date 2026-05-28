"""Cache invalidation signals for /my-schedule/.

A student's weekly schedule is cached per (student_id, week_start_date).
When a Session is created/updated/deleted, we invalidate the cache for every
ACTIVE-enrolled student of that session's kelas for the affected week.

When an Enrollment is created/dropped, we invalidate the next ~8 weeks of
schedule cache for that student so the change is reflected immediately.
"""
from datetime import timedelta

from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Session


@receiver(post_save, sender=Session)
@receiver(post_delete, sender=Session)
def invalidate_schedule_cache_on_session(sender, instance, **kwargs):
    """Invalidate /my-schedule/ cache for all ACTIVE-enrolled students of this
    session's kelas, for the week containing the session date."""
    if not instance.date:
        return
    from enrollments.models import Enrollment, EnrollmentStatus
    week_start = instance.date - timedelta(days=instance.date.weekday())
    student_ids = list(
        Enrollment.objects
        .filter(
            kelas=instance.kelas,
            status=EnrollmentStatus.ACTIVE,
            is_deleted=False,
        )
        .values_list('student_profile_id', flat=True)
    )
    if student_ids:
        cache.delete_many([f'schedule_{sid}_{week_start}' for sid in student_ids])
