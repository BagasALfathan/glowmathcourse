import datetime as _dt
import json
from types import SimpleNamespace

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from accounts.models import ApprovalStatus, Role
from activity_logs.utils import log_activity
from enrollments.models import Enrollment, EnrollmentStatus
from ratings.models import Rating
from sessions_app.models import BookingStatus, Session, SessionBooking, SessionStatus
from .forms import KelasEditForm, KelasForm
from .models import Day, Kelas, KelasStatus, Schedule, Subject
from .utils import (
    update_expired_classes,
    build_schedule_grid, build_calendar_grid, _COLOR_PALETTE, _SCHEDULE_DAYS,
)

_WEEKDAY_TO_DAY = {
    0: 'MONDAY', 1: 'TUESDAY', 2: 'WEDNESDAY',
    3: 'THURSDAY', 4: 'FRIDAY', 5: 'SATURDAY', 6: 'SUNDAY',
}


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
    from datetime import datetime as dt
    errors = []
    if not rows:
        errors.append('Minimal satu jadwal harus ditambahkan.')
        return errors
    seen_days = set()
    for idx, s in enumerate(rows, start=1):
        if not s['day']:
            errors.append(f'Jadwal {idx}: Hari wajib dipilih.')
        else:
            if s['day'] in seen_days:
                errors.append(f'Jadwal {idx}: Hari {s["day"]} sudah digunakan jadwal lain.')
            seen_days.add(s['day'])
        if not s['start_time']:
            errors.append(f'Jadwal {idx}: Jam mulai wajib diisi.')
        if not s['end_time']:
            errors.append(f'Jadwal {idx}: Jam selesai wajib diisi.')
        elif s['start_time'] and s['end_time']:
            try:
                t_start = dt.strptime(s['start_time'], '%H:%M').time()
                t_end = dt.strptime(s['end_time'], '%H:%M').time()
                if t_start >= t_end:
                    errors.append(f'Jadwal {idx}: Jam selesai harus lebih besar dari jam mulai.')
            except ValueError:
                errors.append(f'Jadwal {idx}: Format waktu tidak valid.')
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


def _check_teacher_schedule_conflicts(teacher, new_schedules, exclude_kelas_id=None):
    """Return error strings for any new_schedule that overlaps an existing teacher schedule."""
    from datetime import datetime as _dt_cls
    errors = []
    qs = Schedule.objects.filter(
        kelas__teacher=teacher, kelas__is_deleted=False,
    ).select_related('kelas')
    if exclude_kelas_id:
        qs = qs.exclude(kelas_id=exclude_kelas_id)
    existing = list(qs)

    for new_s in new_schedules:
        day = new_s.get('day', '')
        s_str = new_s.get('start_time', '')
        e_str = new_s.get('end_time', '')
        if not (day and s_str and e_str):
            continue
        try:
            s_new = _dt_cls.strptime(s_str, '%H:%M').time()
            e_new = _dt_cls.strptime(e_str, '%H:%M').time()
        except ValueError:
            continue
        for ex in existing:
            if ex.day != day:
                continue
            if s_new < ex.end_time and e_new > ex.start_time:
                day_label = dict([(d, l) for d, l in [
                    ('MONDAY', 'Senin'), ('TUESDAY', 'Selasa'), ('WEDNESDAY', 'Rabu'),
                    ('THURSDAY', 'Kamis'), ('FRIDAY', 'Jumat'), ('SATURDAY', 'Sabtu'),
                ]]).get(day, day)
                errors.append(
                    f'Jadwal {day_label} ({s_str}–{e_str}) bertabrakan dengan '
                    f'kelas "{ex.kelas.name}" '
                    f'({ex.start_time.strftime("%H:%M")}–{ex.end_time.strftime("%H:%M")}).'
                )
    return errors


# ── Views ──────────────────────────────────────────────────────────────────────

