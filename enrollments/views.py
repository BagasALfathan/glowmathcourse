from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from academics.models import Kelas, KelasStatus
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


# ── Student views ──────────────────────────────────────────────────────────────

@role_required('STUDENT')
@require_POST
def enroll(request, kelas_id):
    kelas = get_object_or_404(Kelas, pk=kelas_id, is_deleted=False)

    # Class must be OPEN (rejects FULL and CLOSED)
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
    student_level = request.user.student_profile.level
    if student_level != kelas.level:
        messages.error(request, f'Kelas ini untuk jenjang {kelas.level}, bukan {student_level}.')
        return redirect('academics:class_detail', pk=kelas_id)

    # Capacity check (double-check, in case status is stale)
    active_count = Enrollment.objects.filter(
        kelas=kelas, status=EnrollmentStatus.ACTIVE, is_deleted=False
    ).count()
    if active_count >= kelas.capacity:
        messages.error(request, 'Kelas sudah penuh.')
        return redirect('academics:class_detail', pk=kelas_id)

    # Check for existing enrollment (handles re-enrollment after dropping)
    existing = Enrollment.objects.filter(student=request.user, kelas=kelas).first()
    if existing:
        if existing.status == EnrollmentStatus.ACTIVE:
            messages.error(request, 'Anda sudah terdaftar di kelas ini.')
            return redirect('academics:class_detail', pk=kelas_id)
        if existing.status == EnrollmentStatus.COMPLETED:
            messages.error(request, 'Anda sudah menyelesaikan kelas ini.')
            return redirect('academics:class_detail', pk=kelas_id)
        # DROPPED → reactivate existing record
        with transaction.atomic():
            existing.status = EnrollmentStatus.ACTIVE
            existing.is_deleted = False
            existing.deleted_at = None
            existing.save()
            _recalculate_kelas_status(kelas)
        log_activity(request.user, 'created', 'enrollment', existing.pk)
        messages.success(request, f'Berhasil mendaftar kembali di kelas {kelas.name}!')
        return redirect('enrollments:my_classes')

    with transaction.atomic():
        enrollment = Enrollment.objects.create(
            student=request.user,
            kelas=kelas,
            status=EnrollmentStatus.ACTIVE,
        )
        _recalculate_kelas_status(kelas)
    log_activity(request.user, 'created', 'enrollment', enrollment.pk)
    messages.success(request, f'Berhasil mendaftar di kelas {kelas.name}!')
    return redirect('enrollments:my_classes')


@role_required('STUDENT')
def my_classes(request):
    from sessions_app.models import BookingStatus, SessionBooking
    all_enrollments = (
        Enrollment.objects
        .filter(student=request.user)
        .select_related('kelas', 'kelas__subject', 'kelas__teacher', 'kelas__academic_period')
        .prefetch_related('kelas__schedules', 'rating')
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
        Enrollment, pk=pk, student=request.user, is_deleted=False
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
