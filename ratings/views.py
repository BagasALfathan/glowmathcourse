from collections import defaultdict

from django.contrib import messages
from django.db.models import Avg, Count
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import role_required
from activity_logs.utils import log_activity
from enrollments.models import Enrollment, EnrollmentStatus

from .models import Rating


@role_required('STUDENT')
def rate_teacher(request, enrollment_id):
    enrollment = get_object_or_404(
        Enrollment,
        pk=enrollment_id,
        student=request.user,
        is_deleted=False,
    )

    if enrollment.status != EnrollmentStatus.COMPLETED:
        messages.warning(request, 'Anda hanya bisa memberikan rating setelah kelas selesai.')
        return redirect('enrollments:my_classes')

    try:
        existing_rating = enrollment.rating
    except Rating.DoesNotExist:
        existing_rating = None

    if request.method == 'POST':
        score_raw = request.POST.get('score', '').strip()
        comment = request.POST.get('comment', '').strip() or None

        if not score_raw.isdigit() or not (1 <= int(score_raw) <= 5):
            messages.error(request, 'Pilih rating bintang 1–5.')
            return render(request, 'ratings/rate_teacher.html', {
                'enrollment': enrollment,
                'existing_rating': existing_rating,
            })

        score = int(score_raw)
        if existing_rating:
            existing_rating.score = score
            existing_rating.comment = comment
            existing_rating.save()
            log_activity(request.user, 'updated', 'rating', existing_rating.pk)
            messages.success(request, 'Rating berhasil diperbarui!')
        else:
            new_rating = Rating.objects.create(enrollment=enrollment, score=score, comment=comment)
            log_activity(request.user, 'created', 'rating', new_rating.pk)
            messages.success(request, 'Rating berhasil diberikan!')

        return redirect('enrollments:my_classes')

    return render(request, 'ratings/rate_teacher.html', {
        'enrollment': enrollment,
        'existing_rating': existing_rating,
    })


@role_required('TEACHER')
def teacher_ratings(request):
    ratings = (
        Rating.objects.filter(
            enrollment__kelas__teacher=request.user,
            enrollment__is_deleted=False,
        )
        .select_related(
            'enrollment__student',
            'enrollment__kelas',
            'enrollment__kelas__subject',
        )
        .order_by('-created_at')
    )

    overall = ratings.aggregate(avg=Avg('score'), count=Count('id'))
    overall_avg = round(overall['avg'], 1) if overall['avg'] else None

    # Group by kelas
    kelas_map = {}
    for r in ratings:
        kelas = r.enrollment.kelas
        if kelas.pk not in kelas_map:
            kelas_map[kelas.pk] = {'kelas': kelas, 'ratings': []}
        kelas_map[kelas.pk]['ratings'].append(r)

    kelas_ratings = []
    for data in kelas_map.values():
        scores = [r.score for r in data['ratings']]
        data['avg'] = round(sum(scores) / len(scores), 1)
        kelas_ratings.append(data)

    return render(request, 'ratings/teacher_ratings.html', {
        'overall_avg': overall_avg,
        'overall_count': overall['count'],
        'kelas_ratings': kelas_ratings,
    })
