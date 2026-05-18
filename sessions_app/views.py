import datetime
import io
import json

from django.contrib import messages
from django.db import models
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from academics.models import Kelas
from accounts.decorators import role_required
from activity_logs.utils import log_activity
from enrollments.models import Enrollment, EnrollmentStatus

from .forms import SessionForm
from .models import Attendance, AttendanceStatus, BookingStatus, Session, SessionBooking, SessionStatus

_WEEKDAY_TO_DAY = ['MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY', 'SUNDAY']


@role_required('TEACHER')
def teacher_attendance_overview(request):
    """Quick-access list of all classes → click to go to sessions/attendance."""
    from django.db.models import Count
    from academics.models import KelasStatus

    today = timezone.localdate()

    klasses = list(
        Kelas.objects
        .filter(teacher_profile__user=request.user, is_deleted=False)
        .select_related('subject')
        .order_by('name')
    )
    kelas_ids = [k.pk for k in klasses]

    sessions_raw = list(
        Session.objects
        .filter(kelas_id__in=kelas_ids)
        .annotate(att_count=Count('attendances'))
        .order_by('kelas_id', '-date')
    )
    sessions_by_kelas = {}
    for s in sessions_raw:
        sessions_by_kelas.setdefault(s.kelas_id, []).append(s)

    active_rows = []
    closed_rows = []
    for kelas in klasses:
        sessions = sessions_by_kelas.get(kelas.pk, [])
        latest_session = sessions[0] if sessions else None
        incomplete_count = sum(
            1 for s in sessions
            if s.date <= today
            and s.status == SessionStatus.COMPLETED
            and s.att_count == 0
        )
        row = {
            'kelas': kelas,
            'latest_session': latest_session,
            'total_sessions': len(sessions),
            'incomplete_count': incomplete_count,
        }
        if kelas.status == KelasStatus.CLOSED:
            closed_rows.append(row)
        else:
            active_rows.append(row)

    return render(request, 'sessions_app/teacher_attendance_overview.html', {
        'active_rows': active_rows,
        'closed_rows': closed_rows,
        'today': today,
    })


@role_required('TEACHER')
def teacher_sessions(request, pk):
    from academics.utils import update_expired_classes
    update_expired_classes()

    kelas = get_object_or_404(Kelas, pk=pk, teacher_profile__user=request.user, is_deleted=False)
    today = timezone.localdate()

    sessions = list(
        Session.objects
        .filter(kelas=kelas)
        .annotate(
            attendance_count=Count('attendances', distinct=True),
            booked_count_ann=Count('bookings', filter=models.Q(bookings__status=BookingStatus.BOOKED), distinct=True),
        )
        .order_by('session_number')
    )

    # Attach matching schedule and live-status flags to each session
    schedules_by_day = {s.day: s for s in kelas.schedules.all()}
    current_time = timezone.localtime().time()
    for session in sessions:
        day_name = _WEEKDAY_TO_DAY[session.date.weekday()]
        session.schedule = schedules_by_day.get(day_name)
        # Prefer session's own stored times; fall back to class schedule
        st = session.start_time or (session.schedule.start_time if session.schedule else None)
        et = session.end_time or (session.schedule.end_time if session.schedule else None)
        if session.is_today and st and et:
            session.is_live = st <= current_time <= et
            session.is_today_upcoming = current_time < st
        else:
            session.is_live = False
            session.is_today_upcoming = False

    completed_count = sum(1 for s in sessions if s.status == SessionStatus.COMPLETED)
    created_count = len(sessions)
    can_create = created_count < kelas.total_sessions

    return render(request, 'sessions_app/teacher_sessions.html', {
        'kelas': kelas,
        'sessions': sessions,
        'completed_count': completed_count,
        'created_count': created_count,
        'can_create': can_create,
        'SessionStatus': SessionStatus,
        'today': today,
    })


