"""Batch-based class services.

Domain model (client revision):
    A Kelas is a permanent weekly slot owned by a teacher. Each enrollment
    cohort runs through one batch window then auto-completes; the slot
    immediately becomes OPEN for the next batch with no manual teacher
    action.

    A class has a type that drives the batch geometry:
      - PRIVAT       : capacity 1, batch window = N weeks (N == total_sessions)
      - GROUP        : capacity chosen by teacher, batch window = N weeks
      - GANJIL_GENAP : capacity 2, batch window = 2N weeks (the kursi ganjil
                       student takes weeks 1, 3, 5, ...; kursi genap takes
                       weeks 2, 4, 6, ...; each student gets exactly N
                       sessions, 14 days apart; the genap seat may join
                       while the week-2 session is still in the future).

    Batch boundary is derived (no new tables): the EARLIEST date among the
    ACTIVE bookings of ACTIVE enrollments anchors the batch's first session;
    the batch's last session date = anchor + 7 * (window_weeks - 1) days
    where window_weeks = N for PRIVAT/GROUP and 2N for GANJIL_GENAP.

All user-facing strings are Bahasa Indonesia, plain ASCII.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from .models import (
    Attendance, Session, SessionBooking, SessionStatus, SessionType,
    BookingKind, BookingStatus,
)

if TYPE_CHECKING:
    from academics.models import Kelas


_WEEKDAY_TO_DAY = [
    'MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY',
    'FRIDAY', 'SATURDAY', 'SUNDAY',
]
_DAY_TO_WEEKDAY = {name: idx for idx, name in enumerate(_WEEKDAY_TO_DAY)}

# Seat codes for Paket Ganjil Genap (module-level, do not collide with
# KelasType or any session enum).
SEAT_GANJIL = 'GANJIL'
SEAT_GENAP = 'GENAP'


def _first_date_on_or_after(start: date, target_weekday: int) -> date:
    """Return the first date >= start whose weekday() matches target_weekday."""
    delta = (target_weekday - start.weekday()) % 7
    return start + timedelta(days=delta)


def _first_date_strictly_after(today: date, target_weekday: int) -> date:
    """Return the first date > today whose weekday() matches target_weekday."""
    delta = (target_weekday - today.weekday()) % 7
    if delta == 0:
        delta = 7
    return today + timedelta(days=delta)


def _window_weeks(kelas: 'Kelas') -> int:
    """How many weeks the batch window spans for this class type."""
    from academics.models import KelasType
    N = max(int(kelas.total_sessions or 0), 0)
    if kelas.class_type == KelasType.GANJIL_GENAP:
        return 2 * N
    return N


# ── Batch state introspection ────────────────────────────────────────────

def batch_state(kelas: 'Kelas') -> dict:
    """Describe the current batch on this kelas (or report none is running).

    Returns a dict with:
      is_anchored        : bool  - some ACTIVE enrollment owns BOOKED bookings
      is_running         : bool  - today >= first_session_date
      first_session_date : date or None
      last_session_date  : date or None  (= anchor + 7 * (window_weeks - 1))
      next_open_date     : date or None  (= last_session_date + 1 day)
      enrolled_count     : int   - distinct ACTIVE enrollments in batch
      capacity           : int   - kelas.capacity (1 for PRIVAT, 2 for GG)

    Derivation: the batch's first session is the EARLIEST date among ACTIVE
    bookings of ACTIVE enrollments of the kelas. Last = anchor + window
    width. The kelas is OPEN for new enrollment when no batch is anchored.
    """
    from enrollments.models import EnrollmentStatus

    bookings = (
        SessionBooking.objects
        .filter(
            enrollment__kelas=kelas,
            enrollment__status=EnrollmentStatus.ACTIVE,
            enrollment__is_deleted=False,
            status=BookingStatus.BOOKED,
            is_deleted=False,
        )
        .select_related('session')
    )

    enrolled_count = (
        bookings.values('enrollment_id').distinct().count()
    )

    if not bookings.exists():
        # Anchor may exist via SCHEDULED future sessions even before the first
        # booking lands (anchor_new_batch creates sessions, then the first
        # book_enrollment_into_current_batch call would otherwise see no
        # batch). Find the EARLIEST future SCHEDULED session and treat that
        # as the batch first_date.
        fallback = (
            Session.objects
            .filter(
                kelas=kelas,
                status=SessionStatus.SCHEDULED,
                session_type=SessionType.REGULAR,
                date__gte=timezone.localdate(),
            )
            .order_by('date')
            .first()
        )
        if fallback is None:
            return {
                'is_anchored': False,
                'is_running': False,
                'first_session_date': None,
                'last_session_date': None,
                'next_open_date': None,
                'enrolled_count': 0,
                'capacity': kelas.capacity,
            }
        first_date = fallback.date
        window_w = _window_weeks(kelas)
        last_date = first_date + timedelta(days=7 * max(window_w - 1, 0))
        return {
            'is_anchored': True,
            'is_running': timezone.localdate() >= first_date,
            'first_session_date': first_date,
            'last_session_date': last_date,
            'next_open_date': last_date + timedelta(days=1),
            'enrolled_count': 0,
            'capacity': kelas.capacity,
        }

    first_date = min(b.session.date for b in bookings)
    window_w = _window_weeks(kelas)
    if window_w <= 0:
        return {
            'is_anchored': True,
            'is_running': True,
            'first_session_date': first_date,
            'last_session_date': first_date,
            'next_open_date': first_date + timedelta(days=1),
            'enrolled_count': enrolled_count,
            'capacity': kelas.capacity,
        }
    last_date = first_date + timedelta(days=7 * (window_w - 1))
    today = timezone.localdate()
    return {
        'is_anchored': True,
        'is_running': today >= first_date,
        'first_session_date': first_date,
        'last_session_date': last_date,
        'next_open_date': last_date + timedelta(days=1),
        'enrolled_count': enrolled_count,
        'capacity': kelas.capacity,
    }


def next_slot_date(kelas: 'Kelas', after: date | None = None) -> date | None:
    """Next slot occurrence strictly after `after` (default: today).

    Returns None if the kelas has no Schedule.
    """
    schedule = kelas.schedules.order_by('id').first()
    if schedule is None:
        return None
    target_weekday = _DAY_TO_WEEKDAY.get(schedule.day)
    if target_weekday is None:
        return None
    base = after if after is not None else timezone.localdate()
    return _first_date_strictly_after(base, target_weekday)


def estimated_completion_date(kelas: 'Kelas', first_date: date) -> date:
    """Date of the last session in a window that begins at `first_date`."""
    weeks = _window_weeks(kelas)
    if weeks <= 0:
        return first_date
    return first_date + timedelta(days=7 * (weeks - 1))


# ── Enrollment-driven batch operations ────────────────────────────────────

def is_enrollment_open(kelas: 'Kelas', for_student_profile=None) -> tuple[bool, str]:
    """May a new student enroll into this kelas right now?

    Returns (ok, reason_id). reason_id is one of:
      ''                  - ok
      'CLOSED'            - kelas.status == CLOSED (teacher retired the slot)
      'BATCH_RUNNING'     - batch first session has happened, no joining
      'FULL'              - capacity reached for current batch
      'GG_GENAP_PAST'     - GG batch's week-2 session has already happened
    """
    from academics.models import KelasStatus, KelasType
    if kelas.status == KelasStatus.CLOSED:
        return False, 'CLOSED'
    state = batch_state(kelas)
    if not state['is_anchored']:
        return True, ''
    today = timezone.localdate()
    cap = kelas.capacity
    if kelas.class_type == KelasType.GANJIL_GENAP:
        # Both seats taken?
        if state['enrolled_count'] >= cap:
            return False, 'FULL'
        # Genap seat free. Week-2 session date = first_date + 7 days.
        week2 = state['first_session_date'] + timedelta(days=7)
        if today >= week2:
            return False, 'GG_GENAP_PAST'
        return True, ''
    # PRIVAT / GROUP
    if state['enrolled_count'] >= cap:
        return False, 'FULL'
    if state['is_running']:
        return False, 'BATCH_RUNNING'
    return True, ''


@transaction.atomic
def anchor_new_batch(kelas: 'Kelas') -> dict:
    """Create the Session rows for a fresh batch on this kelas.

    First session date = next slot occurrence strictly after today.
    For PRIVAT/GROUP: generates N sessions, 7 days apart.
    For GANJIL_GENAP: generates 2N sessions (the full window).

    session_number continues from kelas's current max session_number so the
    unique (kelas, session_number) constraint is preserved across batches.

    Updates kelas.end_date to the new batch's last session date so existing
    callers that read it still see something reasonable.

    Returns: dict with first_session_date, last_session_date, sessions_created.
    """
    schedule = kelas.schedules.order_by('id').first()
    if schedule is None:
        return {
            'first_session_date': None, 'last_session_date': None,
            'sessions_created': 0,
        }
    target_weekday = _DAY_TO_WEEKDAY.get(schedule.day)
    if target_weekday is None:
        return {
            'first_session_date': None, 'last_session_date': None,
            'sessions_created': 0,
        }
    today = timezone.localdate()
    first_date = _first_date_strictly_after(today, target_weekday)

    weeks = _window_weeks(kelas)
    if weeks <= 0:
        return {
            'first_session_date': first_date, 'last_session_date': first_date,
            'sessions_created': 0,
        }

    max_num = (
        Session.objects.filter(kelas=kelas)
        .aggregate(m=Max('session_number'))['m']
        or 0
    )

    new_rows = []
    for i in range(weeks):
        new_rows.append(Session(
            kelas=kelas,
            session_number=max_num + i + 1,
            date=first_date + timedelta(days=7 * i),
            start_time=schedule.start_time,
            end_time=schedule.end_time,
            topic='',
            capacity=kelas.capacity,
            session_type=SessionType.REGULAR,
            status=SessionStatus.SCHEDULED,
        ))
    Session.objects.bulk_create(new_rows, ignore_conflicts=True)

    last_date = first_date + timedelta(days=7 * (weeks - 1))
    if kelas.end_date != last_date:
        kelas.end_date = last_date
        kelas.save(update_fields=['end_date', 'updated_at'])

    return {
        'first_session_date': first_date,
        'last_session_date': last_date,
        'sessions_created': len(new_rows),
    }


def book_enrollment_into_current_batch(enrollment, seat: str | None = None):
    """Create AUTO bookings for `enrollment` over the current batch sessions.

    Returns (seat_code, new_booking_count). seat_code is None for
    PRIVAT/GROUP and SEAT_GANJIL/SEAT_GENAP for GANJIL_GENAP.

    Pre-condition: the batch has been anchored (anchor_new_batch ran). If no
    batch is anchored, returns (None, 0) so the caller can decide to anchor.
    """
    from academics.models import KelasType
    kelas = enrollment.kelas
    state = batch_state(kelas)
    if not state['is_anchored']:
        return None, 0
    first_date = state['first_session_date']
    last_date = state['last_session_date']

    batch_sessions = list(
        Session.objects.filter(
            kelas=kelas,
            date__gte=first_date,
            date__lte=last_date,
            session_type=SessionType.REGULAR,
        ).order_by('date')
    )
    if not batch_sessions:
        return seat, 0

    if kelas.class_type == KelasType.GANJIL_GENAP:
        if seat is None:
            seat = _assign_parity_for_batch(enrollment, batch_sessions, first_date)
        if seat not in (SEAT_GANJIL, SEAT_GENAP):
            return None, 0
        matching = [
            s for s in batch_sessions
            if _parity_for_session(s, first_date) == seat
        ]
        pre = SessionBooking.objects.filter(enrollment=enrollment).count()
        SessionBooking.objects.bulk_create(
            [
                SessionBooking(
                    enrollment=enrollment, session=s,
                    status=BookingStatus.BOOKED, kind=BookingKind.AUTO,
                )
                for s in matching
            ],
            ignore_conflicts=True,
        )
        post = SessionBooking.objects.filter(enrollment=enrollment).count()
        return seat, max(0, post - pre)

    # PRIVAT / GROUP: book ALL batch sessions
    pre = SessionBooking.objects.filter(enrollment=enrollment).count()
    SessionBooking.objects.bulk_create(
        [
            SessionBooking(
                enrollment=enrollment, session=s,
                status=BookingStatus.BOOKED, kind=BookingKind.AUTO,
            )
            for s in batch_sessions
        ],
        ignore_conflicts=True,
    )
    post = SessionBooking.objects.filter(enrollment=enrollment).count()
    return None, max(0, post - pre)


def _parity_for_session(session, first_date: date) -> str:
    """Return SEAT_GANJIL if the session falls on weeks 1, 3, 5, ...; else
    SEAT_GENAP."""
    offset_days = (session.date - first_date).days
    week_index = offset_days // 7  # 0 = week 1, 1 = week 2, ...
    return SEAT_GANJIL if (week_index % 2 == 0) else SEAT_GENAP


def _assign_parity_for_batch(enrollment, batch_sessions, first_date):
    """Pick GANJIL if free in this batch, else GENAP if free, else None."""
    other_bookings = SessionBooking.objects.filter(
        enrollment__kelas=enrollment.kelas,
        enrollment__status='ACTIVE',
        enrollment__is_deleted=False,
        status=BookingStatus.BOOKED,
        is_deleted=False,
        session__in=batch_sessions,
    ).exclude(enrollment_id=enrollment.id).select_related('session')

    ganjil_taken = False
    genap_taken = False
    for b in other_bookings:
        p = _parity_for_session(b.session, first_date)
        if p == SEAT_GANJIL:
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


# ── Sweep finished batches ────────────────────────────────────────────────

@transaction.atomic
def sweep_finished_batches(kelas: 'Kelas') -> int:
    """When the current batch's window has ended, auto-complete every ACTIVE
    enrollment of the kelas.

    Returns the number of enrollments flipped to COMPLETED.

    Called inline from class_browse, class_detail, enroll, teacher class
    pages (cheap, idempotent). Also called by the
    `python manage.py close_finished_batches` cron command.
    """
    from enrollments.models import Enrollment, EnrollmentStatus

    state = batch_state(kelas)
    if not state['is_anchored']:
        return 0
    if state['last_session_date'] is None:
        return 0
    if timezone.localdate() <= state['last_session_date']:
        return 0
    flipped = Enrollment.objects.filter(
        kelas=kelas,
        status=EnrollmentStatus.ACTIVE,
        is_deleted=False,
    ).update(status=EnrollmentStatus.COMPLETED)
    return flipped


# ── Seat status (Paket Ganjil Genap UI) ───────────────────────────────────

def kelas_seat_status(kelas: 'Kelas') -> dict:
    """Return seat occupancy for a GANJIL_GENAP class.

    Reads ACTIVE bookings on the CURRENT batch's sessions and groups by
    enrollment.

    Returns dict {'GANJIL': enrollment_or_None, 'GENAP': enrollment_or_None}.
    """
    state = batch_state(kelas)
    if not state['is_anchored']:
        return {SEAT_GANJIL: None, SEAT_GENAP: None}
    first_date = state['first_session_date']
    last_date = state['last_session_date']
    batch_sessions = list(
        Session.objects.filter(
            kelas=kelas,
            date__gte=first_date,
            date__lte=last_date,
            session_type=SessionType.REGULAR,
        )
    )
    bookings = (
        SessionBooking.objects
        .filter(
            enrollment__kelas=kelas,
            enrollment__status='ACTIVE',
            enrollment__is_deleted=False,
            status=BookingStatus.BOOKED,
            is_deleted=False,
            session__in=batch_sessions,
        )
        .select_related('enrollment', 'session')
    )
    ganjil_owner = None
    genap_owner = None
    for b in bookings:
        p = _parity_for_session(b.session, first_date)
        if p == SEAT_GANJIL and ganjil_owner is None:
            ganjil_owner = b.enrollment
        elif p == SEAT_GENAP and genap_owner is None:
            genap_owner = b.enrollment
        if ganjil_owner and genap_owner:
            break
    return {SEAT_GANJIL: ganjil_owner, SEAT_GENAP: genap_owner}


# ── Makeup constraint ─────────────────────────────────────────────────────

def is_makeup_date_inside_window(kelas: 'Kelas', makeup_date: date) -> bool:
    """A makeup session must land on or before the current batch's window
    end. Returns True if `makeup_date <= last_session_date` of the running
    batch. If no batch is anchored, returns False (no batch, nothing to
    make up against).
    """
    state = batch_state(kelas)
    if not state['is_anchored'] or state['last_session_date'] is None:
        return False
    return makeup_date <= state['last_session_date']


# ── Teacher slot conflict (unchanged from prior model) ────────────────────

def teacher_weekly_slot_conflict(
    teacher_profile,
    day: str,
    start_time,
    end_time,
    exclude_kelas_id: int | None = None,
) -> 'Kelas | None':
    """Return the first non-deleted Kelas this teacher owns whose weekly
    Schedule overlaps the given (day, start_time, end_time) window, or None.

    Overlap uses strict less-than comparisons - back-to-back slots (one
    ending exactly when the next begins) are NOT a conflict. The rule is
    per-teacher; multi-jenjang in one slot is the supported way to teach
    several jenjang simultaneously.
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


