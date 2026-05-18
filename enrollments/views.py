from django.contrib import messages
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from academics.models import Kelas, KelasStatus, Schedule
from accounts.decorators import role_required
from activity_logs.utils import log_activity

from .models import Enrollment, EnrollmentStatus


# ── Shared helper ──────────────────────────────────────────────────────────────

def _recalculate_kelas_status(kelas):
    """Recalculate kelas status (OPEN/FULL) based on current active enrollment count.
    Never changes a CLOSED kelas — only toggles between OPEN and FULL."""
    if kelas.status == KelasStatus.CLOSED:
        return
    active_count = Enrollment.objects.filter(
        kelas=kelas, status=EnrollmentStatus.ACTIVE, is_deleted=False
    ).count()
    new_status = KelasStatus.FULL if active_count >= kelas.capacity else KelasStatus.OPEN
    if kelas.status != new_status:
        kelas.status = new_status
        kelas.save(update_fields=['status', 'updated_at'])


_DAY_LABEL = {
    'MONDAY': 'Senin', 'TUESDAY': 'Selasa', 'WEDNESDAY': 'Rabu',
    'THURSDAY': 'Kamis', 'FRIDAY': 'Jumat', 'SATURDAY': 'Sabtu',
}


def _student_schedule_conflict(student_profile, new_kelas, exclude_enrollment_id=None):
    """Return error string if any schedule of `new_kelas` overlaps a schedule of a
    kelas the student is ACTIVE-enrolled in. None means no conflict.

    Overlap rule: same day AND (new.start < existing.end) AND (new.end > existing.start).
    """
    new_schedules = list(new_kelas.schedules.all())
    if not new_schedules:
        return None
    existing_qs = (
        Schedule.objects
        .filter(
            kelas__enrollments__student_profile=student_profile,
            kelas__enrollments__status=EnrollmentStatus.ACTIVE,
            kelas__enrollments__is_deleted=False,
            kelas__is_deleted=False,
        )
        .exclude(kelas_id=new_kelas.pk)
        .select_related('kelas')
        .distinct()
    )
    if exclude_enrollment_id:
        existing_qs = existing_qs.exclude(kelas__enrollments__pk=exclude_enrollment_id)
    existing = list(existing_qs)
    for new_s in new_schedules:
        for ex in existing:
            if ex.day != new_s.day:
                continue
            if new_s.start_time < ex.end_time and new_s.end_time > ex.start_time:
                day_label = _DAY_LABEL.get(new_s.day, new_s.day)
                return (
                    f'Jadwal {day_label} '
                    f'({new_s.start_time.strftime("%H:%M")}–{new_s.end_time.strftime("%H:%M")}) '
                    f'bertabrakan dengan kelas "{ex.kelas.name}" '
                    f'({ex.start_time.strftime("%H:%M")}–{ex.end_time.strftime("%H:%M")}).'
                )
    return None


def _try_enroll(student_profile, kelas):
    """Atomic enroll with row lock + capacity recheck + duplicate guard.

    Returns a tuple `(status, payload)`:
      - ('ok',          enrollment)  → newly created or reactivated
      - ('already',     enrollment)  → student already ACTIVE-enrolled
      - ('completed',   enrollment)  → student already COMPLETED this kelas
      - ('full',        None)        → capacity reached
      - ('closed',      None)        → kelas not OPEN
    """
    with transaction.atomic():
        locked_kelas = Kelas.objects.select_for_update().get(pk=kelas.pk)
        if locked_kelas.is_deleted or locked_kelas.status == KelasStatus.CLOSED:
            return ('closed', None)
        # Reactivate or block based on existing enrollment row
        existing = (
            Enrollment.objects
            .select_for_update()
            .filter(student_profile=student_profile, kelas=locked_kelas)
            .first()
        )
        if existing and existing.status == EnrollmentStatus.ACTIVE and not existing.is_deleted:
            return ('already', existing)
        if existing and existing.status == EnrollmentStatus.COMPLETED:
            return ('completed', existing)

        # Capacity recheck under lock — this is the race-safe count
        active_count = Enrollment.objects.filter(
            kelas=locked_kelas, status=EnrollmentStatus.ACTIVE, is_deleted=False
        ).count()
        if active_count >= locked_kelas.capacity:
            # Sync status before bailing so the page reflects FULL
            if locked_kelas.status != KelasStatus.FULL:
                locked_kelas.status = KelasStatus.FULL
                locked_kelas.save(update_fields=['status', 'updated_at'])
            return ('full', None)

        if existing:  # DROPPED → reactivate the row
            existing.status = EnrollmentStatus.ACTIVE
            existing.is_deleted = False
            existing.deleted_at = None
            existing.price_at_enrollment = locked_kelas.price
            existing.save()
            enrollment = existing
        else:
            try:
                enrollment = Enrollment.objects.create(
                    student_profile=student_profile,
                    kelas=locked_kelas,
                    status=EnrollmentStatus.ACTIVE,
                    price_at_enrollment=locked_kelas.price,
                )
            except IntegrityError:
                # Lost a race to a parallel writer that created the same row.
                # Treat it as "already enrolled".
                dup = Enrollment.objects.get(
                    student_profile=student_profile, kelas=locked_kelas
                )
                return ('already', dup)

        _recalculate_kelas_status(locked_kelas)
        return ('ok', enrollment)


# ── Student views ──────────────────────────────────────────────────────────────

