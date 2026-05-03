"""
Shared time-aware utility functions for the academics app.
update_expired_classes() is called automatically by StatusUpdateMiddleware on
every authenticated request, cached for 5 minutes via Django's cache framework.
"""
from django.core.cache import cache
from django.db import transaction
from django.db.models import Count, F, Q
from django.utils import timezone

_CACHE_KEY = '_glow_status_update'
_CACHE_TTL = 300  # 5 minutes


# ── Schedule grid constants & helpers ─────────────────────────────────────────

_SCHEDULE_DAYS = [
    ('MONDAY',    'Senin'),
    ('TUESDAY',   'Selasa'),
    ('WEDNESDAY', 'Rabu'),
    ('THURSDAY',  'Kamis'),
    ('FRIDAY',    'Jumat'),
    ('SATURDAY',  'Sabtu'),
]

_SCHEDULE_HOURS = list(range(7, 21))   # 07:00 – 20:00 (14 slots)

_COLOR_PALETTE = [
    'bg-blue-100 text-blue-800 border-blue-200',
    'bg-green-100 text-green-800 border-green-200',
    'bg-purple-100 text-purple-800 border-purple-200',
    'bg-orange-100 text-orange-800 border-orange-200',
    'bg-teal-100 text-teal-800 border-teal-200',
    'bg-pink-100 text-pink-800 border-pink-200',
    'bg-yellow-100 text-yellow-800 border-yellow-200',
    'bg-indigo-100 text-indigo-800 border-indigo-200',
    'bg-rose-100 text-rose-800 border-rose-200',
    'bg-cyan-100 text-cyan-800 border-cyan-200',
]


_CAL_FIRST = 7    # first hour visible in calendar (07:00)
_CAL_LAST = 21    # last hour line (21:00)
_CAL_PX = 64      # pixels per hour


def _has_overlap(st1, et1, st2, et2):
    return st1 < et2 and et1 > st2


def build_calendar_grid(items):
    """
    Compute absolute-position layout for a proportional calendar grid.
    Returns a dict with cal_total_height, cal_hour_labels, cal_days_list.

    Each item in cal_days_list[day].items is a copy of the original dict with
    additional keys: cal_top, cal_height, cal_left_pct, cal_width_pct.
    """
    total_height = (_CAL_LAST - _CAL_FIRST) * _CAL_PX
    hour_labels = [
        {'label': f'{h:02d}:00', 'top': (h - _CAL_FIRST) * _CAL_PX}
        for h in range(_CAL_FIRST, _CAL_LAST + 1)
    ]

    by_day = {day: [] for day, _ in _SCHEDULE_DAYS}
    for item in items:
        day = item['schedule'].day
        if day in by_day:
            by_day[day].append(dict(item))  # shallow copy

    cal_days_list = []
    for day_value, day_label in _SCHEDULE_DAYS:
        day_items = sorted(by_day[day_value], key=lambda x: x['schedule'].start_time)

        # Greedy column assignment: place each item in the first column with no time overlap
        col_slots = []  # col_slots[i] = [(start, end), ...]
        for item in day_items:
            st = item['schedule'].start_time
            et = item['schedule'].end_time
            col = next(
                (i for i, slots in enumerate(col_slots)
                 if not any(_has_overlap(st, et, s, e) for s, e in slots)),
                len(col_slots),
            )
            if col == len(col_slots):
                col_slots.append([])
            col_slots[col].append((st, et))
            item['_cal_col'] = col

        n_cols = max(len(col_slots), 1)
        first_min = _CAL_FIRST * 60
        for item in day_items:
            sched = item['schedule']
            s_min = sched.start_time.hour * 60 + sched.start_time.minute
            e_min = sched.end_time.hour * 60 + sched.end_time.minute
            col = item.pop('_cal_col', 0)
            cal_top = max(0, int((s_min - first_min) * _CAL_PX / 60))
            cal_height = max(int((e_min - s_min) * _CAL_PX / 60), 24)
            cal_height = min(cal_height, total_height - cal_top)
            item['cal_top'] = cal_top
            item['cal_height'] = cal_height
            item['cal_left_pct'] = round(col * 100.0 / n_cols, 2)
            item['cal_width_pct'] = round(100.0 / n_cols, 2)

        cal_days_list.append({'value': day_value, 'label': day_label, 'items': day_items})

    return {
        'cal_total_height': total_height,
        'cal_hour_labels': hour_labels,
        'cal_days_list': cal_days_list,
    }