@role_required('TEACHER')
def teacher_classes_list(request):
    update_expired_classes()
    today = timezone.localdate()
    qs = (
        Kelas.objects
        .filter(teacher=request.user, is_deleted=False)
        .select_related('subject', 'academic_period')
        .prefetch_related('schedules')
        .annotate(
            session_count=Count('sessions', distinct=True),
            completed_session_count=Count(
                'sessions',
                filter=Q(sessions__status=SessionStatus.COMPLETED),
                distinct=True,
            ),
        )
        .order_by('name')
    )

    active_klasses = []
    closed_klasses = []
    for kelas in qs:
        ready = (
            kelas.session_count >= kelas.total_sessions
            and kelas.completed_session_count >= kelas.total_sessions
            and kelas.total_sessions > 0
        )
        kelas.can_complete = ready
        if kelas.status == KelasStatus.CLOSED:
            closed_klasses.append(kelas)
        else:
            active_klasses.append(kelas)

    deleted_klasses = list(
        Kelas.objects
        .filter(teacher=request.user, is_deleted=True)
        .select_related('subject', 'academic_period')
        .prefetch_related('schedules')
        .order_by('-deleted_at')
    )

    return render(request, 'academics/teacher_classes.html', {
        'active_klasses': active_klasses,
        'closed_klasses': closed_klasses,
        'deleted_klasses': deleted_klasses,
        'KelasStatus': KelasStatus,
        'today': today,
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
            conflict_errors = _check_teacher_schedule_conflicts(request.user, posted_schedules)
            if conflict_errors:
                schedule_errors = conflict_errors
            else:
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
                log_activity(request.user, 'created', 'kelas', kelas.pk)
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
            conflict_errors = _check_teacher_schedule_conflicts(
                request.user, posted_schedules, exclude_kelas_id=kelas.pk
            )
            if conflict_errors:
                schedule_errors = conflict_errors
            else:
                with transaction.atomic():
                    form.save()
                    kelas.schedules.all().delete()
                    for s in posted_schedules:
                        Schedule.objects.create(
                            kelas=kelas, day=s['day'],
                            start_time=s['start_time'], end_time=s['end_time'],
                            room=s['room'],
                        )
                log_activity(request.user, 'updated', 'kelas', kelas.pk)
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
    kelas_pk = kelas.pk
    kelas.soft_delete()
    log_activity(request.user, 'deleted', 'kelas', kelas_pk)
    messages.success(request, 'Kelas berhasil dihapus.')
    return redirect('academics:teacher_classes')


@role_required('TEACHER')
@require_POST
def teacher_complete_class(request, pk):
    kelas = get_object_or_404(Kelas, pk=pk, teacher=request.user, is_deleted=False)
    if kelas.status == KelasStatus.CLOSED:
        messages.info(request, 'Kelas ini sudah selesai.')
        return redirect('academics:teacher_classes')
    session_count = Session.objects.filter(kelas=kelas).count()
    completed_count = Session.objects.filter(kelas=kelas, status=SessionStatus.COMPLETED).count()
    if session_count < kelas.total_sessions or completed_count < kelas.total_sessions:
        messages.error(request, 'Selesaikan semua pertemuan terlebih dahulu sebelum menutup kelas.')
        return redirect('academics:teacher_classes')
    with transaction.atomic():
        kelas.status = KelasStatus.CLOSED
        kelas.save(update_fields=['status', 'updated_at'])
        Enrollment.objects.filter(
            kelas=kelas, status=EnrollmentStatus.ACTIVE, is_deleted=False
        ).update(status=EnrollmentStatus.COMPLETED)
    log_activity(request.user, 'updated', 'kelas', kelas.pk)
    messages.success(request, 'Kelas berhasil diselesaikan! Siswa sekarang dapat memberikan rating.')
    return redirect('academics:teacher_classes')


# ── Student-facing views ───────────────────────────────────────────────────────

@role_required('STUDENT')
def class_browse(request):
    """Browse all OPEN classes filtered by the student's level."""
    update_expired_classes()
    student_level = request.user.student_profile.level
    subjects = Subject.objects.filter(is_active=True).order_by('name')
    days = Day.choices
    return render(request, 'academics/class_browse.html', {
        'student_level': student_level,
        'subjects': subjects,
        'days': days,
    })


@role_required('STUDENT')
def class_browse_partial(request):
    """HTMX partial: filtered class grid. Hides expired classes."""
    today = timezone.localdate()
    student_level = request.user.student_profile.level
    subject_filter = request.GET.get('subject', '')
    day_filter = request.GET.get('day', '')

    qs = (
        Kelas.objects
        .filter(
            is_deleted=False,
            status=KelasStatus.OPEN,
            level=student_level,
            end_date__gte=today,
        )
        .select_related('subject', 'academic_period', 'teacher')
        .prefetch_related('schedules')
        .order_by('name')
    )
    if subject_filter:
        qs = qs.filter(subject_id=subject_filter)
    if day_filter:
        qs = qs.filter(schedules__day=day_filter).distinct()

    return render(request, 'academics/_class_browse_grid.html', {
        'klasses': qs,
        'today': today,
        'student_level': student_level,
        'subject_filter': subject_filter,
        'day_filter': day_filter,
    })


@role_required('STUDENT')
def class_detail(request, pk):
    """Class detail page for students. Shows enrollment state."""
    from django.db.models import Avg, Count
    kelas = get_object_or_404(Kelas, pk=pk, is_deleted=False)
    from enrollments.models import Enrollment
    enrollment = Enrollment.objects.filter(
        student=request.user, kelas=kelas, is_deleted=False
    ).first()
    from ratings.models import Rating
    rating_data = Rating.objects.filter(
        enrollment__kelas=kelas,
        enrollment__is_deleted=False,
    ).aggregate(avg=Avg('score'), count=Count('id'))
    rating_avg = round(rating_data['avg'], 1) if rating_data['avg'] else None
    return render(request, 'academics/class_detail.html', {
        'kelas': kelas,
        'enrollment': enrollment,
        'rating_avg': rating_avg,
        'rating_count': rating_data['count'],
    })


@role_required('TEACHER')
def teacher_class_students(request, pk):
    kelas = get_object_or_404(Kelas, pk=pk, teacher=request.user, is_deleted=False)
    from enrollments.models import Enrollment, EnrollmentStatus
    all_enrollments = list(
        Enrollment.objects
        .filter(kelas=kelas, is_deleted=False)
        .select_related('student', 'student__student_profile')
        .order_by('enrolled_at')
    )
    active_enrollments = [e for e in all_enrollments if e.status == EnrollmentStatus.ACTIVE]
    completed_enrollments = [e for e in all_enrollments if e.status == EnrollmentStatus.COMPLETED]
    dropped_enrollments = [e for e in all_enrollments if e.status == EnrollmentStatus.DROPPED]
    return render(request, 'academics/teacher_class_students.html', {
        'kelas': kelas,
        'active_enrollments': active_enrollments,
        'completed_enrollments': completed_enrollments,
        'dropped_enrollments': dropped_enrollments,
        'active_count': len(active_enrollments),
        'EnrollmentStatus': EnrollmentStatus,
    })


# ── Schedule views ────────────────────────────────────────────────────────────

def _student_schedule_ctx(user):
    active_enrollments = (
        Enrollment.objects
        .filter(student=user, status=EnrollmentStatus.ACTIVE, is_deleted=False)
        .select_related('kelas__subject__category', 'kelas__teacher')
        .prefetch_related('kelas__schedules')
    )
    items = []
    for enrollment in active_enrollments:
        kelas = enrollment.kelas
        color = _COLOR_PALETTE[kelas.subject.category_id % len(_COLOR_PALETTE)]
        for sched in kelas.schedules.all():
            items.append({'schedule': sched, 'kelas': kelas, 'color': color})
    grid_rows, days_list = build_schedule_grid(items)
    return {
        'grid_rows': grid_rows,
        'days_list': days_list,
        'days': _SCHEDULE_DAYS,
        'view_role': 'student',
        'total_classes': active_enrollments.count(),
        'user': user,
        **build_calendar_grid(items),
    }


@role_required('STUDENT')
def student_schedule_redirect(request):
    return redirect('academics:student_schedule_classes')


@role_required('STUDENT')
def student_schedule(request):
    return render(request, 'academics/student_schedule.html',
                  _student_schedule_ctx(request.user))


@role_required('STUDENT')
def student_schedule_classes(request):
    return render(request, 'academics/student_schedule.html',
                  _student_schedule_ctx(request.user))


@role_required('STUDENT')
def student_schedule_print(request):
    return render(request, 'academics/student_schedule_print.html',
                  _student_schedule_ctx(request.user))


@role_required('STUDENT')
def student_schedule_sessions(request):
    """Session-based weekly schedule for students."""
    today = timezone.localdate()
    week_param = request.GET.get('week', 'current')
    week_start = today - _dt.timedelta(days=today.weekday())
    if week_param == 'next':
        week_start += _dt.timedelta(days=7)
    elif week_param == 'prev':
        week_start -= _dt.timedelta(days=7)
    week_end = week_start + _dt.timedelta(days=5)

    active_enrollments = list(
        Enrollment.objects
        .filter(student=request.user, status=EnrollmentStatus.ACTIVE, is_deleted=False)
        .select_related('kelas__subject__category', 'kelas__teacher')
        .prefetch_related('kelas__schedules')
    )
    kelas_ids = [e.kelas_id for e in active_enrollments]
    enrollment_ids = [e.pk for e in active_enrollments]

    sessions = list(
        Session.objects
        .filter(kelas_id__in=kelas_ids, date__range=(week_start, week_end))
        .exclude(status=SessionStatus.CANCELLED)
        .select_related('kelas__subject__category')
        .prefetch_related('kelas__schedules')
        .order_by('date', 'start_time')
    ) if kelas_ids else []

    booked_ids = set(
        SessionBooking.objects
        .filter(enrollment_id__in=enrollment_ids, status=BookingStatus.BOOKED)
        .values_list('session_id', flat=True)
    ) if enrollment_ids else set()

    kelas_color = {
        e.kelas_id: _COLOR_PALETTE[e.kelas.subject.category_id % len(_COLOR_PALETTE)]
        for e in active_enrollments
    }

    items = []
    for s in sessions:
        day_str = _WEEKDAY_TO_DAY.get(s.date.weekday())
        start_t = s.start_time
        end_t = s.end_time
        if not start_t:
            sched = s.kelas.schedules.filter(day=day_str).first()
            if sched:
                start_t, end_t = sched.start_time, sched.end_time
            else:
                continue
        proxy = SimpleNamespace(day=day_str, start_time=start_t, end_time=end_t, room='')
        items.append({
            'schedule': proxy,
            'kelas': s.kelas,
            'session': s,
            'color': kelas_color.get(s.kelas_id, _COLOR_PALETTE[0]),
            'is_booked': s.pk in booked_ids,
        })

    grid_rows, days_list = build_schedule_grid(items)
    return render(request, 'academics/student_schedule_sessions.html', {
        'grid_rows': grid_rows,
        'days_list': days_list,
        'days': _SCHEDULE_DAYS,
        'view_role': 'student',
        'week_start': week_start,
        'week_end': week_end,
        'week_param': week_param,
        'total_sessions': len(sessions),
        **build_calendar_grid(items),
    })


def _teacher_schedule_ctx(user):
    import datetime as _dt
    _WDAY = ['MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY', 'SUNDAY']

    active_klasses = list(
        Kelas.objects
        .filter(teacher=user, is_deleted=False,
                status__in=[KelasStatus.OPEN, KelasStatus.FULL])
        .select_related('subject__category')
        .prefetch_related('schedules')
        .annotate(enrolled_count=Count(
            'enrollments',
            filter=Q(enrollments__status=EnrollmentStatus.ACTIVE,
                     enrollments__is_deleted=False),
        ))
    )

    # Load this week's sessions for all active classes
    today = timezone.localdate()
    week_start = today - _dt.timedelta(days=today.weekday())   # Monday
    week_end = week_start + _dt.timedelta(days=5)              # Saturday
    kelas_ids = [k.pk for k in active_klasses]
    week_sessions = list(
        Session.objects.filter(
            kelas_id__in=kelas_ids,
            date__range=(week_start, week_end),
        ).exclude(status=SessionStatus.CANCELLED)
        .order_by('date', 'start_time')
    ) if kelas_ids else []

    sessions_by_kelas_day = {}
    for s in week_sessions:
        day_name = _WDAY[s.date.weekday()]
        sessions_by_kelas_day.setdefault((s.kelas_id, day_name), []).append(s)

    items = []
    for kelas in active_klasses:
        color = _COLOR_PALETTE[kelas.subject.category_id % len(_COLOR_PALETTE)]
        for sched in kelas.schedules.all():
            items.append({
                'schedule': sched,
                'kelas': kelas,
                'color': color,
                'enrolled_count': kelas.enrolled_count,
                'sessions': sessions_by_kelas_day.get((kelas.pk, sched.day), []),
            })
    grid_rows, days_list = build_schedule_grid(items)
    return {
        'grid_rows': grid_rows,
        'days_list': days_list,
        'days': _SCHEDULE_DAYS,
        'view_role': 'teacher',
        'total_classes': len(active_klasses),
        'user': user,
        **build_calendar_grid(items),
    }


@role_required('TEACHER')
def teacher_schedule_redirect(request):
    return redirect('academics:teacher_schedule_classes')


@role_required('TEACHER')
def teacher_schedule(request):
    return render(request, 'academics/teacher_schedule.html',
                  _teacher_schedule_ctx(request.user))


@role_required('TEACHER')
def teacher_schedule_classes(request):
    return render(request, 'academics/teacher_schedule.html',
                  _teacher_schedule_ctx(request.user))


@role_required('TEACHER')
def teacher_schedule_print(request):
    return render(request, 'academics/teacher_schedule_print.html',
                  _teacher_schedule_ctx(request.user))


@role_required('TEACHER')
def teacher_schedule_sessions(request):
    """Session-based weekly schedule for teachers."""
    today = timezone.localdate()
    week_param = request.GET.get('week', 'current')
    week_start = today - _dt.timedelta(days=today.weekday())
    if week_param == 'next':
        week_start += _dt.timedelta(days=7)
    elif week_param == 'prev':
        week_start -= _dt.timedelta(days=7)
    week_end = week_start + _dt.timedelta(days=5)

    active_klasses = list(
        Kelas.objects
        .filter(teacher=request.user, is_deleted=False,
                status__in=[KelasStatus.OPEN, KelasStatus.FULL])
        .select_related('subject__category')
        .prefetch_related('schedules')
        .annotate(enrolled_count=Count(
            'enrollments',
            filter=Q(enrollments__status=EnrollmentStatus.ACTIVE,
                     enrollments__is_deleted=False),
        ))
    )
    kelas_ids = [k.pk for k in active_klasses]
    kelas_map = {k.pk: k for k in active_klasses}
    kelas_color = {
        k.pk: _COLOR_PALETTE[k.subject.category_id % len(_COLOR_PALETTE)]
        for k in active_klasses
    }

    sessions = list(
        Session.objects
        .filter(kelas_id__in=kelas_ids, date__range=(week_start, week_end))
        .exclude(status=SessionStatus.CANCELLED)
        .select_related('kelas__subject__category')
        .prefetch_related('kelas__schedules')
        .annotate(booked_count=Count(
            'bookings',
            filter=Q(bookings__status=BookingStatus.BOOKED),
        ))
        .order_by('date', 'start_time')
    ) if kelas_ids else []

    items = []
    for s in sessions:
        kelas = kelas_map.get(s.kelas_id) or s.kelas
        day_str = _WEEKDAY_TO_DAY.get(s.date.weekday())
        start_t = s.start_time
        end_t = s.end_time
        if not start_t:
            sched = kelas.schedules.filter(day=day_str).first()
            if sched:
                start_t, end_t = sched.start_time, sched.end_time
            else:
                continue
        proxy = SimpleNamespace(day=day_str, start_time=start_t, end_time=end_t, room='')
        items.append({
            'schedule': proxy,
            'kelas': kelas,
            'session': s,
            'color': kelas_color.get(s.kelas_id, _COLOR_PALETTE[0]),
            'enrolled_count': getattr(kelas, 'enrolled_count', 0),
        })

    grid_rows, days_list = build_schedule_grid(items)
    return render(request, 'academics/teacher_schedule_sessions.html', {
        'grid_rows': grid_rows,
        'days_list': days_list,
        'days': _SCHEDULE_DAYS,
        'view_role': 'teacher',
        'week_start': week_start,
        'week_end': week_end,
        'week_param': week_param,
        'total_sessions': len(sessions),
        **build_calendar_grid(items),
    })


# ── Public teacher directory ───────────────────────────────────────────────────

def _teacher_qs():
    """Base queryset for approved teachers with rating + class count annotations."""
    from accounts.models import User as UserModel
    return (
        UserModel.objects
        .filter(role=Role.TEACHER, is_active=True, is_deleted=False,
                approval_status=ApprovalStatus.APPROVED)
        .select_related('teacher_profile')
        .annotate(
            rating_avg=Avg(
                'taught_classes__enrollments__rating__score',
                filter=Q(
                    taught_classes__is_deleted=False,
                    taught_classes__enrollments__is_deleted=False,
                ),
            ),
            rating_count=Count(
                'taught_classes__enrollments__rating',
                filter=Q(
                    taught_classes__is_deleted=False,
                    taught_classes__enrollments__is_deleted=False,
                ),
                distinct=True,
            ),
            open_class_count=Count(
                'taught_classes',
                filter=Q(
                    taught_classes__is_deleted=False,
                    taught_classes__status=KelasStatus.OPEN,
                ),
                distinct=True,
            ),
        )
        .order_by('first_name', 'last_name')
    )


@login_required
def teacher_list(request):
    """Teacher directory — grid of all approved teachers."""
    specializations = (
        list(
            __import__('accounts').models.TeacherProfile.objects
            .exclude(specialization='')
            .values_list('specialization', flat=True)
            .distinct()
            .order_by('specialization')
        )
    )
    return render(request, 'academics/teacher_list.html', {
        'specializations': specializations,
    })


@login_required
def teacher_list_partial(request):
    """HTMX partial: filtered teacher grid."""
    q = request.GET.get('q', '').strip()
    spec_filter = request.GET.get('specialization', '').strip()

    qs = _teacher_qs()
    if q:
        qs = qs.filter(
            Q(first_name__icontains=q) | Q(last_name__icontains=q)
        )
    if spec_filter:
        qs = qs.filter(teacher_profile__specialization__icontains=spec_filter)

    return render(request, 'academics/_teacher_list_grid.html', {
        'teachers': qs,
        'q': q,
        'spec_filter': spec_filter,
    })


@login_required
def teacher_profile(request, pk):
    """Public teacher profile — info + open classes."""
    from accounts.models import User as UserModel
    teacher = get_object_or_404(
        UserModel,
        pk=pk, role=Role.TEACHER, is_active=True, is_deleted=False,
        approval_status=ApprovalStatus.APPROVED,
    )

    try:
        profile = teacher.teacher_profile
    except Exception:
        profile = None

    rating_data = Rating.objects.filter(
        enrollment__kelas__teacher=teacher,
        enrollment__is_deleted=False,
    ).aggregate(avg=Avg('score'), count=Count('id'))
    rating_avg = round(rating_data['avg'], 1) if rating_data['avg'] else None

    open_classes = (
        Kelas.objects
        .filter(teacher=teacher, is_deleted=False, status=KelasStatus.OPEN)
        .select_related('subject', 'academic_period')
        .prefetch_related('schedules')
        .order_by('name')
    )

    viewer_is_student = request.user.role == Role.STUDENT

    return render(request, 'academics/teacher_profile.html', {
        'teacher': teacher,
        'profile': profile,
        'rating_avg': rating_avg,
        'rating_count': rating_data['count'],
        'open_classes': open_classes,
        'viewer_is_student': viewer_is_student,
    })