@role_required('STUDENT')
@require_POST
def enroll(request, kelas_id):
    kelas = get_object_or_404(Kelas, pk=kelas_id, is_deleted=False)

    # Class must be OPEN (rejects FULL and CLOSED) — pre-check before locking
    if kelas.status != KelasStatus.OPEN:
        if kelas.status == KelasStatus.FULL:
            messages.error(request, 'Kelas sudah penuh.')
        else:
            messages.error(request, 'Kelas ini sudah tidak menerima pendaftaran.')
        return redirect('academics:class_detail', pk=kelas_id)

    # Block enrollment if class has already started
    today = timezone.localdate()
    if kelas.start_date < today:
        messages.error(request, 'Pendaftaran sudah ditutup, kelas sudah dimulai.')
        return redirect('academics:class_detail', pk=kelas_id)

    # Level must match
    student_profile = request.user.student_profile
    if student_profile.level != kelas.level:
        messages.error(request, f'Kelas ini untuk jenjang {kelas.level}, bukan {student_profile.level}.')
        return redirect('academics:class_detail', pk=kelas_id)

    # Schedule conflict against student's existing ACTIVE enrollments
    conflict = _student_schedule_conflict(student_profile, kelas)
    if conflict:
        messages.error(request, conflict)
        return redirect('academics:class_detail', pk=kelas_id)

    # Race-safe enroll under row lock + capacity recheck
    result, payload = _try_enroll(student_profile, kelas)

    if result == 'already':
        messages.error(request, 'Anda sudah terdaftar di kelas ini.')
        return redirect('academics:class_detail', pk=kelas_id)
    if result == 'completed':
        messages.error(request, 'Anda sudah menyelesaikan kelas ini.')
        return redirect('academics:class_detail', pk=kelas_id)
    if result == 'full':
        messages.error(request, 'Kelas sudah penuh.')
        return redirect('academics:class_detail', pk=kelas_id)
    if result == 'closed':
        messages.error(request, 'Kelas ini sudah tidak menerima pendaftaran.')
        return redirect('academics:class_detail', pk=kelas_id)

    enrollment = payload
    log_activity(request.user, 'created', 'enrollment', enrollment.pk)
    messages.success(request, f'Berhasil mendaftar di kelas {kelas.name}!')
    return redirect('enrollments:my_classes')


@role_required('STUDENT')
def my_classes(request):
    from sessions_app.models import BookingStatus, SessionBooking
    all_enrollments = (
        Enrollment.objects
        .filter(student_profile__user=request.user)
        .select_related('kelas', 'kelas__subject', 'kelas__teacher_profile__user', 'kelas__academic_period')
        .prefetch_related('kelas__schedules', 'teacher_rating')
        .order_by('-enrolled_at')
    )
    active_enrollments = [e for e in all_enrollments if e.status == EnrollmentStatus.ACTIVE and not e.is_deleted]
    completed_enrollments = [e for e in all_enrollments if e.status == EnrollmentStatus.COMPLETED]
    dropped_enrollments = [e for e in all_enrollments if e.status == EnrollmentStatus.DROPPED]

    # Attach booked session counts for active enrollments
    active_ids = [e.pk for e in active_enrollments]
    from django.db.models import Count, Q
    booking_counts = dict(
        SessionBooking.objects
        .filter(enrollment_id__in=active_ids, status=BookingStatus.BOOKED)
        .values('enrollment_id')
        .annotate(cnt=Count('id'))
        .values_list('enrollment_id', 'cnt')
    )
    for e in active_enrollments:
        e.booked_sessions = booking_counts.get(e.pk, 0)

    return render(request, 'enrollments/my_classes.html', {
        'active_enrollments': active_enrollments,
        'completed_enrollments': completed_enrollments,
        'dropped_enrollments': dropped_enrollments,
    })


@role_required('STUDENT')
@require_POST
def drop_class(request, pk):
    enrollment = get_object_or_404(
        Enrollment, pk=pk, student_profile__user=request.user, is_deleted=False
    )

    # Guard: only ACTIVE enrollments can be dropped
    if enrollment.status != EnrollmentStatus.ACTIVE:
        messages.error(request, 'Hanya pendaftaran aktif yang bisa dibatalkan.')
        return redirect('enrollments:my_classes')

    kelas = enrollment.kelas
    enrollment_pk = enrollment.pk
    with transaction.atomic():
        enrollment.status = EnrollmentStatus.DROPPED
        enrollment.soft_delete()
        _recalculate_kelas_status(kelas)
    log_activity(request.user, 'deleted', 'enrollment', enrollment_pk)

    messages.success(request, f'Berhasil keluar dari kelas {kelas.name}.')
    return redirect('enrollments:my_classes')


# ── Teacher views ──────────────────────────────────────────────────────────────

@role_required('TEACHER')
@require_POST
def teacher_update_enrollment(request, pk):
    """Teacher manually changes an enrollment's status."""
    enrollment = get_object_or_404(Enrollment, pk=pk, is_deleted=False)

    # Ownership: requesting user must be the teacher of the kelas
    if enrollment.kelas.teacher != request.user:
        messages.error(request, 'Anda tidak memiliki akses untuk mengubah pendaftaran ini.')
        return redirect('academics:teacher_classes')

    new_status = request.POST.get('status', '').strip()
    if new_status not in EnrollmentStatus.values:
        messages.error(request, 'Status tidak valid.')
        return redirect('academics:teacher_class_students', pk=enrollment.kelas_id)

    if enrollment.status == new_status:
        return redirect('academics:teacher_class_students', pk=enrollment.kelas_id)

    with transaction.atomic():
        enrollment.status = new_status
        enrollment.save(update_fields=['status', 'updated_at'])
        _recalculate_kelas_status(enrollment.kelas)

    status_label = {'ACTIVE': 'Aktif', 'COMPLETED': 'Selesai', 'DROPPED': 'Keluar'}.get(new_status, new_status)
    messages.success(
        request,
        f'Status {enrollment.student.get_full_name()} diubah menjadi {status_label}.'
    )
    return redirect('academics:teacher_class_students', pk=enrollment.kelas_id)