# ── Backward-compat shims ─────────────────────────────────────────────────
#
# Older callers (teacher_class_edit, teacher_regenerate_sessions, the demo
# seeders) called `generate_sessions_for_kelas`. With the batch model
# sessions are created on first enrollment by `anchor_new_batch`; there is
# nothing to pre-generate at class-create time. These shims let the existing
# call sites keep compiling and behave sensibly:
#
#   - If no batch is anchored: return 0 without creating sessions. The first
#     enrollment will anchor.
#   - If a batch IS anchored: refuse to touch anything (the sessions are
#     already in place). Returns 0.

def generate_sessions_for_kelas(kelas: 'Kelas', regenerate: bool = False) -> int:
    """Compat shim. In the batch model the first enrollee anchors a batch
    and creates its Session rows; this function intentionally creates
    nothing on its own. Kept so call sites compile without rewrite.
    """
    return 0


# Legacy parity helper alias used by enrollments.views and student_pick_session
# until those call sites switch fully to book_enrollment_into_current_batch.
def auto_book_parity_sessions(enrollment, seat: str | None = None):
    """Compat shim: route to the new batch helper."""
    return book_enrollment_into_current_batch(enrollment, seat=seat)


def assign_parity_for_enrollment(enrollment):
    """Compat shim: pick a free seat for the current batch."""
    state = batch_state(enrollment.kelas)
    if not state['is_anchored']:
        return SEAT_GANJIL  # new batch will give first enrollee ganjil
    first_date = state['first_session_date']
    last_date = state['last_session_date']
    batch_sessions = list(
        Session.objects.filter(
            kelas=enrollment.kelas,
            date__gte=first_date, date__lte=last_date,
            session_type=SessionType.REGULAR,
        )
    )
    return _assign_parity_for_batch(enrollment, batch_sessions, first_date)