@role_required('TEACHER')
def teacher_session_create(request, kelas_id):
    kelas = get_object_or_404(Kelas, pk=kelas_id, teacher_profile__user=request.user, is_deleted=False)

    # Determine next session number
    last_session = Session.objects.filter(kelas=kelas).order_by('-session_number').first()
    next_number = (last_session.session_number + 1) if last_session else 1

    # Guard: cannot exceed total_sessions
    if next_number > kelas.total_sessions:
        messages.warning(request, 'Semua pertemuan sudah dibuat.')
        return redirect('sessions_app:teacher_sessions', pk=kelas.pk)

    form = SessionForm(request.POST or None, kelas=kelas)

    if request.method == 'POST' and form.is_valid():
        session_date = form.cleaned_data['date']
        if session_date < kelas.start_date or session_date > kelas.end_date:
            form.add_error(
                'date',
                f'Tanggal harus antara {kelas.start_date.strftime("%d %b %Y")} '
                f'dan {kelas.end_date.strftime("%d %b %Y")}.',
            )
        else:
            session = form.save(commit=False)
            session.kelas = kelas
            session.session_number = next_number
            session.status = SessionStatus.SCHEDULED
            session.save()
            messages.success(request, f'Pertemuan ke-{next_number} berhasil dibuat!')
            return redirect('sessions_app:teacher_sessions', pk=kelas.pk)

    return render(request, 'sessions_app/teacher_session_create.html', {
        'kelas': kelas,
        'form': form,
        'next_number': next_number,
    })


@role_required('TEACHER')
def teacher_session_edit(request, pk):
    session = get_object_or_404(Session.objects.select_related('kelas'), pk=pk)
    if session.kelas.teacher != request.user:
        messages.error(request, 'Anda tidak memiliki akses untuk pertemuan ini.')
        return redirect('academics:teacher_classes')

    kelas = session.kelas

    form = SessionForm(request.POST or None, instance=session, kelas=kelas)

    if request.method == 'POST' and form.is_valid():
        session_date = form.cleaned_data['date']
        if session_date < kelas.start_date or session_date > kelas.end_date:
            form.add_error(
                'date',
                f'Tanggal harus antara {kelas.start_date.strftime("%d %b %Y")} '
                f'dan {kelas.end_date.strftime("%d %b %Y")}.',
            )
        else:
            form.save()
            messages.success(request, f'Pertemuan ke-{session.session_number} berhasil diperbarui!')
            return redirect('sessions_app:teacher_sessions', pk=kelas.pk)

    return render(request, 'sessions_app/teacher_session_edit.html', {
        'kelas': kelas,
        'session': session,
        'form': form,
    })


@role_required('TEACHER')
@require_POST
def teacher_session_update_status(request, pk):
    session = get_object_or_404(Session, pk=pk)

    # Ownership check: session's kelas must belong to this teacher
    if session.kelas.teacher != request.user:
        messages.error(request, 'Anda tidak memiliki akses untuk mengubah pertemuan ini.')
        return redirect('academics:teacher_classes')

    new_status = request.POST.get('status', '').strip()
    if new_status not in SessionStatus.values:
        messages.error(request, 'Status tidak valid.')
        return redirect('sessions_app:teacher_sessions', pk=session.kelas_id)

    if session.status == new_status:
        return redirect('sessions_app:teacher_sessions', pk=session.kelas_id)

    session.status = new_status
    session.save(update_fields=['status', 'updated_at'])

    if new_status == SessionStatus.CANCELLED:
        cancelled_count = SessionBooking.objects.filter(
            session=session, status=BookingStatus.BOOKED
        ).update(status=BookingStatus.CANCELLED)
        status_label = dict(SessionStatus.choices).get(new_status, new_status)
        messages.success(
            request,
            f'Pertemuan ke-{session.session_number} dibatalkan. '
            f'{cancelled_count} pemesanan siswa ikut dibatalkan.'
        )
    else:
        status_label = dict(SessionStatus.choices).get(new_status, new_status)
        messages.success(
            request,
            f'Pertemuan ke-{session.session_number} diubah menjadi {status_label}.'
        )
    return redirect('sessions_app:teacher_sessions', pk=session.kelas_id)


