import json

from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from .forms import KelasEditForm, KelasForm
from .models import Day, Kelas, KelasStatus, Schedule


# ── Shared schedule helpers ────────────────────────────────────────────────────

def _parse_schedules(post):
    """Extract schedule rows from POST data. Returns list of dicts."""
    rows = []
    i = 0
    while f'schedule_day_{i}' in post:
        rows.append({
            'day': post.get(f'schedule_day_{i}', '').strip(),
            'start_time': post.get(f'schedule_start_time_{i}', '').strip(),
            'end_time': post.get(f'schedule_end_time_{i}', '').strip(),
            'room': post.get(f'schedule_room_{i}', '').strip(),
        })
        i += 1
    return rows


def _validate_schedules(rows):
    """Return list of error strings. Empty list means valid."""
    errors = []
    if not rows:
        errors.append('Minimal satu jadwal harus ditambahkan.')
        return errors
    for idx, s in enumerate(rows, start=1):
        if not s['day']:
            errors.append(f'Jadwal {idx}: Hari wajib dipilih.')
        if not s['start_time']:
            errors.append(f'Jadwal {idx}: Jam mulai wajib diisi.')
        if not s['end_time']:
            errors.append(f'Jadwal {idx}: Jam selesai wajib diisi.')
        elif s['start_time'] and s['end_time'] and s['start_time'] >= s['end_time']:
            errors.append(f'Jadwal {idx}: Jam selesai harus lebih besar dari jam mulai.')
    return errors


def _schedules_to_json(kelas):
    """Serialize existing DB schedules to JSON for Alpine.js pre-population."""
    return json.dumps([
        {
            'day': s.day,
            'start_time': s.start_time.strftime('%H:%M'),
            'end_time': s.end_time.strftime('%H:%M'),
            'room': s.room,
        }
        for s in kelas.schedules.all()
    ])


def _rows_to_json(rows):
    """Serialize posted schedule rows back to JSON on form error."""
    return json.dumps(rows) if rows else json.dumps(
        [{'day': '', 'start_time': '', 'end_time': '', 'room': ''}]
    )


# ── Views ──────────────────────────────────────────────────────────────────────

@role_required('TEACHER')
def teacher_classes_list(request):
    status_filter = request.GET.get('status', '')
    qs = (
        Kelas.objects
        .filter(teacher=request.user, is_deleted=False)
        .select_related('subject', 'academic_period')
        .prefetch_related('schedules')
    )
    if status_filter and status_filter in KelasStatus.values:
        qs = qs.filter(status=status_filter)

    return render(request, 'academics/teacher_classes.html', {
        'klasses': qs,
        'status_filter': status_filter,
        'KelasStatus': KelasStatus,
    })


@role_required('TEACHER')
def teacher_class_create(request):
    form = KelasForm(request.POST or None)
    schedule_errors = []
    posted_schedules = []

    if request.method == 'POST':
        posted_schedules = _parse_schedules(request.POST)
        schedule_errors = _validate_schedules(posted_schedules)

        if form.is_valid() and not schedule_errors:
            with transaction.atomic():
                kelas = form.save(commit=False)
                kelas.teacher = request.user
                kelas.save()
                for s in posted_schedules:
                    Schedule.objects.create(
                        kelas=kelas, day=s['day'],
                        start_time=s['start_time'], end_time=s['end_time'],
                        room=s['room'],
                    )
            messages.success(request, 'Kelas berhasil dibuat!')
            return redirect('academics:teacher_classes')

    return render(request, 'academics/teacher_class_create.html', {
        'form': form,
        'schedule_errors': schedule_errors,
        'schedules_json': _rows_to_json(posted_schedules),
    })


@role_required('TEACHER')
def teacher_class_edit(request, pk):
    kelas = get_object_or_404(Kelas, pk=pk, teacher=request.user, is_deleted=False)
    form = KelasEditForm(request.POST or None, instance=kelas)
    schedule_errors = []
    posted_schedules = []

    if request.method == 'POST':
        posted_schedules = _parse_schedules(request.POST)
        schedule_errors = _validate_schedules(posted_schedules)

        if form.is_valid() and not schedule_errors:
            with transaction.atomic():
                form.save()
                kelas.schedules.all().delete()
                for s in posted_schedules:
                    Schedule.objects.create(
                        kelas=kelas, day=s['day'],
                        start_time=s['start_time'], end_time=s['end_time'],
                        room=s['room'],
                    )
            messages.success(request, 'Kelas berhasil diperbarui!')
            return redirect('academics:teacher_classes')

        # On error, restore what the user typed into Alpine
        schedules_json = _rows_to_json(posted_schedules)
    else:
        schedules_json = _schedules_to_json(kelas)

    return render(request, 'academics/teacher_class_edit.html', {
        'form': form,
        'kelas': kelas,
        'schedule_errors': schedule_errors,
        'schedules_json': schedules_json,
    })


@role_required('TEACHER')
@require_POST
def teacher_class_delete(request, pk):
    kelas = get_object_or_404(Kelas, pk=pk, teacher=request.user, is_deleted=False)
    kelas.soft_delete()
    messages.success(request, 'Kelas berhasil dihapus.')
    return redirect('academics:teacher_classes')


# ── Student-facing views ───────────────────────────────────────────────────────

@role_required('STUDENT')
def class_browse(request):
    """Browse all OPEN classes filtered by the student's level."""
    student_level = request.user.student_profile.level
    klasses = (
        Kelas.objects
        .filter(is_deleted=False, status=KelasStatus.OPEN, level=student_level)
        .select_related('subject', 'academic_period', 'teacher')
        .prefetch_related('schedules')
        .order_by('name')
    )
    return render(request, 'academics/class_browse.html', {
        'klasses': klasses,
        'student_level': student_level,
    })


@role_required('STUDENT')
def class_detail(request, pk):
    """Class detail page for students. Shows enrollment state."""
    kelas = get_object_or_404(Kelas, pk=pk, is_deleted=False)
    from enrollments.models import Enrollment
    enrollment = Enrollment.objects.filter(
        student=request.user, kelas=kelas, is_deleted=False
    ).first()
    return render(request, 'academics/class_detail.html', {
        'kelas': kelas,
        'enrollment': enrollment,
    })


@role_required('TEACHER')
def teacher_class_students(request, pk):
    kelas = get_object_or_404(Kelas, pk=pk, teacher=request.user, is_deleted=False)
    from enrollments.models import Enrollment, EnrollmentStatus
    enrollments = (
        Enrollment.objects
        .filter(kelas=kelas, is_deleted=False)
        .select_related('student', 'student__student_profile')
        .order_by('enrolled_at')
    )
    active_count = enrollments.filter(status=EnrollmentStatus.ACTIVE).count()
    return render(request, 'academics/teacher_class_students.html', {
        'kelas': kelas,
        'enrollments': enrollments,
        'active_count': active_count,
        'EnrollmentStatus': EnrollmentStatus,
    })
