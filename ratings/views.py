from django.contrib import messages
from django.core.cache import cache
from django.db import transaction
from django.db.models import Avg, Count
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import role_required
from activity_logs.utils import log_activity
from enrollments.models import Enrollment, EnrollmentStatus

from .models import ClassRating, TeacherRating


@role_required('STUDENT')
def rate_teacher(request, enrollment_id):
    """Rate the teacher AND the kelas after enrollment is COMPLETED.

    Both ratings are submitted together (single form), persisted atomically,
    and cache is invalidated for downstream pages (teacher profile, kelas
    detail reviews, admin leaderboards).
    """
    enrollment = get_object_or_404(
        Enrollment.objects.select_related(
            'kelas__subject', 'kelas__teacher_profile__user',
        ),
        pk=enrollment_id,
        student_profile__user=request.user,
        is_deleted=False,
    )
    kelas = enrollment.kelas
    teacher = kelas.teacher_profile

    # ── Guard 1: must be COMPLETED ────────────────────────────────────────
    if enrollment.status != EnrollmentStatus.COMPLETED:
        messages.error(request, 'Kamu hanya bisa memberikan rating setelah kelas selesai.')
        return redirect('enrollments:my_class_detail', enrollment_id=enrollment.id)

    # ── Guard 2: must not have rated already (either side) ────────────────
    already_rated_teacher = TeacherRating.objects.filter(enrollment=enrollment).exists()
    already_rated_class = ClassRating.objects.filter(enrollment=enrollment).exists()
    if already_rated_teacher or already_rated_class:
        messages.info(request, 'Kamu sudah memberikan rating untuk kelas ini. Terima kasih!')
        return redirect('enrollments:my_class_detail', enrollment_id=enrollment.id)

    if request.method == 'POST':
        try:
            teacher_score = int(request.POST.get('teacher_score', 0))
            class_score = int(request.POST.get('class_score', 0))
        except (ValueError, TypeError):
            messages.error(request, 'Format rating tidak valid.')
            return redirect('ratings:rate_teacher', enrollment_id=enrollment.id)
        teacher_comment = request.POST.get('teacher_comment', '').strip()
        class_comment = request.POST.get('class_comment', '').strip()

        # Validate score range
        if not (1 <= teacher_score <= 5) or not (1 <= class_score <= 5):
            messages.error(request, 'Rating harus antara 1 hingga 5 bintang.')
            return redirect('ratings:rate_teacher', enrollment_id=enrollment.id)
        # Validate optional comment length
        if teacher_comment and len(teacher_comment) < 20:
            messages.error(request, 'Komentar untuk guru minimal 20 karakter (atau kosongkan).')
            return redirect('ratings:rate_teacher', enrollment_id=enrollment.id)
        if class_comment and len(class_comment) < 20:
            messages.error(request, 'Komentar untuk kelas minimal 20 karakter (atau kosongkan).')
            return redirect('ratings:rate_teacher', enrollment_id=enrollment.id)

        try:
            with transaction.atomic():
                # Lock the enrollment row so a double-submit can't slip past the
                # already-rated guard. OneToOne unique constraint on
                # (enrollment) is the final fence — IntegrityError still possible
                # under extreme race, caught below.
                Enrollment.objects.select_for_update().get(pk=enrollment.pk)
                if (
                    TeacherRating.objects.filter(enrollment=enrollment).exists()
                    or ClassRating.objects.filter(enrollment=enrollment).exists()
                ):
                    messages.info(request, 'Kamu sudah memberikan rating untuk kelas ini.')
                    return redirect('enrollments:my_class_detail', enrollment_id=enrollment.id)

                t_rating = TeacherRating.objects.create(
                    enrollment=enrollment,
                    teacher_profile=teacher,
                    score=teacher_score,
                    comment=teacher_comment or '',
                )
                ClassRating.objects.create(
                    enrollment=enrollment,
                    kelas=kelas,
                    score=class_score,
                    comment=class_comment or '',
                )

                # Invalidate downstream caches
                cache.delete_many([
                    f'teacher_avg_rating_{teacher.id}',
                    f'teacher_{teacher.id}_stats',
                    f'teacher_profile_{teacher.user_id}_stats',
                    f'teacher_profile_{teacher.user_id}_reviews',
                    f'kelas_{kelas.id}_reviews',
                    'admin_top_teachers',
                    'admin_worst_teachers',
                    'top_teachers_dashboard',
                ])
            log_activity(request.user, 'created', 'rating', t_rating.pk)
            messages.success(
                request,
                f'Terima kasih! Rating untuk {teacher.user.get_full_name() or teacher.user.username} '
                f'dan kelas {kelas.name} berhasil dikirim. ⭐'
            )
            return redirect('enrollments:my_class_detail', enrollment_id=enrollment.id)
        except Exception:
            import logging
            logging.getLogger(__name__).exception('Rating submission failed')
            messages.error(request, 'Terjadi kesalahan saat menyimpan rating. Silakan coba lagi.')
            return redirect('ratings:rate_teacher', enrollment_id=enrollment.id)

    # ── GET: render form ──────────────────────────────────────────────────
    teacher_full_name = teacher.user.get_full_name() or teacher.user.username
    initials_first = (teacher.user.first_name[:1] if teacher.user.first_name else teacher.user.username[:1]).upper()
    initials_last = (teacher.user.last_name[:1] if teacher.user.last_name else '').upper()
    teacher_initials = (initials_first + initials_last) or '?'
    subject_emoji = (kelas.subject.icon if kelas.subject else '') or '📖'

    return render(request, 'ratings/rate_teacher.html', {
        'enrollment': enrollment,
        'kelas': kelas,
        'teacher': teacher,
        'teacher_full_name': teacher_full_name,
        'teacher_initials': teacher_initials,
        'subject_emoji': subject_emoji,
    })


@role_required('TEACHER')
def teacher_ratings(request):
    try:
        teacher_profile = request.user.teacher_profile
    except Exception:
        teacher_profile = None

    ratings = (
        TeacherRating.objects.filter(
            teacher_profile=teacher_profile,
            enrollment__is_deleted=False,
        )
        .select_related(
            'enrollment__student_profile__user',
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