@role_required('TEACHER')
def teacher_attendance(request, pk):
    session = get_object_or_404(
        Session.objects.select_related('kelas__teacher_profile__user'),
        pk=pk,
    )
    if session.kelas.teacher != request.user:
        messages.error(request, 'Anda tidak memiliki akses untuk pertemuan ini.')
        return redirect('academics:teacher_classes')

    # Block marking attendance for future sessions
    today = timezone.localdate()
    if session.date > today:
        messages.error(request, 'Belum bisa mengisi absensi untuk pertemuan yang belum berlangsung.')
        return redirect('sessions_app:teacher_sessions', pk=session.kelas_id)

    # Only students who have BOOKED this session
    booked_enrollment_ids = SessionBooking.objects.filter(
        session=session, status=BookingStatus.BOOKED
    ).values_list('enrollment_id', flat=True)
    enrollments = (
        Enrollment.objects
        .filter(pk__in=booked_enrollment_ids, is_deleted=False)
        .select_related('student_profile__user')
        .order_by('student_profile__user__last_name', 'student_profile__user__first_name')
    )

    # Existing attendance records for this session (keyed by enrollment_id)
    existing = {
        a.enrollment_id: a
        for a in Attendance.objects.filter(session=session)
    }

    if request.method == 'POST':
        for enrollment in enrollments:
            key = f'attendance_{enrollment.pk}'
            raw_status = request.POST.get(key, '').strip()
            if raw_status not in AttendanceStatus.values:
                raw_status = AttendanceStatus.PRESENT  # fallback

            if enrollment.pk in existing:
                att = existing[enrollment.pk]
                if att.status != raw_status:
                    att.status = raw_status
                    att.save(update_fields=['status', 'updated_at'])
            else:
                Attendance.objects.create(
                    enrollment=enrollment,
                    session=session,
                    status=raw_status,
                )

        log_activity(request.user, 'updated', 'attendance', session.pk)

        action = request.POST.get('action', '')
        if action == 'save_and_next':
            next_session = (
                Session.objects
                .filter(kelas=session.kelas, session_number__gt=session.session_number)
                .order_by('session_number')
                .first()
            )
            if next_session:
                messages.success(
                    request,
                    f'Kehadiran disimpan! Sekarang Pertemuan ke-{next_session.session_number}.',
                )
                return redirect('sessions_app:teacher_attendance', pk=next_session.pk)
            else:
                messages.success(request, 'Semua kehadiran telah diisi!')
                return redirect('sessions_app:teacher_sessions', pk=session.kelas_id)
        else:
            messages.success(request, 'Kehadiran berhasil disimpan!')

        # Reload existing after save so pre-fill is up-to-date
        existing = {
            a.enrollment_id: a
            for a in Attendance.objects.filter(session=session)
        }

    # Build rows with pre-filled status for template
    rows = []
    for enrollment in enrollments:
        att = existing.get(enrollment.pk)
        rows.append({
            'enrollment': enrollment,
            'current_status': att.status if att else '',
        })

    # Next session (for "Simpan & Lanjut" button)
    next_session = (
        Session.objects
        .filter(kelas=session.kelas, session_number__gt=session.session_number)
        .order_by('session_number')
        .first()
    )

    # Serialize initial Alpine.js state
    statuses_json = json.dumps({
        str(row['enrollment'].pk): row['current_status']
        for row in rows
    })

    # Schedule for this session (for time display + live badge)
    schedules_by_day = {s.day: s for s in session.kelas.schedules.all()}
    day_name = _WEEKDAY_TO_DAY[session.date.weekday()]
    session_schedule = schedules_by_day.get(day_name)
    current_time = timezone.localtime().time()
    # Prefer session's own stored times; fall back to class schedule
    _st = session.start_time or (session_schedule.start_time if session_schedule else None)
    _et = session.end_time or (session_schedule.end_time if session_schedule else None)
    session_is_live = bool(
        session.date == today and _st and _et and _st <= current_time <= _et
    )

    return render(request, 'sessions_app/teacher_attendance.html', {
        'session': session,
        'kelas': session.kelas,
        'rows': rows,
        'AttendanceStatus': AttendanceStatus,
        'already_marked': bool(existing),
        'next_session': next_session,
        'statuses_json': statuses_json,
        'session_schedule': session_schedule,
        'session_is_live': session_is_live,
    })


# ─── Student booking views ────────────────────────────────────────────────────

def student_session_redirect(request, pk):
    """Resolve a bare session id to the enrollment-scoped session list (which is
    where students actually interact with it). Falls back to dashboard if the
    student isn't enrolled in that class."""
    from django.shortcuts import get_object_or_404, redirect
    from enrollments.models import Enrollment, EnrollmentStatus
    session = get_object_or_404(Session, pk=pk)
    enrollment = (
        Enrollment.objects
        .filter(
            student_profile__user=request.user,
            kelas=session.kelas,
            status=EnrollmentStatus.ACTIVE,
            is_deleted=False,
        )
        .first()
    )
    if enrollment:
        return redirect('sessions_app:student_session_list', enrollment_id=enrollment.pk)
    return redirect('dashboard:student')