def build_schedule_grid(items):
    """
    Convert a flat list of schedule item dicts into two structures:

    grid_rows  — list of {hour_label, cells[day0..day5]} for the table grid
    days_list  — list of {value, label, items} for the mobile list view

    Each item dict must contain at minimum:
        'schedule': Schedule instance  (provides .day, .start_time, .end_time, .room)
    Additional keys (kelas, color, enrolled_count …) are passed through untouched.
    """
    grid = {h: {day: [] for day, _ in _SCHEDULE_DAYS} for h in _SCHEDULE_HOURS}
    by_day = {day: [] for day, _ in _SCHEDULE_DAYS}

    for item in items:
        sched = item['schedule']
        h = sched.start_time.hour
        d = sched.day
        if h in grid and d in grid[h]:
            grid[h][d].append(item)
        if d in by_day:
            by_day[d].append(item)

    for day_items in by_day.values():
        day_items.sort(key=lambda x: x['schedule'].start_time)

    grid_rows = [
        {
            'hour_label': f'{h:02d}:00',
            'cells': [grid[h][day] for day, _ in _SCHEDULE_DAYS],
        }
        for h in _SCHEDULE_HOURS
    ]
    days_list = [
        {'value': day, 'label': label, 'items': by_day[day]}
        for day, label in _SCHEDULE_DAYS
    ]
    return grid_rows, days_list


def update_expired_classes():
    """
    Synchronise class, enrollment, and session statuses with today's date.
    Cached for 5 minutes so it runs at most once per 5 minutes per process.

    1. Sessions where date < today and SCHEDULED → COMPLETED
    2. Classes where end_date < today → CLOSED; their ACTIVE enrollments → COMPLETED
    3. Classes where all expected sessions are COMPLETED → CLOSED; ACTIVE → COMPLETED
    """
    if cache.get(_CACHE_KEY):
        return

    from .models import Kelas, KelasStatus
    from enrollments.models import Enrollment, EnrollmentStatus
    from sessions_app.models import Session, SessionStatus

    today = timezone.localdate()

    # Step 1: auto-complete past SCHEDULED sessions
    Session.objects.filter(
        date__lt=today,
        status=SessionStatus.SCHEDULED,
    ).update(status=SessionStatus.COMPLETED)

    # Step 2: auto-close expired classes and complete their enrollments
    expired_qs = Kelas.objects.filter(
        end_date__lt=today,
        is_deleted=False,
    ).exclude(status=KelasStatus.CLOSED)

    if expired_qs.exists():
        with transaction.atomic():
            expired_ids = list(expired_qs.values_list('pk', flat=True))
            Enrollment.objects.filter(
                kelas_id__in=expired_ids,
                status=EnrollmentStatus.ACTIVE,
                is_deleted=False,
            ).update(status=EnrollmentStatus.COMPLETED)
            expired_qs.update(status=KelasStatus.CLOSED)

    # Step 3: auto-close classes where all expected sessions are COMPLETED
    all_done_qs = (
        Kelas.objects
        .filter(is_deleted=False, total_sessions__gt=0)
        .exclude(status=KelasStatus.CLOSED)
        .annotate(
            created_count=Count('sessions', distinct=True),
            completed_count=Count(
                'sessions',
                filter=Q(sessions__status=SessionStatus.COMPLETED),
                distinct=True,
            ),
        )
        .filter(
            created_count=F('total_sessions'),
            completed_count=F('total_sessions'),
        )
    )

    if all_done_qs.exists():
        with transaction.atomic():
            done_ids = list(all_done_qs.values_list('pk', flat=True))
            Enrollment.objects.filter(
                kelas_id__in=done_ids,
                status=EnrollmentStatus.ACTIVE,
                is_deleted=False,
            ).update(status=EnrollmentStatus.COMPLETED)
            Kelas.objects.filter(pk__in=done_ids).update(status=KelasStatus.CLOSED)

    cache.set(_CACHE_KEY, True, timeout=_CACHE_TTL)
