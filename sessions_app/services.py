"""Services for the weekly-slot class model.

Domain rule (confirmed with client):
    A class is one recurring weekly slot. It meets once per week on a single
    day at a fixed time, for a number of weeks. Number of weeks equals number
    of sessions.

generate_sessions_for_kelas() turns a Kelas + its single weekly Schedule into
the exact set of Session rows that slot implies. It is idempotent and refuses
to delete or modify any Session that already has Attendance rows.

All user-facing strings stay in Bahasa Indonesia. Use plain hyphens only (no
em-dash, en-dash, or arrow characters) per the project writing rule.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING

from django.db import transaction
from django.utils import timezone

from .models import (
    Attendance, Session, SessionBooking, SessionStatus, SessionType,
)

if TYPE_CHECKING:
    from academics.models import Kelas


# Day.choices values are MONDAY..SATURDAY (Sunday omitted in the project Day
# enum but date.weekday() returns 0..6 with 6=Sunday; mapping list below.)
_WEEKDAY_TO_DAY = [
    'MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY',
    'FRIDAY', 'SATURDAY', 'SUNDAY',
]
_DAY_TO_WEEKDAY = {name: idx for idx, name in enumerate(_WEEKDAY_TO_DAY)}


def _first_date_on_or_after(start: date, target_weekday: int) -> date:
    """Return the first date >= start whose weekday() matches target_weekday."""
    delta = (target_weekday - start.weekday()) % 7
    return start + timedelta(days=delta)


@transaction.atomic
def generate_sessions_for_kelas(kelas: 'Kelas', regenerate: bool = False) -> int:
    """Generate weekly Session rows for `kelas` from its single Schedule.

    Behavior:
        - Read the single weekly Schedule (day, start_time, end_time).
        - Find the first date on or after kelas.start_date matching that day.
        - Create one Session per week (every 7 days) until kelas.total_sessions
          sessions exist for the kelas. session_number is 1, 2, 3, ...
        - Each session uses the schedule's start_time/end_time,
          session_type=REGULAR, status=COMPLETED if date < today else SCHEDULED.
        - After generating, set kelas.end_date to the date of the last session
          and save.
        - Auto-book every ACTIVE enrollment of the kelas into the resulting
          sessions, re-using sessions_app.views._auto_book_regular_sessions.

    Idempotency:
        - Never create a duplicate session_number for the kelas.
        - Never delete or modify a Session that has Attendance rows.

    regenerate=False (default):
        - Add only missing session_numbers; existing rows are left untouched.
        - end_date is still recomputed from the slot.

    regenerate=True:
        - Delete only future SCHEDULED sessions with NO attendance (and their
          dependent SessionBookings via FK CASCADE).
        - Past sessions, sessions with any Attendance, and cancelled sessions
          are preserved.
        - Then top up missing session_numbers as in the default path.

    Returns:
        The number of Session rows newly created in this call.
    """
    from enrollments.models import Enrollment, EnrollmentStatus
    from sessions_app.views import _auto_book_regular_sessions

    schedule = kelas.schedules.order_by('id').first()
    if schedule is None:
        return 0

    target_weekday = _DAY_TO_WEEKDAY.get(schedule.day)
    if target_weekday is None:
        return 0

    total = int(kelas.total_sessions or 0)
    if total <= 0:
        return 0

    today = timezone.localdate()

    # Step 1: regenerate, if requested, drops only safe (future SCHEDULED, no
    # attendance) sessions. Attended or completed sessions are preserved.
    if regenerate:
        wipeable_ids = list(
            Session.objects
            .filter(
                kelas=kelas,
                status=SessionStatus.SCHEDULED,
                date__gte=today,
            )
            .exclude(attendances__isnull=False)
            .values_list('id', flat=True)
        )
        if wipeable_ids:
            Session.objects.filter(pk__in=wipeable_ids).delete()

    # Step 2: compute the slot's expected dates (per week).
    first_date = _first_date_on_or_after(kelas.start_date, target_weekday)
    expected_dates = [first_date + timedelta(days=7 * i) for i in range(total)]

    # Step 3: build the missing-only insert set, honoring existing
    # session_numbers (never duplicate, never modify, never delete attended).
    existing_by_number = {
        s.session_number: s
        for s in Session.objects.filter(kelas=kelas).only(
            'id', 'session_number', 'date'
        )
    }

    created_count = 0
    last_session_date = None
    for idx, slot_date in enumerate(expected_dates):
        sess_num = idx + 1
        existing = existing_by_number.get(sess_num)
        if existing is not None:
            # Preserve existing row. Use its date for the end_date calc so we
            # honor any holiday-exception reschedules already made.
            last_session_date = existing.date
            continue
        Session.objects.create(
            kelas=kelas,
            session_number=sess_num,
            date=slot_date,
            start_time=schedule.start_time,
            end_time=schedule.end_time,
            topic='',
            capacity=kelas.capacity,
            session_type=SessionType.REGULAR,
            status=(
                SessionStatus.COMPLETED if slot_date < today
                else SessionStatus.SCHEDULED
            ),
        )
        last_session_date = slot_date
        created_count += 1

    # Step 4: sync end_date to the last expected slot date so the class
    # boundary stays consistent with the slot. Use the canonical "last expected
    # date" rather than max(existing) so a partially-attended class that loses
    # future rows still extends correctly.
    canonical_end = expected_dates[-1]
    if kelas.end_date != canonical_end:
        kelas.end_date = canonical_end
        kelas.save(update_fields=['end_date', 'updated_at'])

    # Step 5: every ACTIVE enrollment must be re-booked so newly created
    # sessions get AUTO SessionBookings. For GANJIL_GENAP classes, route to
    # the parity-aware helper so each student only gets bookings on their
    # assigned parity. Idempotent via unique (enrollment, session).
    from academics.models import KelasType
    is_paket = kelas.class_type == KelasType.GANJIL_GENAP
    active_enrollments = list(
        Enrollment.objects.filter(
            kelas=kelas, status=EnrollmentStatus.ACTIVE, is_deleted=False,
        ).order_by('enrolled_at', 'id')
    )
    if is_paket:
        for enr in active_enrollments:
            auto_book_parity_sessions(enr)
    else:
        for enr in active_enrollments:
            _auto_book_regular_sessions(enr)

    return created_count


# ── Ganjil-Genap (parity) helpers ──────────────────────────────────────────

# Module-level seat codes (do not collide with KelasType / sessions enums).
SEAT_GANJIL = 'GANJIL'
SEAT_GENAP = 'GENAP'


def kelas_seat_status(kelas):
    """Return seat occupancy for a GANJIL_GENAP class.

    Reads ACTIVE bookings on REGULAR sessions, groups by enrollment, and
    inspects the parity of the booked session_numbers. A seat is taken if any
    ACTIVE enrollment owns at least one booking on a session of that parity.

    Returns: dict {'GANJIL': enrollment_or_None, 'GENAP': enrollment_or_None}
    """
    from sessions_app.models import BookingStatus, SessionBooking, SessionType
    bookings = (
        SessionBooking.objects
        .filter(
            enrollment__kelas=kelas,
            enrollment__status='ACTIVE',
            enrollment__is_deleted=False,
            status=BookingStatus.BOOKED,
            is_deleted=False,
            session__session_type=SessionType.REGULAR,
        )
        .select_related('enrollment', 'session')
    )
    ganjil_owner = None
    genap_owner = None
    for b in bookings:
        parity = SEAT_GANJIL if (b.session.session_number % 2 == 1) else SEAT_GENAP
        if parity == SEAT_GANJIL and ganjil_owner is None:
            ganjil_owner = b.enrollment
        elif parity == SEAT_GENAP and genap_owner is None:
            genap_owner = b.enrollment
    return {SEAT_GANJIL: ganjil_owner, SEAT_GENAP: genap_owner}


def assign_parity_for_enrollment(enrollment):
    """Pick GANJIL if free, else GENAP if free, else None (capacity reached).

    The current enrollment's existing bookings are ignored when checking who
    occupies which seat, so a re-enroll / re-call is idempotent.
    """
    from sessions_app.models import BookingStatus, SessionBooking, SessionType
    bookings = (
        SessionBooking.objects
        .filter(
            enrollment__kelas=enrollment.kelas,
            enrollment__status='ACTIVE',
            enrollment__is_deleted=False,
            status=BookingStatus.BOOKED,
            is_deleted=False,
            session__session_type=SessionType.REGULAR,
        )
        .exclude(enrollment_id=enrollment.id)
        .select_related('enrollment', 'session')
    )
    ganjil_taken = False
    genap_taken = False
    for b in bookings:
        if b.session.session_number % 2 == 1:
            ganjil_taken = True
        else:
            genap_taken = True
        if ganjil_taken and genap_taken:
            break
    if not ganjil_taken:
        return SEAT_GANJIL
    if not genap_taken:
        return SEAT_GENAP
    return None


def auto_book_parity_sessions(enrollment, seat=None):
    """For a GANJIL_GENAP enrollment, create AUTO bookings only on the
    sessions whose session_number matches the assigned parity.

    If `seat` is None, assigns the first free parity (ganjil before genap).
    Returns: (seat_code, new_booking_count). If no free seat, returns
    (None, 0) without creating any rows.
    """
    from sessions_app.models import (
        BookingKind, BookingStatus, Session, SessionBooking, SessionStatus,
        SessionType,
    )
    if seat is None:
        seat = assign_parity_for_enrollment(enrollment)
    if seat not in (SEAT_GANJIL, SEAT_GENAP):
        return None, 0

    target_parity = 1 if seat == SEAT_GANJIL else 0
    regular_sessions = list(
        Session.objects
        .filter(
            kelas=enrollment.kelas,
            session_type=SessionType.REGULAR,
            status__in=[SessionStatus.SCHEDULED, SessionStatus.COMPLETED],
        )
        .only('id', 'session_number')
    )
    matching = [s for s in regular_sessions if (s.session_number % 2) == target_parity]
    if not matching:
        return seat, 0
    pre = SessionBooking.objects.filter(enrollment=enrollment).count()
    rows = [
        SessionBooking(
            enrollment=enrollment, session=s,
            status=BookingStatus.BOOKED, kind=BookingKind.AUTO,
        )
        for s in matching
    ]
    SessionBooking.objects.bulk_create(rows, ignore_conflicts=True)
    post = SessionBooking.objects.filter(enrollment=enrollment).count()
    return seat, max(0, post - pre)


# ── Slot conflict (teacher level) ──────────────────────────────────────────

def teacher_weekly_slot_conflict(
    teacher_profile,
    day: str,
    start_time,
    end_time,
    exclude_kelas_id: int | None = None,
) -> 'Kelas | None':
    """Return the first non-deleted Kelas this teacher owns whose weekly
    Schedule overlaps the given (day, start_time, end_time) window, or None.

    Overlap uses strict less-than comparisons, so back-to-back slots (one
    ending exactly when the next begins) do not count as conflicts.

    Args:
        exclude_kelas_id: pass the current kelas pk on edit to skip self.
    """
    from academics.models import Kelas

    qs = (
        Kelas.objects
        .filter(
            teacher_profile=teacher_profile,
            is_deleted=False,
            schedules__day=day,
        )
        .distinct()
        .prefetch_related('schedules')
    )
    if exclude_kelas_id:
        qs = qs.exclude(pk=exclude_kelas_id)

    for kelas in qs:
        for sched in kelas.schedules.all():
            if sched.day != day:
                continue
            if start_time < sched.end_time and sched.start_time < end_time:
                return kelas
    return None