@role_required('STUDENT')
def student_session_list(request, enrollment_id):
    from enrollments.models import Enrollment, EnrollmentStatus
    enrollment = get_object_or_404(
        Enrollment,
        pk=enrollment_id,
        student_profile__user=request.user,
        status=EnrollmentStatus.ACTIVE,
        is_deleted=False,
    )
    kelas = enrollment.kelas

    sessions = list(
        Session.objects
        .filter(kelas=kelas)
        .annotate(
            booked_count_ann=Count('bookings', filter=models.Q(bookings__status=BookingStatus.BOOKED), distinct=True),
        )
        .order_by('session_number')
    )

    # Build schedule lookup by day name
    schedules_by_day = {s.day: s for s in kelas.schedules.all()}

    # Map session_id → booking for this student
    my_bookings = {
        b.session_id: b
        for b in SessionBooking.objects.filter(enrollment=enrollment)
    }

    today = timezone.localdate()
    current_time = timezone.localtime().time()
    rows = []
    for session in sessions:
        booking = my_bookings.get(session.pk)
        is_booked = booking and booking.status == BookingStatus.BOOKED
        is_full = session.capacity > 0 and session.booked_count_ann >= session.capacity and not is_booked
        day_name = _WEEKDAY_TO_DAY[session.date.weekday()]
        schedule = schedules_by_day.get(day_name)
        st = session.start_time or (schedule.start_time if schedule else None)
        is_past_start = (
            session.is_today
            and st is not None
            and current_time >= st
        )
        rows.append({
            'session': session,
            'booking': booking,
            'is_booked': is_booked,
            'is_full': is_full,
            'schedule': schedule,
            'is_past_start': is_past_start,
        })

    total_booked = sum(1 for r in rows if r['is_booked'])

    # Countdown for the next booked upcoming session
    now_aware = timezone.localtime()
    next_countdown_start_ts = None
    next_countdown_end_ts = None
    for row in rows:
        if row['is_booked'] and not row['session'].is_past:
            s = row['session']
            sched = row['schedule']
            # Prefer session's own stored times; fall back to class schedule
            st = s.start_time or (sched.start_time if sched else None)
            et = s.end_time or (sched.end_time if sched else None)
            if not (st and et):
                continue
            aware_start = timezone.make_aware(datetime.datetime.combine(s.date, st))
            aware_end = timezone.make_aware(datetime.datetime.combine(s.date, et))
            if aware_end > now_aware:
                next_countdown_start_ts = int(aware_start.timestamp() * 1000)
                next_countdown_end_ts = int(aware_end.timestamp() * 1000)
                break

    return render(request, 'sessions_app/student_session_list.html', {
        'kelas': kelas,
        'enrollment': enrollment,
        'rows': rows,
        'total_booked': total_booked,
        'today': today,
        'next_countdown_start_ts': next_countdown_start_ts,
        'next_countdown_end_ts': next_countdown_end_ts,
    })


