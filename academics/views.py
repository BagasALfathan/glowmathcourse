import datetime as _dt
import json
from datetime import timedelta
from types import SimpleNamespace

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Avg, Count, F, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from accounts.models import ApprovalStatus, Level, Role, TeacherJenjang
from activity_logs.utils import log_activity
from enrollments.models import Enrollment, EnrollmentStatus
from ratings.models import TeacherRating
from sessions_app.models import BookingStatus, Session, SessionBooking, SessionStatus
from .forms import KelasEditForm, KelasForm
from .models import (
    AcademicPeriod, Day, Kelas, KelasJenjang, KelasStatus, KelasType,
    Schedule, Subject,
)
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
        kelas__teacher_profile__user=teacher, kelas__is_deleted=False,
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
        .filter(teacher_profile__user=request.user, is_deleted=False)
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
        .filter(teacher_profile__user=request.user, is_deleted=True)
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
    """Create a weekly-slot kelas.

    Domain model: a kelas is one recurring weekly slot. The teacher picks Hari,
    Jam mulai, Jam selesai, Tanggal mulai, Jumlah minggu (= total_sessions),
    Ruangan (optional), plus the usual identity fields. On save we create the
    Kelas, the single Schedule row, then call generate_sessions_for_kelas() so
    end_date and the Session rows are both derived from the slot.
    """
    from decimal import Decimal
    from sessions_app.services import (
        generate_sessions_for_kelas, teacher_weekly_slot_conflict,
    )

    teacher_profile = request.user.teacher_profile

    active_period = AcademicPeriod.objects.filter(is_active=True).first()
    all_periods = AcademicPeriod.objects.all().order_by('-is_active', '-start_date')
    subjects = (
        Subject.objects.filter(is_active=True)
        .select_related('category')
        .order_by('name')
    )
    teacher_levels = list(
        TeacherJenjang.objects
        .filter(teacher_profile=teacher_profile)
        .values_list('level', flat=True)
        .order_by('level')
    )

    # Day.choices excludes Sunday in this project; honor the same set in the UI.
    day_choices = [(v, label) for v, label in Day.choices if v != 'SUNDAY']
    valid_days = {v for v, _ in day_choices}

    if request.method == 'POST':
        name = (request.POST.get('name') or '').strip()
        subject_id = request.POST.get('subject')
        period_id = request.POST.get('academic_period')
        # Multi-jenjang: accept either a single `level` or many `levels[]`.
        levels_raw = (
            request.POST.getlist('levels')
            or [v for v in [request.POST.get('level')] if v]
        )
        # De-dup while preserving order, drop blanks
        levels_picked = [
            v for v in dict.fromkeys(levels_raw) if v
        ]
        class_type = (request.POST.get('class_type') or KelasType.REGULAR).strip().upper()
        if class_type not in {v for v, _ in KelasType.choices}:
            class_type = KelasType.REGULAR
        description = (request.POST.get('description') or '').strip()
        start_date_raw = request.POST.get('start_date') or ''
        day = (request.POST.get('day') or '').strip().upper()
        start_time_raw = request.POST.get('start_time') or ''
        end_time_raw = request.POST.get('end_time') or ''
        room = (request.POST.get('room') or '').strip()

        errors = []
        if not name:
            errors.append('Nama kelas wajib diisi.')
        if not subject_id:
            errors.append('Pilih mata pelajaran.')
        if not period_id:
            errors.append('Pilih periode akademik.')
        if not levels_picked:
            errors.append('Pilih minimal satu jenjang.')
        else:
            invalid_levels = [
                v for v in levels_picked if v not in {lv for lv, _ in Level.choices}
            ]
            if invalid_levels:
                errors.append('Jenjang tidak valid: ' + ', '.join(invalid_levels) + '.')
            elif teacher_levels:
                out_of_scope = [v for v in levels_picked if v not in teacher_levels]
                if out_of_scope:
                    errors.append(
                        'Jenjang ' + ', '.join(out_of_scope) + ' belum terdaftar di profil Anda. '
                        'Tambahkan di Pengaturan dulu.'
                    )

        # Parse the slot fields
        start_date_parsed = None
        try:
            start_date_parsed = _dt.datetime.strptime(start_date_raw, '%Y-%m-%d').date()
        except ValueError:
            errors.append('Tanggal mulai wajib diisi.')

        if day not in valid_days:
            errors.append('Pilih hari pertemuan (Senin sampai Sabtu).')

        start_time_parsed = None
        end_time_parsed = None
        try:
            start_time_parsed = _dt.datetime.strptime(start_time_raw[:5], '%H:%M').time()
        except ValueError:
            errors.append('Jam mulai wajib diisi.')
        try:
            end_time_parsed = _dt.datetime.strptime(end_time_raw[:5], '%H:%M').time()
        except ValueError:
            errors.append('Jam selesai wajib diisi.')
        if start_time_parsed and end_time_parsed and end_time_parsed <= start_time_parsed:
            errors.append('Jam selesai harus setelah jam mulai.')

        # Capacity rules per class_type:
        #   PRIVAT       -> forced to 1
        #   GROUP        -> teacher chooses (required input)
        #   GANJIL_GENAP -> forced to 2
        if class_type == KelasType.PRIVAT:
            capacity_int = 1
        elif class_type == KelasType.GANJIL_GENAP:
            capacity_int = 2
        else:
            try:
                capacity_int = int(request.POST.get('capacity') or 0)
                if capacity_int <= 0:
                    errors.append('Kapasitas wajib diisi dan harus lebih dari 0 untuk kelas Grup.')
            except (TypeError, ValueError):
                errors.append('Kapasitas tidak valid.')
                capacity_int = 0

        try:
            weeks_int = int(request.POST.get('weeks') or 0)
            if weeks_int <= 0:
                errors.append('Jumlah pertemuan per siswa harus lebih dari 0.')
            elif weeks_int > 52:
                errors.append('Jumlah pertemuan maksimal 52.')
        except (TypeError, ValueError):
            errors.append('Jumlah pertemuan tidak valid.')
            weeks_int = 0

        # Teacher slot conflict: same teacher, same day, overlapping time window.
        if (
            not errors
            and day in valid_days
            and start_time_parsed and end_time_parsed
        ):
            clash = teacher_weekly_slot_conflict(
                teacher_profile, day, start_time_parsed, end_time_parsed,
            )
            if clash is not None:
                errors.append(
                    f'Slot bentrok dengan kelas Anda yang lain: "{clash.name}" '
                    f'di hari yang sama. Pilih jam atau hari lain.'
                )

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            try:
                with transaction.atomic():
                    # Batch model: sessions are NOT generated at create time.
                    # The first enrollment will anchor the first batch and
                    # create that batch's sessions.
                    kelas = Kelas.objects.create(
                        teacher_profile=teacher_profile,
                        subject_id=subject_id,
                        academic_period_id=period_id,
                        name=name,
                        description=description,
                        level=levels_picked[0],
                        class_type=class_type,
                        start_date=start_date_parsed,
                        end_date=start_date_parsed,
                        capacity=capacity_int,
                        total_sessions=weeks_int,
                        price=Decimal('0'),
                        status=KelasStatus.OPEN,
                    )
                    kelas.set_jenjang(levels_picked)
                    Schedule.objects.create(
                        kelas=kelas,
                        day=day,
                        start_time=start_time_parsed,
                        end_time=end_time_parsed,
                        room=room,
                    )
                log_activity(request.user, 'created', 'kelas', kelas.pk)
                jenjang_label = ', '.join(
                    dict(Level.choices).get(lv, lv) for lv in levels_picked
                )
                type_note = {
                    KelasType.PRIVAT: 'Tipe: Privat (kapasitas 1, paket per siswa).',
                    KelasType.GROUP: f'Tipe: Grup (kapasitas {capacity_int}).',
                    KelasType.GANJIL_GENAP: 'Tipe: Paket Ganjil Genap (2 kursi, window 2N minggu).',
                }.get(class_type, '')
                messages.success(
                    request,
                    f'Kelas "{kelas.name}" berhasil dibuat (jenjang: {jenjang_label}). '
                    f'Batch pertama dimulai otomatis saat siswa pertama mendaftar. '
                    + type_note
                )
                return redirect('academics:teacher_classes')
            except Exception as e:
                messages.error(request, f'Gagal membuat kelas: {e}')

        form_data = request.POST
    else:
        form_data = {}

    start_date_default = active_period.start_date.strftime('%Y-%m-%d') if active_period else ''

    return render(request, 'academics/teacher_class_create.html', {
        'subjects': subjects,
        'teacher_levels': teacher_levels,
        'all_level_choices': list(Level.choices),
        'all_class_types': list(KelasType.choices),
        'active_period': active_period,
        'all_periods': all_periods,
        'form_data': form_data,
        'day_choices': day_choices,
        'default_weeks': 8,
        'start_date_default': start_date_default,
        # Multi-select prefill: list of currently selected level codes.
        'selected_levels': (
            request.POST.getlist('levels')
            if request.method == 'POST' else []
        ),
        'selected_class_type': (
            request.POST.get('class_type') or KelasType.REGULAR
            if request.method == 'POST' else KelasType.REGULAR
        ),
    })


