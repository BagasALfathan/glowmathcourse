"""Sidebar context — exposes per-request data needed by the shared sidebar
partials (especially badge counts) without forcing every view to pass it.

Computed only for authenticated STUDENT users; everyone else gets safe zero
defaults so templates can reference the keys unconditionally.
"""
from django.core.cache import cache


def sidebar_data(request):
    data = {
        'sidebar_pending_ratings_count': 0,
        'sidebar_first_unrated_enrollment_id': None,
    }

    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return data
    if getattr(user, 'role', None) != 'STUDENT':
        return data
    if not hasattr(user, 'student_profile'):
        return data

    sp = user.student_profile
    cache_key = f'sidebar_pending_ratings_{user.id}'
    cached = cache.get(cache_key)

    if cached is not None:
        data['sidebar_pending_ratings_count'] = cached.get('count', 0)
        data['sidebar_first_unrated_enrollment_id'] = cached.get('first_id')
        return data

    try:
        from enrollments.models import Enrollment, EnrollmentStatus
        from ratings.models import TeacherRating

        rated_ids = TeacherRating.objects.filter(
            enrollment__student_profile=sp,
        ).values_list('enrollment_id', flat=True)

        unrated = (
            Enrollment.objects
            .filter(
                student_profile=sp,
                status=EnrollmentStatus.COMPLETED,
                is_deleted=False,
            )
            .exclude(id__in=rated_ids)
            .order_by('-updated_at', '-id')
        )

        count = unrated.count()
        first_id = unrated.values_list('id', flat=True).first() if count else None
    except Exception:
        count = 0
        first_id = None

    cache.set(cache_key, {'count': count, 'first_id': first_id}, 300)
    data['sidebar_pending_ratings_count'] = count
    data['sidebar_first_unrated_enrollment_id'] = first_id
    return data