@role_required('STUDENT')
@require_POST
def student_book_session(request, enrollment_id, session_id):
    from enrollments.models import Enrollment, EnrollmentStatus
    enrollment = get_object_or_404(
        Enrollment,
        pk=enrollment_id,
        student_profile__user=request.user,
        status=EnrollmentStatus.ACTIVE,
        is_deleted=False,
    )
    session = get_object_or_404(Session, pk=session_id, kelas=enrollment.kelas)
    today = timezone.localdate()

    # Validate: cannot book past sessions
    if session.date < today:
        messages.error(request, 'Tidak bisa mendaftar pertemuan yang sudah lewat.')
        return redirect('sessions_app:student_session_list', enrollment_id=enrollment_id)

    # Validate: cannot book today's session if it has already started
    if session.date == today:
        schedules_by_day = {s.day: s for s in enrollment.kelas.schedules.all()}
        day_name = _WEEKDAY_TO_DAY[session.date.weekday()]
        schedule = schedules_by_day.get(day_name)
        st = session.start_time or (schedule.start_time if schedule else None)
        if st and timezone.localtime().time() >= st:
            messages.error(request, 'Pertemuan sudah dimulai, tidak bisa mendaftar.')
            return redirect('sessions_app:student_session_list', enrollment_id=enrollment_id)

    # Validate: cannot book cancelled sessions
    if session.status == SessionStatus.CANCELLED:
        messages.error(request, 'Pertemuan ini sudah dibatalkan.')
        return redirect('sessions_app:student_session_list', enrollment_id=enrollment_id)

    # Pre-check capacity before attempting create
    if session.capacity > 0:
        already_booked = SessionBooking.objects.filter(
            session=session, status=BookingStatus.BOOKED
        ).count()
        # Check if student already has an active booking (exclude from count)
        student_has_booking = SessionBooking.objects.filter(
            enrollment=enrollment, session=session, status=BookingStatus.BOOKED
        ).exists()
        if not student_has_booking and already_booked >= session.capacity:
            messages.error(request, 'Maaf, pertemuan ini sudah penuh.')
            return redirect('sessions_app:student_session_list', enrollment_id=enrollment_id)

    booking, created = SessionBooking.objects.get_or_create(
        enrollment=enrollment,
        session=session,
        defaults={'status': BookingStatus.BOOKED},
    )

    if not created:
        if booking.status == BookingStatus.CANCELLED:
            booking.status = BookingStatus.BOOKED
            booking.save(update_fields=['status', 'updated_at'])
            messages.success(request, f'Berhasil mendaftar ke Pertemuan ke-{session.session_number}!')
        else:
            messages.info(request, 'Kamu sudah terdaftar di pertemuan ini.')
    else:
        # Race-condition guard: re-check after insert
        booked = SessionBooking.objects.filter(session=session, status=BookingStatus.BOOKED).count()
        if session.capacity > 0 and booked > session.capacity:
            booking.status = BookingStatus.CANCELLED
            booking.save(update_fields=['status', 'updated_at'])
            messages.error(request, 'Maaf, pertemuan ini sudah penuh.')
        else:
            messages.success(request, f'Berhasil mendaftar ke Pertemuan ke-{session.session_number}!')

    return redirect('sessions_app:student_session_list', enrollment_id=enrollment_id)


@role_required('STUDENT')
@require_POST
def student_cancel_booking(request, enrollment_id, session_id):
    from enrollments.models import Enrollment, EnrollmentStatus
    enrollment = get_object_or_404(
        Enrollment,
        pk=enrollment_id,
        student_profile__user=request.user,
        status=EnrollmentStatus.ACTIVE,
        is_deleted=False,
    )
    session = get_object_or_404(Session, pk=session_id, kelas=enrollment.kelas)
    today = timezone.localdate()

    # Cannot cancel today's or past sessions
    if session.date <= today:
        messages.error(request, 'Tidak bisa membatalkan pertemuan yang sudah berlangsung atau hari ini.')
        return redirect('sessions_app:student_session_list', enrollment_id=enrollment_id)

    booking = SessionBooking.objects.filter(enrollment=enrollment, session=session).first()
    if booking and booking.status == BookingStatus.BOOKED:
        booking.status = BookingStatus.CANCELLED
        booking.save(update_fields=['status', 'updated_at'])
        messages.success(request, f'Pendaftaran Pertemuan ke-{session.session_number} dibatalkan.')
    else:
        messages.info(request, 'Tidak ada pendaftaran aktif untuk pertemuan ini.')

    return redirect('sessions_app:student_session_list', enrollment_id=enrollment_id)


# ─── Attendance exports ────────────────────────────────────────────────────────

def _build_attendance_data(kelas):
    """Return (sessions, enrollments, att_map) for export views."""
    sessions = list(Session.objects.filter(kelas=kelas).order_by('session_number'))
    enrollments = list(
        Enrollment.objects
        .filter(kelas=kelas, status=EnrollmentStatus.ACTIVE, is_deleted=False)
        .select_related('student_profile__user')
        .order_by('student_profile__user__last_name', 'student_profile__user__first_name')
    )
    att_map = {
        (a.enrollment_id, a.session_id): a.status
        for a in Attendance.objects.filter(session__kelas=kelas)
    }
    return sessions, enrollments, att_map


def _attendance_row(enrollment, sessions, att_map):
    """Return (cells_list, present, permitted, absent) for one student."""
    cells = []
    present = permitted = absent = 0
    for session in sessions:
        status = att_map.get((enrollment.pk, session.pk))
        if status == AttendanceStatus.PRESENT:
            cells.append('H')
            present += 1
        elif status == AttendanceStatus.PERMITTED:
            cells.append('I')
            permitted += 1
        elif status == AttendanceStatus.ABSENT:
            cells.append('A')
            absent += 1
        else:
            cells.append('-')
    return cells, present, permitted, absent