@role_required('TEACHER')
def teacher_class_edit(request, pk):
    """Phase 3B — Notion Clean Edit Class page.

    Reuses the Create Class form layout. All fields prefilled from the
    existing Kelas instance. Adds a Status field (OPEN/FULL/CLOSED).
    Schedule input stays on the detail page (locked decision).

    Ownership: filter ensures a teacher can only edit their OWN classes —
    foreign Kelas IDs return 404, not 403.
    """
    from decimal import Decimal, InvalidOperation

    teacher_profile = request.user.teacher_profile
    kelas = get_object_or_404(
        Kelas, pk=pk, teacher_profile=teacher_profile, is_deleted=False
    )

    subjects = (
        Subject.objects.filter(is_active=True)
        .select_related('category')
        .order_by('name')
    )
    all_periods = AcademicPeriod.objects.all().order_by('-is_active', '-start_date')
    teacher_levels = list(
        TeacherJenjang.objects
        .filter(teacher_profile=teacher_profile)
        .values_list('level', flat=True)
        .order_by('level')
    )

    from sessions_app.services import (
        generate_sessions_for_kelas, teacher_weekly_slot_conflict,
    )

    # Day.choices excludes Sunday; honor in UI
    day_choices = [(v, label) for v, label in Day.choices if v != 'SUNDAY']
    valid_days = {v for v, _ in day_choices}

    current_schedule = kelas.schedules.order_by('id').first()

    if request.method == 'POST':
        name = (request.POST.get('name') or '').strip()
        subject_id = request.POST.get('subject')
        period_id = request.POST.get('academic_period')
        levels_raw = (
            request.POST.getlist('levels')
            or [v for v in [request.POST.get('level')] if v]
        )
        levels_picked = [v for v in dict.fromkeys(levels_raw) if v]
        class_type = (request.POST.get('class_type') or kelas.class_type).strip().upper()
        if class_type not in {v for v, _ in KelasType.choices}:
            class_type = kelas.class_type
        description = (request.POST.get('description') or '').strip()
        start_date_raw = request.POST.get('start_date') or ''
        day = (request.POST.get('day') or '').strip().upper()
        start_time_raw = request.POST.get('start_time') or ''
        end_time_raw = request.POST.get('end_time') or ''
        room = (request.POST.get('room') or '').strip()
        status = request.POST.get('status') or kelas.status

        errors = []
        if not name:
            errors.append('Nama kelas wajib diisi.')
        if not subject_id:
            errors.append('Pilih mata pelajaran.')
        if not period_id:
            errors.append('Pilih periode akademik.')
        if not levels_picked:
            errors.append('Pilih minimal satu jenjang.')
        else:
            invalid_levels = [
                v for v in levels_picked if v not in {lv for lv, _ in Level.choices}
            ]
            if invalid_levels:
                errors.append('Jenjang tidak valid: ' + ', '.join(invalid_levels) + '.')
            elif teacher_levels:
                out_of_scope = [v for v in levels_picked if v not in teacher_levels]
                if out_of_scope:
                    errors.append(
                        'Jenjang ' + ', '.join(out_of_scope) + ' belum terdaftar di profil Anda. '
                        'Tambahkan di Pengaturan dulu.'
                    )
        if status not in {s for s, _ in KelasStatus.choices}:
            errors.append('Status kelas tidak valid.')

        start_date_parsed = None
        try:
            start_date_parsed = _dt.datetime.strptime(start_date_raw, '%Y-%m-%d').date()
        except ValueError:
            errors.append('Tanggal mulai wajib diisi.')

        if day not in valid_days:
            errors.append('Pilih hari pertemuan (Senin sampai Sabtu).')

        start_time_parsed = None
        end_time_parsed = None
        try:
            start_time_parsed = _dt.datetime.strptime(start_time_raw[:5], '%H:%M').time()
        except ValueError:
            errors.append('Jam mulai wajib diisi.')
        try:
            end_time_parsed = _dt.datetime.strptime(end_time_raw[:5], '%H:%M').time()
        except ValueError:
            errors.append('Jam selesai wajib diisi.')
        if start_time_parsed and end_time_parsed and end_time_parsed <= start_time_parsed:
            errors.append('Jam selesai harus setelah jam mulai.')

        if class_type == KelasType.PRIVAT:
            capacity_int = 1
        elif class_type == KelasType.GANJIL_GENAP:
            capacity_int = 2
        else:
            try:
                capacity_int = int(request.POST.get('capacity') or 0)
                if capacity_int <= 0:
                    errors.append('Kapasitas wajib diisi dan harus lebih dari 0 untuk kelas Grup.')
            except (TypeError, ValueError):
                errors.append('Kapasitas tidak valid.')
                capacity_int = 0

        try:
            weeks_int = int(request.POST.get('weeks') or 0)
            if weeks_int <= 0:
                errors.append('Jumlah pertemuan per siswa harus lebih dari 0.')
            elif weeks_int > 52:
                errors.append('Jumlah pertemuan maksimal 52.')
        except (TypeError, ValueError):
            errors.append('Jumlah pertemuan tidak valid.')
            weeks_int = 0

        # Slot conflict guard (skips self via exclude_kelas_id)
        if (
            not errors
            and day in valid_days
            and start_time_parsed and end_time_parsed
        ):
            clash = teacher_weekly_slot_conflict(
                teacher_profile, day, start_time_parsed, end_time_parsed,
                exclude_kelas_id=kelas.pk,
            )
            if clash is not None:
                errors.append(
                    f'Slot bentrok dengan kelas Anda yang lain: "{clash.name}" '
                    f'di hari yang sama. Pilih jam atau hari lain.'
                )

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            slot_changed = (
                current_schedule is None
                or current_schedule.day != day
                or current_schedule.start_time != start_time_parsed
                or current_schedule.end_time != end_time_parsed
            )
            weeks_changed = (kelas.total_sessions != weeks_int)
            start_changed = (kelas.start_date != start_date_parsed)
            try:
                with transaction.atomic():
                    kelas.name = name
                    kelas.subject_id = subject_id
                    kelas.academic_period_id = period_id
                    kelas.level = levels_picked[0]
                    kelas.class_type = class_type
                    kelas.description = description
                    kelas.start_date = start_date_parsed
                    kelas.capacity = capacity_int
                    kelas.total_sessions = weeks_int
                    kelas.status = status
                    kelas.save()
                    # Sync KelasJenjang relation
                    kelas.set_jenjang(levels_picked)

                    if current_schedule is None:
                        Schedule.objects.create(
                            kelas=kelas, day=day,
                            start_time=start_time_parsed,
                            end_time=end_time_parsed,
                            room=room,
                        )
                    elif slot_changed or current_schedule.room != room:
                        current_schedule.day = day
                        current_schedule.start_time = start_time_parsed
                        current_schedule.end_time = end_time_parsed
                        current_schedule.room = room
                        current_schedule.save()

                    # Batch model: do NOT regenerate sessions on edit. The
                    # currently running batch (if any) keeps its existing
                    # sessions; the new slot/weeks take effect on the NEXT
                    # batch when a new student anchors it.
                log_activity(request.user, 'updated', 'kelas', kelas.pk)
                messages.success(
                    request,
                    f'Kelas "{kelas.name}" berhasil diperbarui. '
                    f'Perubahan slot atau jumlah pertemuan berlaku untuk '
                    f'batch berikutnya; batch berjalan tidak diubah.'
                )
                return redirect('academics:teacher_classes')
            except Exception as e:
                messages.error(request, f'Gagal memperbarui kelas: {e}')

        form_data = request.POST
    else:
        form_data = {}

    # Single source-of-truth for chip + select prefill: submitted form_data
    # on POST-error, else the existing kelas value.
    selected_subject = form_data.get('subject') if form_data else str(kelas.subject_id)
    selected_level = form_data.get('level') if form_data else kelas.level
    selected_period = form_data.get('academic_period') if form_data else str(kelas.academic_period_id)
    selected_status = form_data.get('status') if form_data else kelas.status

    def _val(field, fallback):
        if form_data:
            return form_data.get(field) or ''
        return fallback

    schedule_day = (
        current_schedule.day if current_schedule else ''
    )
    schedule_start = (
        current_schedule.start_time.strftime('%H:%M') if current_schedule else ''
    )
    schedule_end = (
        current_schedule.end_time.strftime('%H:%M') if current_schedule else ''
    )
    schedule_room = current_schedule.room if current_schedule else ''

    # Multi-jenjang prefill: form_data takes priority on POST error, else
    # the kelas's current KelasJenjang set.
    if form_data:
        selected_levels = (
            form_data.getlist('levels')
            or [v for v in [form_data.get('level')] if v]
        )
    else:
        selected_levels = kelas.get_jenjang_list()
    selected_class_type = (
        form_data.get('class_type') if form_data else kelas.class_type
    ) or KelasType.REGULAR

    return render(request, 'academics/teacher_class_edit.html', {
        'kelas': kelas,
        'subjects': subjects,
        'teacher_levels': teacher_levels,
        'all_level_choices': list(Level.choices),
        'all_class_types': list(KelasType.choices),
        'all_periods': all_periods,
        'all_status_choices': list(KelasStatus.choices),
        'day_choices': day_choices,
        'selected_subject': selected_subject,
        'selected_level': selected_level,
        'selected_levels': selected_levels,
        'selected_class_type': selected_class_type,
        'selected_period': selected_period,
        'selected_status': selected_status,
        'selected_day': _val('day', schedule_day),
        'name_value': _val('name', kelas.name),
        'description_value': _val('description', kelas.description or ''),
        'capacity_value': _val('capacity', str(kelas.capacity)),
        'weeks_value': _val('weeks', str(kelas.total_sessions)),
        'start_date_value': _val('start_date', kelas.start_date.strftime('%Y-%m-%d')),
        'start_time_value': _val('start_time', schedule_start),
        'end_time_value': _val('end_time', schedule_end),
        'room_value': _val('room', schedule_room),
    })


@role_required('TEACHER')
@require_POST
def teacher_class_delete(request, pk):
    kelas = get_object_or_404(Kelas, pk=pk, teacher_profile__user=request.user, is_deleted=False)
    kelas_pk = kelas.pk
    kelas.soft_delete()
    log_activity(request.user, 'deleted', 'kelas', kelas_pk)
    messages.success(request, 'Kelas berhasil dihapus.')
    return redirect('academics:teacher_classes')


@role_required('TEACHER')
@require_POST
def teacher_complete_class(request, pk):
    kelas = get_object_or_404(Kelas, pk=pk, teacher_profile__user=request.user, is_deleted=False)
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

@login_required
def class_browse(request):
    """Browse classes — V2.9 Khan playful theme with collapsed-button popup filters."""
    from django.core.cache import cache
    from django.core.paginator import Paginator
    from accounts.models import Level

    update_expired_classes()
    user = request.user

    # ── Base queryset ─────────────────────────────────────────────────────────
    qs = (
        Kelas.objects
        .filter(is_deleted=False)
        .select_related('subject', 'teacher_profile__user', 'academic_period')
        .prefetch_related('schedules')
    )

    # ── Filter: status ────────────────────────────────────────────────────────
    # Default shows OPEN + FULL together so users can see (and waitlist) full classes.
    status_filter = request.GET.getlist('status')
    if status_filter:
        qs = qs.filter(status__in=status_filter)
    else:
        qs = qs.filter(status__in=[KelasStatus.OPEN, KelasStatus.FULL])

    # ── Filter: search ────────────────────────────────────────────────────────
    search = request.GET.get('q', '').strip()
    if search:
        qs = qs.filter(
            Q(name__icontains=search)
            | Q(subject__name__icontains=search)
            | Q(teacher_profile__user__first_name__icontains=search)
            | Q(teacher_profile__user__last_name__icontains=search)
            | Q(teacher_profile__user__username__icontains=search)
        )

    # ── Filter: jenjang tab (Phase 3R Grup B) ─────────────────────────────────
    # Primary jenjang selector — defaults to the signed-in student's level,
    # otherwise 'ALL'. Tabs let the student peek at other jenjang without
    # mutating their profile.
    student_level = None
    if user.is_authenticated and getattr(user, 'role', None) == 'STUDENT':
        sp = getattr(user, 'student_profile', None)
        student_level = getattr(sp, 'level', None) if sp is not None else None

    requested_jenjang = request.GET.get('jenjang')
    if requested_jenjang is None:
        selected_jenjang = student_level or 'ALL'
    else:
        selected_jenjang = requested_jenjang or 'ALL'
    if selected_jenjang != 'ALL' and selected_jenjang not in Level.values:
        selected_jenjang = 'ALL'
    if selected_jenjang != 'ALL':
        qs = qs.filter(jenjang_set__level=selected_jenjang).distinct()

    # ── Filter: level (multi-jenjang aware) ──────────────────────────────────
    level_filter = [v for v in request.GET.getlist('level') if v in Level.values]
    if level_filter:
        qs = qs.filter(jenjang_set__level__in=level_filter).distinct()

    # ── Filter: subject ───────────────────────────────────────────────────────
    subject_filter_raw = request.GET.getlist('subject')
    subject_filter = [int(s) for s in subject_filter_raw if s.isdigit()]
    if subject_filter:
        qs = qs.filter(subject_id__in=subject_filter)

    # ── Filter: days ──────────────────────────────────────────────────────────
    valid_days = {d for d, _ in Day.choices}
    days_filter = [v for v in request.GET.getlist('day') if v in valid_days]
    if days_filter:
        qs = qs.filter(schedules__day__in=days_filter).distinct()

    # ── Filter: time period ───────────────────────────────────────────────────
    time_filter = request.GET.get('time', '')
    _time_ranges = {
        'pagi':  ('06:00', '11:00'),
        'siang': ('11:00', '15:00'),
        'sore':  ('15:00', '18:00'),
        'malam': ('18:00', '22:00'),
    }
    if time_filter in _time_ranges:
        start, end = _time_ranges[time_filter]
        qs = qs.filter(
            schedules__start_time__gte=start,
            schedules__start_time__lt=end,
        ).distinct()

    # ── Filter: price ─────────────────────────────────────────────────────────
    price_min_raw = request.GET.get('price_min', '').strip()
    price_max_raw = request.GET.get('price_max', '').strip()
    try:
        if price_min_raw:
            qs = qs.filter(price__gte=int(price_min_raw))
    except ValueError:
        price_min_raw = ''
    try:
        if price_max_raw:
            qs = qs.filter(price__lte=int(price_max_raw))
    except ValueError:
        price_max_raw = ''

    # ── Filter: rating ────────────────────────────────────────────────────────
    rating_filter = request.GET.get('rating', '').strip()
    if rating_filter:
        try:
            min_rating = float(rating_filter)
            qs = qs.annotate(
                _t_avg=Avg('teacher_profile__ratings_received__score')
            ).filter(_t_avg__gte=min_rating)
        except ValueError:
            rating_filter = ''

    # ── Annotate active enrollment count + waitlist size ──────────────────────
    qs = qs.annotate(
        active_enrolled=Count(
            'enrollments',
            filter=Q(
                enrollments__status='ACTIVE',
                enrollments__is_deleted=False,
            ),
            distinct=True,
        ),
        waitlist_count=Count('waitlists', distinct=True),
    )

    # ── Sort ──────────────────────────────────────────────────────────────────
    sort_by = request.GET.get('sort', 'match')
    if sort_by == 'popular':
        qs = qs.order_by('-active_enrolled', '-created_at')
    elif sort_by == 'newest':
        qs = qs.order_by('-created_at')
    elif sort_by == 'cheapest':
        qs = qs.order_by('price', '-created_at')
    elif sort_by == 'rating':
        qs = qs.annotate(
            _t_rating=Avg('teacher_profile__ratings_received__score')
        ).order_by(F('_t_rating').desc(nulls_last=True), '-created_at')
    else:
        # 'match': student → their level first, then popularity. Other roles → popularity.
        sort_by = 'match'
        user_level = None
        if hasattr(user, 'student_profile') and user.student_profile is not None:
            user_level = user.student_profile.level
        if user_level:
            qs = qs.annotate(
                _is_my_level=Count('jenjang_set', filter=Q(jenjang_set__level=user_level))
            ).order_by('-_is_my_level', '-active_enrolled', '-created_at')
        else:
            qs = qs.order_by('-active_enrolled', '-created_at')

    # ── Paginate ──────────────────────────────────────────────────────────────
    paginator = Paginator(qs, 24)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    # ── Preload student-specific maps for state detection ─────────────────────
    from enrollments.models import EnrollmentWaitlist, EnrollmentStatus
    student_profile = getattr(user, 'student_profile', None)
    enrolled_kelas_ids = set()
    waitlist_positions = {}  # kelas_id -> position (so badge can show #N)
    if student_profile is not None:
        enrolled_kelas_ids = set(
            Enrollment.objects
            .filter(
                student_profile=student_profile,
                status__in=[EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED],
                is_deleted=False,
            )
            .values_list('kelas_id', flat=True)
        )
        waitlist_positions = dict(
            EnrollmentWaitlist.objects
            .filter(student_profile=student_profile)
            .values_list('kelas_id', 'position')
        )

    # ── Trending kelas (last 7 days, >= 5 enrollments) — cached 1 hour ────────
    trending_ids = cache.get('browse_trending_kelas_ids')
    if trending_ids is None:
        last_week = timezone.now() - timedelta(days=7)
        trending_data = (
            Enrollment.objects
            .filter(enrolled_at__gte=last_week, is_deleted=False)
            .values('kelas_id')
            .annotate(recent_count=Count('id'))
            .filter(recent_count__gte=5)
            .order_by('-recent_count')[:20]
        )
        trending_ids = {row['kelas_id']: row['recent_count'] for row in trending_data}
        cache.set('browse_trending_kelas_ids', trending_ids, 3600)

    # ── Per-card metadata (capacity, schedule, rating, 9-state logic) ─────────
    now = timezone.now()
    today = timezone.localdate()
    teacher_rating_cache = {}  # in-request dedupe

    # CTA text per state — keeps template clean
    _cta_for = {
        'enrolled':           ('Sudah Terdaftar',  True),
        'in_waitlist':        ('Di Waitlist',      True),
        'locked':             ('Penuh',            True),
        'waitlist_available': ('+ Daftar Antri',   False),
        'urgent':             ('Daftar Sekarang →', False),
    }

    from sessions_app.services import (
        batch_state as _batch_state,
        estimated_completion_date as _est_completion,
        next_slot_date as _next_slot,
        sweep_finished_batches as _sweep,
    )
    for kelas in page_obj:
        # Batch-aware annotations (cheap; cached state per-kelas at template).
        # Sweep first so a kelas whose window just ended reopens for display.
        _sweep(kelas)
        kelas.batch_state = _batch_state(kelas)
        if not kelas.batch_state['is_anchored']:
            kelas.next_slot_date = _next_slot(kelas)
            if kelas.next_slot_date:
                kelas.estimated_finish = _est_completion(kelas, kelas.next_slot_date)
            else:
                kelas.estimated_finish = None
        else:
            kelas.next_slot_date = None
            kelas.estimated_finish = None
        # Capacity %
        kelas.capacity_pct = int(round((kelas.active_enrolled / kelas.capacity) * 100)) if kelas.capacity else 0
        kelas.slots_remaining = max(0, kelas.capacity - kelas.active_enrolled)
        # Schedule preview (already prefetched)
        kelas.schedule_list = list(kelas.schedules.all())[:2]
        # Teacher rating with per-teacher cache (30 min)
        tp_id = kelas.teacher_profile_id
        if tp_id in teacher_rating_cache:
            kelas.teacher_rating = teacher_rating_cache[tp_id]
        else:
            cache_key = f'teacher_avg_rating_{tp_id}'
            tr = cache.get(cache_key)
            if tr is None:
                agg = TeacherRating.objects.filter(
                    teacher_profile_id=tp_id
                ).aggregate(avg=Avg('score'), cnt=Count('id'))
                tr = {
                    'avg': round(agg['avg'] or 0, 1),
                    'count': agg['cnt'] or 0,
                }
                cache.set(cache_key, tr, 1800)
            teacher_rating_cache[tp_id] = tr
            kelas.teacher_rating = tr

        # ── 9-state logic (priority order — see PART 5 of spec) ───────────────
        kelas.states = []           # all applicable states (allow stacking)
        kelas.primary_state = None  # the badge to render

        if kelas.id in enrolled_kelas_ids:
            kelas.states.append('enrolled')
            kelas.primary_state = 'enrolled'
        elif kelas.id in waitlist_positions:
            kelas.states.append('in_waitlist')
            kelas.primary_state = 'in_waitlist'
            kelas.waitlist_position = waitlist_positions[kelas.id]
        elif kelas.status == KelasStatus.FULL and kelas.capacity_pct >= 100:
            if kelas.waitlist_count >= 10:
                kelas.states.append('locked')
                kelas.primary_state = 'locked'
            else:
                kelas.states.append('waitlist_available')
                kelas.primary_state = 'waitlist_available'
        else:
            # Enhancement states — may stack; primary_state set by priority
            if kelas.teacher_rating['avg'] >= 4.8 and kelas.teacher_rating['count'] >= 10:
                kelas.states.append('top_teacher')
                kelas.primary_state = 'top_teacher'

            if 0 < kelas.slots_remaining <= 3:
                kelas.states.append('urgent')
                kelas.primary_state = 'urgent'  # urgent overrides top_teacher (conversion)

            if kelas.start_date:
                days_until = (kelas.start_date - today).days
                if 0 <= days_until <= 7:
                    kelas.days_until_start = days_until
                    kelas.states.append('starting_soon')
                    if kelas.primary_state in (None, 'top_teacher'):
                        kelas.primary_state = 'starting_soon'

            if kelas.id in trending_ids:
                kelas.trending_growth = trending_ids[kelas.id]
                kelas.states.append('trending')
                if kelas.primary_state is None:
                    kelas.primary_state = 'trending'

            if student_profile and student_profile.level in kelas.get_jenjang_list():
                kelas.states.append('recommended')
                if kelas.primary_state is None:
                    kelas.primary_state = 'recommended'

            if kelas.created_at and (now - kelas.created_at).days <= 14:
                kelas.states.append('new')
                if kelas.primary_state is None:
                    kelas.primary_state = 'new'

        # CTA text + disabled flag
        text_disabled = _cta_for.get(kelas.primary_state)
        if text_disabled is not None:
            kelas.cta_text, kelas.cta_disabled = text_disabled
            if kelas.primary_state == 'in_waitlist':
                kelas.cta_text = f'Antrian #{kelas.waitlist_position}'
        else:
            kelas.cta_text, kelas.cta_disabled = 'Detail →', False

    # ── Filter option lists (cached) ──────────────────────────────────────────
    level_counts = cache.get('browse_filter_levels')
    if level_counts is None:
        level_counts = list(
            Kelas.objects
            .filter(is_deleted=False, status=KelasStatus.OPEN)
            .values('level')
            .annotate(c=Count('id'))
            .order_by('level')
        )
        # Ensure every level in the enum appears (even with c=0) so user can pick any
        present = {row['level'] for row in level_counts}
        for code, _ in Level.choices:
            if code not in present:
                level_counts.append({'level': code, 'c': 0})
        level_order = [code for code, _ in Level.choices]
        level_counts.sort(key=lambda r: level_order.index(r['level']) if r['level'] in level_order else 999)
        cache.set('browse_filter_levels', level_counts, 300)

    subject_options = cache.get('browse_filter_subjects')
    if subject_options is None:
        subject_options = list(
            Subject.objects
            .annotate(
                kelas_count=Count(
                    'classes',
                    filter=Q(classes__is_deleted=False, classes__status=KelasStatus.OPEN),
                )
            )
            .filter(kelas_count__gt=0)
            .order_by('-kelas_count', 'name')[:12]
        )
        cache.set('browse_filter_subjects', subject_options, 300)

    # ── Status options with counts (small, not cached separately) ─────────────
    status_options = [
        {'code': 'OPEN',   'label': 'Tersedia',  'dot': 'g',
         'count': Kelas.objects.filter(is_deleted=False, status=KelasStatus.OPEN).count()},
        {'code': 'FULL',   'label': 'Penuh',     'dot': 'r',
         'count': Kelas.objects.filter(is_deleted=False, status=KelasStatus.FULL).count()},
        {'code': 'CLOSED', 'label': 'Tutup',     'dot': 'a',
         'count': Kelas.objects.filter(is_deleted=False, status=KelasStatus.CLOSED).count()},
    ]

    active_filter_count = sum([
        1 if level_filter else 0,
        1 if subject_filter else 0,
        1 if days_filter else 0,
        1 if time_filter else 0,
        1 if rating_filter else 0,
        1 if (price_min_raw or price_max_raw) else 0,
        1 if status_filter else 0,
    ])

    context = {
        'page_obj': page_obj,
        'total_count': paginator.count,
        # Sticky filter state
        'search': search,
        'selected_jenjang': selected_jenjang,
        'student_level': student_level,
        'jenjang_choices': ['TK', 'SD', 'SMP', 'SMA', 'UMUM'],
        'selected_levels': level_filter,
        'selected_subjects': subject_filter,
        'selected_days': days_filter,
        'selected_time': time_filter,
        'price_min': price_min_raw,
        'price_max': price_max_raw,
        'selected_rating': rating_filter,
        'selected_status': status_filter,
        'sort_by': sort_by,
        # Option lists
        'level_counts': level_counts,
        'subject_options': subject_options,
        'status_options': status_options,
        'days_list': [
            ('MONDAY',    'Sn'),
            ('TUESDAY',   'Sl'),
            ('WEDNESDAY', 'Rb'),
            ('THURSDAY',  'Km'),
            ('FRIDAY',    'Jm'),
            ('SATURDAY',  'Sb'),
        ],
        'time_options': [
            ('pagi',  'Pagi',  '06:00–11:00', 'sun'),
            ('siang', 'Siang', '11:00–15:00', 'sun-high'),
            ('sore',  'Sore',  '15:00–18:00', 'sunset'),
            ('malam', 'Malam', '18:00–22:00', 'moon'),
        ],
        'rating_options': [
            ('4.0', '4.0+', 4),
            ('4.5', '4.5+', 4),
            ('4.8', '4.8+', 5),
        ],
        'active_filter_count': active_filter_count,
    }
    return render(request, 'academics/class_browse.html', context)