@role_required('TEACHER')
def export_attendance_excel(request, pk):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment

    kelas = get_object_or_404(Kelas, pk=pk, teacher_profile__user=request.user, is_deleted=False)
    sessions, enrollments, att_map = _build_attendance_data(kelas)

    wb = Workbook()
    ws = wb.active
    ws.title = 'Kehadiran'

    header_fill = PatternFill('solid', fgColor='4F46E5')
    header_font = Font(bold=True, color='FFFFFF', size=10)
    center = Alignment(horizontal='center', vertical='center')

    # Header
    headers = ['No', 'Nama Siswa']
    for s in sessions:
        headers.append(f'P{s.session_number}')
    headers += ['Total H', 'Total I', 'Total A', '% Hadir']
    ws.append(headers)

    # Style header row
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center

    # Data rows
    for i, enrollment in enumerate(enrollments, 1):
        cells, present, permitted, absent = _attendance_row(enrollment, sessions, att_map)
        total_marked = present + permitted + absent
        pct = f'{round((present + permitted) / total_marked * 100)}%' if total_marked else '-'
        row = [i, enrollment.student.get_full_name()] + cells + [present, permitted, absent, pct]
        ws.append(row)

    # Column widths
    ws.column_dimensions['A'].width = 5
    ws.column_dimensions['B'].width = 28
    for col_idx in range(3, 3 + len(sessions)):
        col_letter = ws.cell(row=1, column=col_idx).column_letter
        ws.column_dimensions[col_letter].width = 5
    for offset in range(4):
        col_letter = ws.cell(row=1, column=3 + len(sessions) + offset).column_letter
        ws.column_dimensions[col_letter].width = 10

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    safe_name = kelas.name.replace(' ', '_').replace('/', '-')
    date_str = timezone.localdate().strftime('%Y%m%d')
    filename = f'Kehadiran_{safe_name}_{date_str}.xlsx'
    response = HttpResponse(
        output.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@role_required('TEACHER')
def export_attendance_pdf(request, pk):
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    kelas = get_object_or_404(Kelas, pk=pk, teacher_profile__user=request.user, is_deleted=False)
    sessions, enrollments, att_map = _build_attendance_data(kelas)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(A4),
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
    )
    styles = getSampleStyleSheet()

    def para(text, style='Normal', **kwargs):
        s = ParagraphStyle('_', parent=styles[style], **kwargs)
        return Paragraph(text, s)

    teacher_name = kelas.teacher.get_full_name() if kelas.teacher else '-'
    period_name = kelas.academic_period.name if kelas.academic_period_id else '-'

    elements = [
        para(f'Laporan Kehadiran — {kelas.name}', 'Heading1', fontSize=14, alignment=1),
        Spacer(1, 0.2 * cm),
        para(
            f'{kelas.subject.name}  ·  Guru: {teacher_name}  ·  Periode: {period_name}',
            fontSize=9, alignment=1,
        ),
        Spacer(1, 0.5 * cm),
    ]

    header = ['No', 'Nama Siswa'] + [f'P{s.session_number}' for s in sessions] + ['H', 'I', 'A', '%']
    data = [header]

    for i, enrollment in enumerate(enrollments, 1):
        cells, present, permitted, absent = _attendance_row(enrollment, sessions, att_map)
        total_marked = present + permitted + absent
        pct = f'{round((present + permitted) / total_marked * 100)}%' if total_marked else '-'
        data.append([str(i), enrollment.student.get_full_name()] + cells + [str(present), str(permitted), str(absent), pct])

    indent_col = colors.HexColor('#4F46E5')
    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), indent_col),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (1, 1), (1, -1), 'LEFT'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F9FAFB')]),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#E5E7EB')),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 0.5 * cm))
    elements.append(para(
        f'Dicetak: {timezone.localdate().strftime("%d %B %Y")}',
        fontSize=7, alignment=2,
    ))

    doc.build(elements)
    buffer.seek(0)

    safe_name = kelas.name.replace(' ', '_').replace('/', '-')
    date_str = timezone.localdate().strftime('%Y%m%d')
    filename = f'Kehadiran_{safe_name}_{date_str}.pdf'
    response = HttpResponse(buffer.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