@login_required
def class_detail(request, pk):
    """Class detail page — Khan Playful design with mega hero + sticky enroll."""
    from django.core.cache import cache

    kelas = get_object_or_404(
        Kelas.objects
        .select_related('subject', 'teacher_profile__user', 'academic_period')
        .prefetch_related('schedules', 'sessions'),
        pk=pk, is_deleted=False,
    )

    # Batch sweep: roll over to the next batch if the current one just ended.
    from sessions_app.services import (
        batch_state as _batch_state,
        estimated_completion_date as _est_completion,
        is_enrollment_open as _is_open,
        next_slot_date as _next_slot,
        sweep_finished_batches as _sweep,
    )
    _sweep(kelas)
    kelas.refresh_from_db()
    bstate = _batch_state(kelas)
    batch_open, batch_reason = _is_open(kelas)
    if bstate['is_anchored']:
        batch_next_open_str = (
            bstate['next_open_date'].strftime('%d %b %Y')
            if bstate['next_open_date'] else 'segera'
        )
        next_start_date = None
        est_finish = None
    else:
        batch_next_open_str = ''
        next_start_date = _next_slot(kelas)
        est_finish = _est_completion(kelas, next_start_date) if next_start_date else None

    # ── Capacity (live, 30s cache) ────────────────────────────────────────────
    capacity_cache_key = f'kelas_{kelas.id}_capacity'
    active_count = cache.get(capacity_cache_key)
    if active_count is None:
        active_count = Enrollment.objects.filter(
            kelas=kelas,
            status=EnrollmentStatus.ACTIVE,
            is_deleted=False,
        ).count()
        cache.set(capacity_cache_key, active_count, 30)
    slots_remaining = max(0, kelas.capacity - active_count)
    capacity_pct = int(round((active_count / kelas.capacity) * 100)) if kelas.capacity else 0

    # ── Viewer's enrollment status (if student) ───────────────────────────────
    student_profile = getattr(request.user, 'student_profile', None)
    user_enrollment = None
    user_enrolled = False
    if student_profile is not None:
        user_enrollment = (
            Enrollment.objects
            .filter(student_profile=student_profile, kelas=kelas, is_deleted=False)
            .exclude(status=EnrollmentStatus.DROPPED)
            .first()
        )
        user_enrolled = user_enrollment is not None

    # ── Schedules (with Indonesian day label) ─────────────────────────────────
    _day_id = {
        'MONDAY': 'Senin', 'TUESDAY': 'Selasa', 'WEDNESDAY': 'Rabu',
        'THURSDAY': 'Kamis', 'FRIDAY': 'Jumat', 'SATURDAY': 'Sabtu',
    }
    schedules = list(kelas.schedules.all().order_by('day', 'start_time'))
    for s in schedules:
        s.day_id = _day_id.get(s.day, s.day)
        # time-of-day emoji
        h = s.start_time.hour
        if h < 11:
            s.emoji = '🌅'
        elif h < 17:
            s.emoji = '☀️'
        else:
            s.emoji = '🌙'

    # ── Sessions preview (first 3 by date) + total count ──────────────────────
    sessions_preview = list(kelas.sessions.all().order_by('date', 'start_time')[:3])
    total_sessions_actual = kelas.sessions.count()
    total_sessions = kelas.total_sessions or total_sessions_actual

    # ── Teacher stats (30 min cache) ──────────────────────────────────────────
    teacher_profile = kelas.teacher_profile
    teacher_stats_key = f'teacher_{teacher_profile.id}_stats'
    teacher_stats = cache.get(teacher_stats_key)
    if teacher_stats is None:
        agg = TeacherRating.objects.filter(
            teacher_profile=teacher_profile
        ).aggregate(avg=Avg('score'), c=Count('id'))
        active_classes_count = (
            Kelas.objects
            .filter(teacher_profile=teacher_profile, is_deleted=False)
            .exclude(status=KelasStatus.CLOSED)
            .count()
        )
        student_count = (
            Enrollment.objects
            .filter(
                kelas__teacher_profile=teacher_profile,
                status=EnrollmentStatus.ACTIVE,
                is_deleted=False,
            )
            .values('student_profile').distinct().count()
        )
        teacher_stats = {
            'avg_rating': round(agg['avg'] or 0, 1),
            'rating_count': agg['c'] or 0,
            'active_classes': active_classes_count,
            'student_count': student_count,
        }
        cache.set(teacher_stats_key, teacher_stats, 1800)

    # ── Reviews (top 3 + distribution, 30 min cache) ──────────────────────────
    reviews_cache_key = f'kelas_{kelas.id}_reviews'
    reviews_data = cache.get(reviews_cache_key)
    if reviews_data is None:
        ratings_qs = (
            TeacherRating.objects
            .filter(enrollment__kelas=kelas, enrollment__is_deleted=False)
            .select_related('enrollment__student_profile__user')
            .order_by('-created_at')
        )
        total_ratings = ratings_qs.count()
        avg_score = ratings_qs.aggregate(a=Avg('score'))['a'] or 0
        distribution = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}
        for r in ratings_qs.values_list('score', flat=True):
            bucket = int(round(r))
            if 1 <= bucket <= 5:
                distribution[bucket] += 1
        bars = []
        for star in (5, 4, 3, 2, 1):
            count = distribution[star]
            pct = int(round(count / total_ratings * 100)) if total_ratings else 0
            bars.append({'star': star, 'count': count, 'pct': pct})
        top_reviews = []
        for r in list(ratings_qs[:3]):
            r.star_str = '★' * max(1, min(5, int(round(r.score))))
            top_reviews.append(r)
        reviews_data = {
            'total': total_ratings,
            'avg': round(avg_score, 1),
            'bars': bars,
            'top_reviews': top_reviews,
        }
        cache.set(reviews_cache_key, reviews_data, 1800)

    # ── Description fallback ──────────────────────────────────────────────────
    teacher_full_name = teacher_profile.user.get_full_name() or teacher_profile.user.username
    description = (
        kelas.description.strip()
        if kelas.description else
        f'Kelas {kelas.name} untuk jenjang {kelas.get_jenjang_display()}. '
        f'Bergabunglah dengan {teacher_full_name} untuk pengalaman belajar terbaik!'
    )

    # ── Learning outcomes (fallback — no field in schema) ─────────────────────
    learning_outcomes = [
        f'Penguasaan materi {kelas.subject.name}',
        'Latihan soal tingkat HOTS',
        'Strategi pengerjaan soal',
        'Time management saat ujian',
        'Tips & trik belajar efektif',
        'Simulasi rutin & pembahasan',
    ]

    # ── Level mismatch flag (multi-jenjang aware) ────────────────────────────
    accepted_levels = kelas.get_jenjang_list()
    level_mismatch = bool(
        student_profile and student_profile.level not in accepted_levels
    )

    # ── Related classes (same subject + any matching jenjang → fallback) ─────
    related_cache_key = f'kelas_{kelas.id}_related'
    related_classes = cache.get(related_cache_key)
    if related_classes is None:
        def _build_related(filter_kwargs):
            return list(
                Kelas.objects
                .filter(is_deleted=False, **filter_kwargs)
                .exclude(pk=kelas.id)
                .exclude(status=KelasStatus.CLOSED)
                .select_related('teacher_profile__user', 'subject')
                .annotate(
                    active_count=Count(
                        'enrollments',
                        filter=Q(
                            enrollments__status=EnrollmentStatus.ACTIVE,
                            enrollments__is_deleted=False,
                        ),
                        distinct=True,
                    ),
                    avg_rating=Avg('enrollments__teacher_rating__score'),
                )
                .order_by(F('avg_rating').desc(nulls_last=True), '-active_count')[:3]
            )

        related_qs = _build_related(
            {'jenjang_set__level__in': accepted_levels, 'subject': kelas.subject}
        )
        if len(related_qs) < 3:
            related_qs = _build_related({'jenjang_set__level__in': accepted_levels})
        # `distinct()` is applied here (not via _build_related) so the slice still works
        seen, unique_related = set(), []
        for k in related_qs:
            if k.pk in seen:
                continue
            seen.add(k.pk)
            unique_related.append(k)
        related_qs = unique_related
        for k in related_qs:
            k.slots_remaining = max(0, k.capacity - k.active_count)
            k.capacity_pct = int(round((k.active_count / k.capacity) * 100)) if k.capacity else 0
            k.is_full_or_no_slots = (k.status == KelasStatus.FULL) or (k.slots_remaining == 0)
        related_classes = related_qs
        cache.set(related_cache_key, related_classes, 1800)

    # Paket Ganjil Genap seat status (only meaningful for that class type).
    seat_status = None
    if kelas.class_type == KelasType.GANJIL_GENAP:
        from sessions_app.services import kelas_seat_status, SEAT_GANJIL, SEAT_GENAP
        seats = kelas_seat_status(kelas)
        def _seat_row(code, label):
            enr = seats.get(code)
            who = ''
            if enr is not None:
                who = enr.student_profile.user.get_full_name() or enr.student_profile.user.username
            return {
                'code': code,
                'label': label,
                'taken': enr is not None,
                'student_name': who,
            }
        seat_status = [
            _seat_row(SEAT_GANJIL, 'Slot Ganjil'),
            _seat_row(SEAT_GENAP, 'Slot Genap'),
        ]

    return render(request, 'academics/class_detail.html', {
        'kelas': kelas,
        'subject_icon': kelas.subject.icon or '📚',
        'active_count': active_count,
        'slots_remaining': slots_remaining,
        'capacity_pct': capacity_pct,
        'user_enrolled': user_enrolled,
        'user_enrollment': user_enrollment,
        'schedules': schedules,
        'sessions_preview': sessions_preview,
        'total_sessions': total_sessions,
        'teacher': teacher_profile,
        'teacher_stats': teacher_stats,
        'reviews_data': reviews_data,
        'description': description,
        'learning_outcomes': learning_outcomes,
        'student_profile': student_profile,
        'level_mismatch': level_mismatch,
        'related_classes': related_classes,
        'seat_status': seat_status,
        'batch_state': bstate,
        'batch_open': batch_open,
        'batch_reason': batch_reason,
        'batch_next_open_str': batch_next_open_str,
        'next_start_date': next_start_date,
        'est_finish': est_finish,
    })


@role_required('TEACHER')
def teacher_class_students(request, pk):
    """Phase 3B — card-grid roster of students in a class.

    View + light action buttons (Nilai per-student, Kehadiran class-wide).
    DROPPED + soft-deleted enrollments are hidden.
    """
    teacher_profile = request.user.teacher_profile
    kelas = get_object_or_404(
        Kelas.objects.select_related('subject'),
        pk=pk, teacher_profile=teacher_profile, is_deleted=False,
    )

    enrollments = list(
        Enrollment.objects
        .filter(kelas=kelas, is_deleted=False)
        .exclude(status=EnrollmentStatus.DROPPED)
        .select_related('student_profile__user')
        .order_by('student_profile__user__first_name', 'student_profile__user__last_name')
    )

    # Attach a per-enrollment WhatsApp deeplink. Phone lives on User
    # (see PITFALLS.md — student_profile.phone is a @property shim, but
    # we read User.phone directly to stay aligned with the canonical path).
    for enr in enrollments:
        phone = (enr.student_profile.user.phone or '').strip()
        digits = ''.join(c for c in phone if c.isdigit())
        if digits.startswith('0'):
            digits = '62' + digits[1:]
        enr.wa_link = f'https://wa.me/{digits}' if digits else ''

    return render(request, 'academics/teacher_class_students.html', {
        'kelas': kelas,
        'enrollments': enrollments,
        'student_count': len(enrollments),
    })


# ── Schedule views ────────────────────────────────────────────────────────────

def _student_schedule_ctx(user):
    active_enrollments = (
        Enrollment.objects
        .filter(student_profile__user=user, status=EnrollmentStatus.ACTIVE, is_deleted=False)
        .select_related('kelas__subject__category', 'kelas__teacher_profile__user')
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
    """Real redirect from /my-schedule/ to /my-schedule/classes/.

    Preserves the querystring so the week navigation works when other code or
    bookmarks point at the legacy short URL.
    """
    target = '/my-schedule/classes/'
    qs = request.META.get('QUERY_STRING', '')
    if qs:
        target = f'{target}?{qs}'
    return redirect(target)


def _render_student_schedule_week(request):
    """Khan Playful weekly view body. Used by /my-schedule/classes/.

    Renders 7-day grid + today highlight + week navigator. Cached 5min per
    (student, week_start). Cache is invalidated by Session/Enrollment signals.

    Accepts ?week=YYYY-MM-DD (canonical) or ?week=prev|next|current (also
    supported so prev/next button conventions are unified with the sessions
    tab).
    """
    from datetime import datetime, timedelta
    from django.core.cache import cache
    from sessions_app.models import Session

    student_profile = request.user.student_profile
    today = timezone.localdate()

    _ID_MONTHS_LONG = ['Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
                       'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember']
    _ID_MONTHS_SHORT = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun',
                        'Jul', 'Ags', 'Sep', 'Okt', 'Nov', 'Des']
    _ID_DAYS = ['Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu']

    # ── Parse week (default = current) ─────────────────────────────────────
    week_param = request.GET.get('week', '').strip()
    today_monday = today - timedelta(days=today.weekday())
    week_start = today_monday
    if week_param:
        # Sessions-tab convention: prev / next / current
        if week_param == 'next':
            week_start = today_monday + timedelta(days=7)
        elif week_param == 'prev':
            week_start = today_monday - timedelta(days=7)
        elif week_param == 'current':
            week_start = today_monday
        else:
            # Canonical YYYY-MM-DD; snap to that week's Monday
            try:
                target_date = datetime.strptime(week_param, '%Y-%m-%d').date()
                week_start = target_date - timedelta(days=target_date.weekday())
            except ValueError:
                week_start = today_monday
    week_end = week_start + timedelta(days=6)
    prev_week = (week_start - timedelta(days=7)).strftime('%Y-%m-%d')
    next_week = (week_start + timedelta(days=7)).strftime('%Y-%m-%d')

    # ── Per-week per-student cache ─────────────────────────────────────────
    cache_key = f'schedule_{student_profile.id}_{week_start}'
    week_data = cache.get(cache_key)
    if week_data is None:
        sessions = list(
            Session.objects
            .filter(
                kelas__enrollments__student_profile=student_profile,
                kelas__enrollments__status=EnrollmentStatus.ACTIVE,
                kelas__enrollments__is_deleted=False,
                date__gte=week_start,
                date__lte=week_end,
            )
            .select_related('kelas__subject', 'kelas__teacher_profile__user')
            .order_by('date', 'start_time')
            .distinct()
        )
        # Decorate each session
        for s in sessions:
            if s.start_time and s.end_time:
                start_min = s.start_time.hour * 60 + s.start_time.minute
                end_min = s.end_time.hour * 60 + s.end_time.minute
                dur = max(0, end_min - start_min)
                h, m = divmod(dur, 60)
                if h and m:
                    s.duration_label = f'{h}j {m}m'
                elif h:
                    s.duration_label = f'{h}j'
                else:
                    s.duration_label = f'{m}m'
            else:
                s.duration_label = ''
            s.subject_emoji = (s.kelas.subject.icon if s.kelas.subject else '') or '📖'
            s.is_online = bool(s.meeting_url)

        # Group by date
        by_date = {}
        for s in sessions:
            by_date.setdefault(s.date, []).append(s)

        days_data = []
        for i in range(7):
            day_date = week_start + timedelta(days=i)
            day_sessions = by_date.get(day_date, [])
            is_today = (day_date == today)
            is_past = (day_date < today)
            n = len(day_sessions)
            completed = sum(1 for s in day_sessions if s.status == 'COMPLETED')
            if not day_sessions:
                summary, day_status = 'Tidak ada sesi', 'libur'
            elif is_past:
                summary, day_status = f'{n} sesi · {completed} selesai', 'past'
            elif is_today:
                upcoming = n - completed
                summary = f'{n} sesi · {completed} selesai · {upcoming} mendatang'
                day_status = 'today'
            else:
                summary, day_status = f'{n} sesi mendatang', 'upcoming'
            days_data.append({
                'date': day_date,
                'day_num': day_date.day,
                'month_short': _ID_MONTHS_SHORT[day_date.month - 1],
                'day_name': _ID_DAYS[i],
                'sessions': day_sessions,
                'is_today': is_today,
                'is_past': is_past,
                'summary': summary,
                'day_status': day_status,
            })

        today_data = next((d for d in days_data if d['is_today']), None)
        total_sessions = sum(len(d['sessions']) for d in days_data)
        completed_count = sum(1 for d in days_data for s in d['sessions'] if s.status == 'COMPLETED')
        upcoming_count = total_sessions - completed_count
        active_classes_count = Enrollment.objects.filter(
            student_profile=student_profile,
            status=EnrollmentStatus.ACTIVE,
            is_deleted=False,
        ).count()
        week_data = {
            'days_data': days_data,
            'today_data': today_data,
            'total_sessions': total_sessions,
            'completed_count': completed_count,
            'upcoming_count': upcoming_count,
            'active_classes_count': active_classes_count,
        }
        cache.set(cache_key, week_data, 300)

    # ── Header strings (not cached — cheap to compute) ─────────────────────
    if week_start.month == week_end.month:
        week_range_str = (
            f'{week_start.day}–{week_end.day} {_ID_MONTHS_LONG[week_end.month - 1]} {week_end.year}'
        )
    else:
        week_range_str = (
            f'{week_start.day} {_ID_MONTHS_SHORT[week_start.month - 1]} – '
            f'{week_end.day} {_ID_MONTHS_SHORT[week_end.month - 1]} {week_end.year}'
        )
    is_current_week = (week_start == today_monday)

    return render(request, 'academics/student_schedule.html', {
        **week_data,
        'week_start': week_start,
        'week_end': week_end,
        'week_range_str': week_range_str,
        'is_current_week': is_current_week,
        'prev_week': prev_week,
        'next_week': next_week,
    })


@role_required('STUDENT')
def student_schedule(request):
    return render(request, 'academics/student_schedule.html',
                  _student_schedule_ctx(request.user))


@role_required('STUDENT')
def student_schedule_classes(request):
    """Canonical weekly classes view at /my-schedule/classes/.

    Delegates to the same body the legacy /my-schedule/ used to render so the
    Khan Playful day grid + stats + prev/next navigation all work here.
    """
    return _render_student_schedule_week(request)


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
        .filter(student_profile__user=request.user, status=EnrollmentStatus.ACTIVE, is_deleted=False)
        .select_related('kelas__subject__category', 'kelas__teacher_profile__user')
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
        .filter(teacher_profile__user=user, is_deleted=False,
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


# Phase 3B monthly calendar — Indonesian month names + color palette per kelas
_INDONESIAN_MONTHS = [
    'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
    'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember',
]
# (palette_name, chip_class for Tailwind cells, dot_class for legend dots)
_KELAS_PALETTE = [
    ('emerald', 'bg-emerald-100 text-emerald-800 border-emerald-200', 'bg-emerald-500'),
    ('blue',    'bg-blue-100 text-blue-800 border-blue-200',          'bg-blue-500'),
    ('amber',   'bg-amber-100 text-amber-800 border-amber-200',       'bg-amber-500'),
    ('purple',  'bg-purple-100 text-purple-800 border-purple-200',    'bg-purple-500'),
    ('pink',    'bg-pink-100 text-pink-800 border-pink-200',          'bg-pink-500'),
    ('teal',    'bg-teal-100 text-teal-800 border-teal-200',          'bg-teal-500'),
]


def _teacher_monthly_schedule_ctx(user, request):
    """Build the monthly-calendar context used by both screen + print views.

    Pulls every Session from every (non-deleted) class taught by the user
    for the requested (year, month). Assigns one Tailwind color slot per
    distinct kelas (cycling through _KELAS_PALETTE).
    """
    import calendar as _cal

    teacher_profile = user.teacher_profile
    today = timezone.localdate()

    try:
        year = int(request.GET.get('year') or today.year)
        month = int(request.GET.get('month') or today.month)
    except (TypeError, ValueError):
        year, month = today.year, today.month
    if not (1 <= month <= 12):
        year, month = today.year, today.month

    sessions = list(
        Session.objects
        .filter(
            kelas__teacher_profile=teacher_profile,
            kelas__is_deleted=False,
            date__year=year,
            date__month=month,
        )
        .select_related('kelas', 'kelas__subject')
        .order_by('date', 'start_time')
    )

    # Deterministic color assignment: ordered by kelas.id so colors are
    # stable across paginated months.
    distinct_kelas = sorted(
        {s.kelas_id: s.kelas for s in sessions}.values(),
        key=lambda k: k.id,
    )
    color_by_kelas = {}
    legend = []
    for i, k in enumerate(distinct_kelas):
        name, chip_class, dot_class = _KELAS_PALETTE[i % len(_KELAS_PALETTE)]
        color_by_kelas[k.id] = (name, chip_class)
        legend.append({
            'kelas': k,
            'color_name': name,
            'chip_class': chip_class,
            'dot_class': dot_class,
        })

    # Attach color class + color name to each session for template simplicity
    for s in sessions:
        name, chip_class = color_by_kelas.get(s.kelas_id, (_KELAS_PALETTE[0][0], _KELAS_PALETTE[0][1]))
        s.color_name = name
        s.chip_class = chip_class

    # Group sessions by day-of-month → {day_int: [session, ...]}
    sessions_by_day = {}
    for s in sessions:
        sessions_by_day.setdefault(s.date.day, []).append(s)

    # Build the calendar weeks. monthcalendar returns weeks as [int]
    # where 0 means "padding" (day outside this month). We enrich each
    # cell into a dict the template can render directly.
    _cal.setfirstweekday(_cal.MONDAY)
    raw_weeks = _cal.monthcalendar(year, month)
    is_today_month = (year == today.year and month == today.month)
    weeks = []
    for week in raw_weeks:
        row = []
        for day in week:
            if day == 0:
                row.append({'is_padding': True})
            else:
                day_sessions = sessions_by_day.get(day, [])
                row.append({
                    'is_padding': False,
                    'day': day,
                    'is_today': is_today_month and day == today.day,
                    'sessions': day_sessions[:2],
                    'overflow': max(0, len(day_sessions) - 2),
                })
        weeks.append(row)

    prev_month = 12 if month == 1 else month - 1
    prev_year = year - 1 if month == 1 else year
    next_month = 1 if month == 12 else month + 1
    next_year = year + 1 if month == 12 else year

    return {
        'year': year,
        'month': month,
        'month_name': _INDONESIAN_MONTHS[month - 1],
        'weeks': weeks,
        'legend': legend,
        'session_count': len(sessions),
        'distinct_kelas_count': len(distinct_kelas),
        'prev_year': prev_year, 'prev_month': prev_month,
        'next_year': next_year, 'next_month': next_month,
        'today': today,
        'is_current_month': is_today_month,
        'teacher_name': user.get_full_name() or user.username,
    }


@role_required('TEACHER')
def teacher_schedule(request):
    return render(
        request,
        'academics/teacher_schedule.html',
        _teacher_monthly_schedule_ctx(request.user, request),
    )


@role_required('TEACHER')
def teacher_schedule_classes(request):
    return render(
        request,
        'academics/teacher_schedule.html',
        _teacher_monthly_schedule_ctx(request.user, request),
    )


@role_required('TEACHER')
def teacher_schedule_print(request):
    return render(
        request,
        'academics/teacher_schedule_print.html',
        _teacher_monthly_schedule_ctx(request.user, request),
    )


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
        .filter(teacher_profile__user=request.user, is_deleted=False,
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
    """Browse Teachers — Khan Playful 3-col catalog with hero pill search,
    chip filters, sort, and pagination. Uses the existing `teacher_list` URL
    name so sidebar / dashboard / breadcrumb links keep working."""
    from django.core.paginator import Paginator
    from accounts.models import Level, TeacherProfile

    qs = (
        TeacherProfile.objects
        .filter(
            user__approval_status=ApprovalStatus.APPROVED,
            user__is_active=True,
            user__is_deleted=False,
        )
        .select_related('user')
        .prefetch_related('jenjang_set')
    )

    # ── Annotate stats (use correct reverse paths) ─────────────────────────
    qs = qs.annotate(
        active_classes_count=Count(
            'taught_classes',
            filter=Q(taught_classes__is_deleted=False) & ~Q(taught_classes__status=KelasStatus.CLOSED),
            distinct=True,
        ),
        student_count=Count(
            'taught_classes__enrollments',
            filter=Q(
                taught_classes__enrollments__status=EnrollmentStatus.ACTIVE,
                taught_classes__enrollments__is_deleted=False,
            ),
            distinct=True,
        ),
        avg_rating=Avg('ratings_received__score'),
        rating_count=Count('ratings_received', distinct=True),
    )

    # ── Filters ────────────────────────────────────────────────────────────
    search = request.GET.get('q', '').strip()
    if search:
        qs = qs.filter(
            Q(user__first_name__icontains=search)
            | Q(user__last_name__icontains=search)
            | Q(user__username__icontains=search)
            | Q(specialization__icontains=search)
            | Q(bio__icontains=search)
        )

    # ── Filter: jenjang tab (Phase 3R Grup B) ──────────────────────────────
    # Primary filter — default to signed-in student's level, fallback 'ALL'.
    # A teacher matches a jenjang if they have a TeacherJenjang row at that
    # level OR they teach a Kelas at that level (live/non-deleted).
    user = request.user
    student_level = None
    if user.is_authenticated and getattr(user, 'role', None) == 'STUDENT':
        sp = getattr(user, 'student_profile', None)
        student_level = getattr(sp, 'level', None) if sp is not None else None

    requested_jenjang = request.GET.get('jenjang')
    if requested_jenjang is None:
        selected_jenjang = student_level or 'ALL'
    else:
        selected_jenjang = requested_jenjang or 'ALL'
    if selected_jenjang != 'ALL' and selected_jenjang not in Level.values:
        selected_jenjang = 'ALL'
    if selected_jenjang != 'ALL':
        qs = qs.filter(
            Q(jenjang_set__level=selected_jenjang)
            | Q(taught_classes__level=selected_jenjang,
                taught_classes__is_deleted=False)
        ).distinct()

    # Legacy `?level=` param (single value) — kept for backward-compat with
    # any existing bookmarks; the new tab UI uses `?jenjang=` instead.
    level_filter = request.GET.get('level', '')
    if level_filter in Level.values:
        qs = qs.filter(jenjang_set__level=level_filter).distinct()
    else:
        level_filter = ''

    subject_filter_raw = request.GET.get('subject', '')
    subject_filter = subject_filter_raw if subject_filter_raw.isdigit() else ''
    if subject_filter:
        qs = qs.filter(
            taught_classes__subject_id=int(subject_filter),
            taught_classes__is_deleted=False,
        ).distinct()

    quick = request.GET.get('quick', '')
    if quick == 'top_rated':
        qs = qs.filter(avg_rating__gte=4.5, rating_count__gte=5)
    elif quick == 'new':
        qs = qs.filter(user__date_joined__gte=timezone.now() - timedelta(days=60))
    else:
        quick = ''

    # ── Sort ───────────────────────────────────────────────────────────────
    sort = request.GET.get('sort', 'top_rated')
    if sort == 'most_students':
        qs = qs.order_by('-student_count', '-avg_rating')
    elif sort == 'newest':
        qs = qs.order_by('-user__date_joined')
    elif sort == 'most_classes':
        qs = qs.order_by('-active_classes_count', '-avg_rating')
    else:
        sort = 'top_rated'
        qs = qs.order_by('-avg_rating', '-rating_count', '-student_count')

    # ── Paginate ───────────────────────────────────────────────────────────
    paginator = Paginator(qs, 12)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    # ── Per-teacher display props ──────────────────────────────────────────
    _gradients = [
        'from-emerald-500 to-emerald-600',
        'from-blue-500 to-blue-600',
        'from-violet-500 to-violet-600',
        'from-pink-500 to-pink-600',
        'from-amber-500 to-amber-600',
        'from-teal-500 to-teal-600',
    ]
    now = timezone.now()
    for i, t in enumerate(page_obj):
        t.avg_rating_display = round(t.avg_rating or 0, 1) if t.rating_count else None
        t.gradient = _gradients[i % len(_gradients)]
        first = t.user.first_name[:1].upper() if t.user.first_name else ''
        last = t.user.last_name[:1].upper() if t.user.last_name else ''
        if not first and not last:
            first = (t.user.username[:1] or '?').upper()
        t.initials = (first + last) or '?'
        t.display_name = t.user.get_full_name() or t.user.username
        if t.avg_rating and t.avg_rating >= 4.7 and t.rating_count >= 10:
            t.badge, t.badge_text = 'top', '🏆 TOP RATED'
        elif t.user.date_joined and t.user.date_joined >= now - timedelta(days=60):
            t.badge, t.badge_text = 'new', '✨ BARU'
        else:
            t.badge = None
        t.jenjang_list = list(t.jenjang_set.all()[:3])

    # ── Filter option lists ────────────────────────────────────────────────
    subjects = Subject.objects.filter(is_active=True).order_by('name')
    total_approved = (
        TeacherProfile.objects
        .filter(
            user__approval_status=ApprovalStatus.APPROVED,
            user__is_active=True,
            user__is_deleted=False,
        )
        .count()
    )

    return render(request, 'academics/teacher_list.html', {
        'page_obj': page_obj,
        'total_count': paginator.count,
        'total_approved': total_approved,
        'search': search,
        'level_filter': level_filter,
        'selected_jenjang': selected_jenjang,
        'student_level': student_level,
        'jenjang_choices': ['TK', 'SD', 'SMP', 'SMA', 'UMUM'],
        'subject_filter': subject_filter,
        'quick': quick,
        'sort': sort,
        'subjects': subjects,
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

    # Phase 3R Grup B: mirror the jenjang tab filter from teacher_list so
    # HTMX-driven swaps stay consistent with the full-page filter.
    user = request.user
    student_level = None
    if user.is_authenticated and getattr(user, 'role', None) == 'STUDENT':
        sp = getattr(user, 'student_profile', None)
        student_level = getattr(sp, 'level', None) if sp is not None else None
    requested_jenjang = request.GET.get('jenjang')
    if requested_jenjang is None:
        selected_jenjang = student_level or 'ALL'
    else:
        selected_jenjang = requested_jenjang or 'ALL'
    if selected_jenjang != 'ALL' and selected_jenjang not in Level.values:
        selected_jenjang = 'ALL'
    if selected_jenjang != 'ALL':
        qs = qs.filter(
            Q(teacher_profile__jenjang_set__level=selected_jenjang)
            | Q(teacher_profile__taught_classes__level=selected_jenjang,
                teacher_profile__taught_classes__is_deleted=False)
        ).distinct()

    return render(request, 'academics/_teacher_list_grid.html', {
        'teachers': qs,
        'q': q,
        'spec_filter': spec_filter,
        'selected_jenjang': selected_jenjang,
        'student_level': student_level,
    })


@login_required
def teacher_profile(request, pk):
    """Public teacher profile — Khan Playful teal design.

    `pk` is the User pk (kept for backward compat — older templates link to
    {% url 'academics:teacher_profile' teacher.user_id %}).
    """
    from django.core.cache import cache
    from accounts.models import User as UserModel
    teacher_user = get_object_or_404(
        UserModel,
        pk=pk, role=Role.TEACHER, is_active=True, is_deleted=False,
        approval_status=ApprovalStatus.APPROVED,
    )
    try:
        profile = teacher_user.teacher_profile
    except Exception:
        profile = None

    # ── Cached aggregate stats + active classes ────────────────────────────
    stats = cache.get(f'teacher_profile_{teacher_user.pk}_stats') if profile else None
    if profile and stats is None:
        rating_agg = TeacherRating.objects.filter(
            teacher_profile=profile
        ).aggregate(avg=Avg('score'), c=Count('id'))
        # Active (OPEN/FULL but not CLOSED) classes with capacity + per-class rating
        active_classes = list(
            Kelas.objects
            .filter(teacher_profile=profile, is_deleted=False)
            .exclude(status=KelasStatus.CLOSED)
            .annotate(
                active_count=Count(
                    'enrollments',
                    filter=Q(enrollments__status='ACTIVE', enrollments__is_deleted=False),
                    distinct=True,
                ),
                class_avg_rating=Avg('enrollments__teacher_rating__score'),
            )
            .select_related('subject')
            .order_by('-active_count', 'name')[:6]
        )
        for k in active_classes:
            k.slots_remaining = max(0, k.capacity - k.active_count)
            k.capacity_pct = int(round((k.active_count / k.capacity) * 100)) if k.capacity else 0
        total_active = (
            Kelas.objects
            .filter(teacher_profile=profile, is_deleted=False)
            .exclude(status=KelasStatus.CLOSED)
            .count()
        )
        total_students = (
            Enrollment.objects
            .filter(
                kelas__teacher_profile=profile,
                status=EnrollmentStatus.ACTIVE,
                is_deleted=False,
            )
            .values('student_profile').distinct().count()
        )
        stats = {
            'avg_rating': round(rating_agg['avg'] or 0, 1),
            'rating_count': rating_agg['c'] or 0,
            'active_classes': active_classes,
            'total_active_classes': total_active,
            'total_students': total_students,
        }
        cache.set(f'teacher_profile_{teacher_user.pk}_stats', stats, 1800)
    if stats is None:
        stats = {'avg_rating': 0, 'rating_count': 0, 'active_classes': [],
                 'total_active_classes': 0, 'total_students': 0}

    # ── Top reviews + 5-star distribution (cached 30 min) ──────────────────
    reviews_data = cache.get(f'teacher_profile_{teacher_user.pk}_reviews') if profile else None
    if profile and reviews_data is None:
        ratings_qs = (
            TeacherRating.objects
            .filter(teacher_profile=profile)
            .select_related('enrollment__student_profile__user', 'enrollment__kelas')
            .order_by('-created_at')
        )
        dist = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}
        total = 0
        for r in ratings_qs.values_list('score', flat=True):
            bucket = int(round(r))
            if 1 <= bucket <= 5:
                dist[bucket] += 1
            total += 1
        # Pre-build per-star bar percent so template can iterate cleanly
        bars = []
        for star in (5, 4, 3, 2, 1):
            count = dist[star]
            pct = int(round(count / total * 100)) if total else 0
            bars.append({'star': star, 'count': count, 'pct': pct})
        reviews_data = {
            'total': total,
            'distribution': dist,
            'bars': bars,
            'top_reviews': list(ratings_qs[:6]),
        }
        cache.set(f'teacher_profile_{teacher_user.pk}_reviews', reviews_data, 1800)
    if reviews_data is None:
        reviews_data = {'total': 0, 'distribution': {}, 'bars': [], 'top_reviews': []}

    # ── Weekly schedule grid (Phase 3R Grup C) ─────────────────────────────
    # Source: this tutor's REGULAR sessions on or after today that are still
    # SCHEDULED. We derive each cell from session.date.weekday() + start_time
    # (a real Session row → a pickable slot), so taps map to a concrete pk.
    # Time rows = sorted distinct start_times across the visible sessions.
    weekly_grid = None
    if profile:
        from sessions_app.models import (
            Session, SessionBooking, SessionStatus, SessionType, BookingStatus,
        )
        today_d = timezone.localdate()
        upcoming = list(
            Session.objects
            .filter(
                kelas__teacher_profile=profile,
                kelas__is_deleted=False,
                session_type=SessionType.REGULAR,
                status=SessionStatus.SCHEDULED,
                date__gte=today_d,
            )
            .select_related('kelas', 'kelas__subject')
            .order_by('date', 'start_time')
        )

        # Per-viewer state: which of those sessions does the logged-in student
        # already have a BOOKED, non-deleted SessionBooking for? Cheap because
        # we restrict by session_id__in.
        enrolled_session_ids = set()
        viewer_student_level = None
        if request.user.is_authenticated and getattr(request.user, 'role', None) == Role.STUDENT:
            sp = getattr(request.user, 'student_profile', None)
            if sp is not None:
                viewer_student_level = sp.level
                if upcoming:
                    enrolled_session_ids = set(
                        SessionBooking.objects
                        .filter(
                            enrollment__student_profile=sp,
                            session_id__in=[s.pk for s in upcoming],
                            status=BookingStatus.BOOKED,
                            is_deleted=False,
                        )
                        .values_list('session_id', flat=True)
                    )

        # Pre-compute booked counts per session in one query (avoid N+1
        # triggered by Session.booked_count @property in template).
        booked_map = {}
        if upcoming:
            from django.db.models import Count as _Count
            booked_map = dict(
                SessionBooking.objects
                .filter(
                    session_id__in=[s.pk for s in upcoming],
                    status=BookingStatus.BOOKED, is_deleted=False,
                )
                .values('session_id')
                .annotate(n=_Count('id'))
                .values_list('session_id', 'n')
            )

        # Mon-Sat (project convention — no Sun). Indexes match Python's
        # date.weekday(): Mon=0 … Sun=6, so we keep 0..5.
        day_keys = [
            (0, 'Senin', 'Sen'),
            (1, 'Selasa', 'Sel'),
            (2, 'Rabu', 'Rab'),
            (3, 'Kamis', 'Kam'),
            (4, 'Jumat', 'Jum'),
            (5, 'Sabtu', 'Sab'),
        ]

        # cells_by_time[time_str][day_idx] = list of cell dicts (usually 1)
        cells_by_time = {}
        all_times = set()
        for s in upcoming:
            day_idx = s.date.weekday()
            if day_idx > 5:  # skip Sunday
                continue
            t = s.start_time
            if t is None:
                continue
            time_key = t.strftime('%H:%M')
            all_times.add((t, time_key))
            booked = booked_map.get(s.pk, 0)
            cap = s.kelas.capacity or 0
            is_full = cap > 0 and booked >= cap
            is_enrolled = s.pk in enrolled_session_ids
            level_match = (viewer_student_level is None) or (viewer_student_level == s.kelas.level)
            if is_enrolled:
                state = 'enrolled'
            elif is_full:
                state = 'full'
            elif not level_match:
                state = 'wrong_level'
            else:
                state = 'open'
            cell = {
                'session': s,
                'kelas': s.kelas,
                'state': state,
                'booked': booked,
                'capacity': cap,
            }
            cells_by_time.setdefault(time_key, {}).setdefault(day_idx, []).append(cell)

        # Build the final grid rows. Empty cells render as blanks.
        sorted_times = sorted(all_times, key=lambda x: x[0])
        grid_rows = []
        for t_obj, time_key in sorted_times:
            row = {
                'time_label': t_obj.strftime('%H:%M'),
                'cells': [
                    cells_by_time.get(time_key, {}).get(day_idx, [])
                    for day_idx, _, _ in day_keys
                ],
            }
            grid_rows.append(row)

        weekly_grid = {
            'days': day_keys,
            'rows': grid_rows,
            'is_empty': len(grid_rows) == 0,
            'viewer_level': viewer_student_level,
        }

    return render(request, 'academics/teacher_profile.html', {
        'teacher': teacher_user,
        'profile': profile,
        'stats': stats,
        'reviews_data': reviews_data,
        'viewer_is_student': request.user.role == Role.STUDENT,
        'weekly_grid': weekly_grid,
    })


# ─── Teacher "See All" list pages ───────────────────────────────────────────


@role_required('TEACHER')
def teacher_all_students(request):
    """Paginated, filterable list of every student enrolled in teacher's classes.

    Filters: search (name / username / school), status, level, class id.
    """
    from django.core.paginator import Paginator
    from grades.models import Grade
    from sessions_app.models import Attendance, AttendanceStatus
    from django.db.models import FloatField, ExpressionWrapper, IntegerField

    teacher_profile = request.user.teacher_profile

    enrollments = (
        Enrollment.objects
        .filter(
            kelas__teacher_profile=teacher_profile,
            kelas__is_deleted=False,
            is_deleted=False,
        )
        .select_related('student_profile__user', 'kelas__subject')
        .annotate(
            att_total=Count('attendances', distinct=True),
            att_present=Count(
                'attendances',
                filter=Q(attendances__status=AttendanceStatus.PRESENT),
                distinct=True,
            ),
            avg_score=Avg('grades__score'),
        )
    )

    search = (request.GET.get('search') or '').strip()
    status_filter = (request.GET.get('status') or '').strip()
    level_filter = (request.GET.get('level') or '').strip()
    class_filter = (request.GET.get('class') or '').strip()

    if search:
        enrollments = enrollments.filter(
            Q(student_profile__user__first_name__icontains=search)
            | Q(student_profile__user__last_name__icontains=search)
            | Q(student_profile__user__username__icontains=search)
            | Q(student_profile__school_name__icontains=search)
        )
    if status_filter in {EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED, EnrollmentStatus.DROPPED}:
        enrollments = enrollments.filter(status=status_filter)
    if level_filter in {'TK', 'SD', 'SMP', 'SMA', 'UMUM'}:
        enrollments = enrollments.filter(kelas__level=level_filter)
    if class_filter.isdigit():
        enrollments = enrollments.filter(kelas_id=int(class_filter))

    enrollments = enrollments.order_by('-enrolled_at')

    paginator = Paginator(enrollments, 25)
    page_obj = paginator.get_page(request.GET.get('page') or 1)

    # Post-process: attach computed attendance_rate (int %) to each row
    rows = []
    for e in page_obj.object_list:
        rate = round(e.att_present * 100 / e.att_total) if e.att_total else None
        avg = round(float(e.avg_score), 1) if e.avg_score is not None else None
        rows.append({
            'enrollment': e,
            'attendance_rate': rate,
            'avg_score': avg,
        })

    teacher_classes = (
        Kelas.objects
        .filter(teacher_profile=teacher_profile, is_deleted=False)
        .order_by('name')
    )

    qs_preserve = _build_qs(request, drop=['page'])

    return render(request, 'teacher/students_list.html', {
        'page_obj': page_obj,
        'rows': rows,
        'total_count': paginator.count,
        'search': search,
        'status_filter': status_filter,
        'level_filter': level_filter,
        'class_filter': class_filter,
        'teacher_classes': teacher_classes,
        'qs_preserve': qs_preserve,
    })


@role_required('TEACHER')
def teacher_all_sessions(request):
    """Paginated, filterable list of every session in teacher's classes.

    Filters: class id, status, date from/to.
    """
    from django.core.paginator import Paginator
    from sessions_app.models import AttendanceStatus

    teacher_profile = request.user.teacher_profile

    sessions = (
        Session.objects
        .filter(
            kelas__teacher_profile=teacher_profile,
            kelas__is_deleted=False,
        )
        .select_related('kelas__subject', 'kelas__teacher_profile__user')
        .annotate(
            att_total=Count('attendances', distinct=True),
            enrolled_n=Count(
                'kelas__enrollments',
                filter=Q(
                    kelas__enrollments__status=EnrollmentStatus.ACTIVE,
                    kelas__enrollments__is_deleted=False,
                ),
                distinct=True,
            ),
        )
    )

    class_filter = (request.GET.get('class') or '').strip()
    status_filter = (request.GET.get('status') or '').strip()
    date_from = (request.GET.get('date_from') or '').strip()
    date_to = (request.GET.get('date_to') or '').strip()

    if class_filter.isdigit():
        sessions = sessions.filter(kelas_id=int(class_filter))
    if status_filter in {SessionStatus.SCHEDULED, SessionStatus.COMPLETED, SessionStatus.CANCELLED}:
        sessions = sessions.filter(status=status_filter)
    if date_from:
        try:
            sessions = sessions.filter(date__gte=_dt.datetime.strptime(date_from, '%Y-%m-%d').date())
        except ValueError:
            pass
    if date_to:
        try:
            sessions = sessions.filter(date__lte=_dt.datetime.strptime(date_to, '%Y-%m-%d').date())
        except ValueError:
            pass

    sessions = sessions.order_by('-date', 'start_time')

    paginator = Paginator(sessions, 25)
    page_obj = paginator.get_page(request.GET.get('page') or 1)

    teacher_classes = (
        Kelas.objects
        .filter(teacher_profile=teacher_profile, is_deleted=False)
        .order_by('name')
    )

    qs_preserve = _build_qs(request, drop=['page'])

    return render(request, 'teacher/sessions_list.html', {
        'page_obj': page_obj,
        'total_count': paginator.count,
        'class_filter': class_filter,
        'status_filter': status_filter,
        'date_from': date_from,
        'date_to': date_to,
        'teacher_classes': teacher_classes,
        'qs_preserve': qs_preserve,
    })


def _build_qs(request, drop=None):
    """Rebuild the current query string, dropping `drop` keys. For pagination links."""
    drop = set(drop or [])
    parts = []
    for key, value in request.GET.lists():
        if key in drop:
            continue
        for v in value:
            if v:
                parts.append(f'{key}={v}')
    return '&'.join(parts)
