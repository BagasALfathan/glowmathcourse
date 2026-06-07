"""Tests for the batch-based class model.

Coverage:
  * Schema: Session unique (kelas, session_number); Attendance unique
    (enrollment, session).
  * Batch lifecycle (PRIVAT / GROUP / GANJIL_GENAP) including anchor on first
    enrollment, joiner pre-start, joiner blocked after first session, auto-
    completion via sweep, slot reopens, second batch continues numbering.
  * GG parity: A on odd weeks, B on even, 14-day steps, B may join until
    week-2 has happened, B's last session is one week after A's, both
    auto-complete after window end.
  * Makeup: a manually added session inside the window is accepted (the
    check is a pure helper), outside is rejected.
  * Teacher slot exclusivity (per-teacher; back-to-back not overlap).

Run:  python manage.py test sessions_app
"""
from datetime import date, time, timedelta
from unittest import mock

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from accounts.models import Level, Role, User
from academics.models import (
    AcademicPeriod, Category, Kelas, KelasStatus, KelasType, PeriodType,
    Quarter, Schedule, Subject,
)
from enrollments.models import Enrollment, EnrollmentStatus
from sessions_app.models import (
    Attendance, AttendanceStatus, BookingKind, BookingStatus, Session,
    SessionBooking, SessionStatus, SessionType,
)
from sessions_app.services import (
    SEAT_GANJIL, SEAT_GENAP, anchor_new_batch, batch_state,
    book_enrollment_into_current_batch, is_enrollment_open,
    is_makeup_date_inside_window, sweep_finished_batches,
    teacher_weekly_slot_conflict,
)


# ── Helpers ────────────────────────────────────────────────────────────────

def _world():
    teacher = User.objects.create(username='t_world', role=Role.TEACHER)
    cat = Category.objects.create(name='Cat')
    subj = Subject.objects.create(category=cat, name='Subj')
    today = timezone.localdate()
    period = AcademicPeriod.objects.create(
        year='2026', period_type=PeriodType.QUARTER, quarter=Quarter.Q1,
        name='P', start_date=today, end_date=today + timedelta(days=200),
    )
    return teacher, cat, subj, period


def _make_kelas(teacher, subj, period, *, name='K', level=Level.SMA,
                class_type=KelasType.GROUP, total_sessions=4, capacity=8,
                day='MONDAY', start_t=time(10, 0), end_t=time(11, 30)):
    today = timezone.localdate()
    kelas = Kelas.objects.create(
        teacher_profile=teacher.teacher_profile, subject=subj,
        academic_period=period, name=name, level=level,
        class_type=class_type,
        start_date=today, end_date=today,
        capacity=capacity, total_sessions=total_sessions,
        status=KelasStatus.OPEN,
    )
    kelas.set_jenjang([level])
    Schedule.objects.create(
        kelas=kelas, day=day, start_time=start_t, end_time=end_t,
    )
    return kelas


def _make_student(username, level=Level.SMA):
    u = User.objects.create(username=username, role=Role.STUDENT)
    u.student_profile.level = level
    u.student_profile.save(update_fields=['level'])
    return u


# ── Schema constraints ────────────────────────────────────────────────────

class SessionConstraintTests(TestCase):
    def test_session_number_unique_per_kelas(self):
        teacher, _, subj, period = _world()
        kelas = _make_kelas(teacher, subj, period)
        today = timezone.localdate()
        Session.objects.create(kelas=kelas, session_number=1, date=today)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Session.objects.create(kelas=kelas, session_number=1, date=today)


class AttendanceConstraintTests(TestCase):
    def test_attendance_unique_per_enrollment_session(self):
        teacher, _, subj, period = _world()
        kelas = _make_kelas(teacher, subj, period)
        s = _make_student('s_att')
        enr = Enrollment.objects.create(
            student_profile=s.student_profile, kelas=kelas,
            status=EnrollmentStatus.ACTIVE, price_at_enrollment=0,
        )
        session = Session.objects.create(
            kelas=kelas, session_number=1, date=timezone.localdate(),
        )
        Attendance.objects.create(
            enrollment=enr, session=session, status=AttendanceStatus.PRESENT,
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Attendance.objects.create(
                    enrollment=enr, session=session,
                    status=AttendanceStatus.ABSENT,
                )


# ── PRIVAT full lifecycle ─────────────────────────────────────────────────

class PrivatBatchLifecycleTests(TestCase):
    """End-to-end: anchor -> book N sessions -> window passes -> sweep
    completes -> kelas reopens -> second student starts a fresh batch and
    session_number continues."""

    def test_full_lifecycle(self):
        teacher, _, subj, period = _world()
        kelas = _make_kelas(
            teacher, subj, period,
            class_type=KelasType.PRIVAT, capacity=1, total_sessions=4,
            day='MONDAY',
        )
        # No batch anchored yet -> open.
        ok, reason = is_enrollment_open(kelas)
        self.assertTrue(ok, f'should be open, got reason={reason}')

        s_a = _make_student('s_a')
        enr_a = Enrollment.objects.create(
            student_profile=s_a.student_profile, kelas=kelas,
            status=EnrollmentStatus.ACTIVE, price_at_enrollment=0,
        )
        anchor_new_batch(kelas)
        book_enrollment_into_current_batch(enr_a)

        # 4 sessions exist for the kelas, on Mondays, 7 days apart.
        sessions = list(
            Session.objects.filter(kelas=kelas).order_by('session_number')
        )
        self.assertEqual(len(sessions), 4)
        self.assertEqual([s.session_number for s in sessions], [1, 2, 3, 4])
        for s in sessions:
            self.assertEqual(s.date.weekday(), 0, 'Monday')
        for a, b in zip(sessions, sessions[1:]):
            self.assertEqual((b.date - a.date).days, 7)
        # A booked on all 4.
        self.assertEqual(
            SessionBooking.objects.filter(enrollment=enr_a).count(), 4,
        )

        # Capacity 1: second student blocked from joining same batch.
        ok2, reason2 = is_enrollment_open(kelas)
        self.assertFalse(ok2)
        self.assertEqual(reason2, 'FULL')

        # Fast-forward: pretend window has ended.
        fake_today = sessions[-1].date + timedelta(days=1)
        with mock.patch('sessions_app.services.timezone.localdate',
                        return_value=fake_today):
            flipped = sweep_finished_batches(kelas)
            self.assertEqual(flipped, 1)
            enr_a.refresh_from_db()
            self.assertEqual(enr_a.status, EnrollmentStatus.COMPLETED)
            # Kelas stays OPEN (not auto-CLOSED).
            kelas.refresh_from_db()
            self.assertEqual(kelas.status, KelasStatus.OPEN)
            ok3, _ = is_enrollment_open(kelas)
            self.assertTrue(ok3)

            # Second student starts a fresh batch. session_number continues.
            s_b = _make_student('s_b')
            enr_b = Enrollment.objects.create(
                student_profile=s_b.student_profile, kelas=kelas,
                status=EnrollmentStatus.ACTIVE, price_at_enrollment=0,
            )
            anchor_new_batch(kelas)
            book_enrollment_into_current_batch(enr_b)

        nums = list(
            Session.objects.filter(kelas=kelas)
            .order_by('session_number')
            .values_list('session_number', flat=True)
        )
        self.assertEqual(nums, [1, 2, 3, 4, 5, 6, 7, 8])


# ── GROUP lifecycle ──────────────────────────────────────────────────────

class GroupBatchLifecycleTests(TestCase):
    def test_joiner_pre_start_ok_post_start_blocked(self):
        teacher, _, subj, period = _world()
        kelas = _make_kelas(
            teacher, subj, period, class_type=KelasType.GROUP,
            capacity=3, total_sessions=4, day='MONDAY',
        )
        s_a = _make_student('s_a')
        enr_a = Enrollment.objects.create(
            student_profile=s_a.student_profile, kelas=kelas,
            status=EnrollmentStatus.ACTIVE, price_at_enrollment=0,
        )
        anchor_new_batch(kelas)
        book_enrollment_into_current_batch(enr_a)
        state = batch_state(kelas)
        first_date = state['first_session_date']

        # Pre-start: joiner allowed.
        ok, _ = is_enrollment_open(kelas)
        self.assertTrue(ok)

        s_b = _make_student('s_b')
        enr_b = Enrollment.objects.create(
            student_profile=s_b.student_profile, kelas=kelas,
            status=EnrollmentStatus.ACTIVE, price_at_enrollment=0,
        )
        book_enrollment_into_current_batch(enr_b)
        # B booked on the same 4 sessions.
        self.assertEqual(
            SessionBooking.objects.filter(enrollment=enr_b).count(), 4,
        )

        # Now fast-forward past the first session: joiners blocked even with
        # a free seat.
        post_start = first_date + timedelta(days=1)
        with mock.patch('sessions_app.services.timezone.localdate',
                        return_value=post_start):
            ok3, reason3 = is_enrollment_open(kelas)
            self.assertFalse(ok3)
            self.assertEqual(reason3, 'BATCH_RUNNING')

    def test_full_capacity_blocks_pre_start(self):
        teacher, _, subj, period = _world()
        kelas = _make_kelas(
            teacher, subj, period, class_type=KelasType.GROUP,
            capacity=2, total_sessions=4, day='MONDAY',
        )
        for name in ('s_a', 's_b'):
            s = _make_student(name)
            enr = Enrollment.objects.create(
                student_profile=s.student_profile, kelas=kelas,
                status=EnrollmentStatus.ACTIVE, price_at_enrollment=0,
            )
            state = batch_state(kelas)
            if not state['is_anchored']:
                anchor_new_batch(kelas)
            book_enrollment_into_current_batch(enr)
        ok, reason = is_enrollment_open(kelas)
        self.assertFalse(ok)
        self.assertEqual(reason, 'FULL')

    def test_reopen_after_window_ends(self):
        teacher, _, subj, period = _world()
        kelas = _make_kelas(
            teacher, subj, period, class_type=KelasType.GROUP,
            capacity=4, total_sessions=4, day='MONDAY',
        )
        s_a = _make_student('s_a')
        enr_a = Enrollment.objects.create(
            student_profile=s_a.student_profile, kelas=kelas,
            status=EnrollmentStatus.ACTIVE, price_at_enrollment=0,
        )
        anchor_new_batch(kelas)
        book_enrollment_into_current_batch(enr_a)
        state = batch_state(kelas)

        end = state['last_session_date'] + timedelta(days=1)
        with mock.patch('sessions_app.services.timezone.localdate',
                        return_value=end):
            sweep_finished_batches(kelas)
            enr_a.refresh_from_db()
            self.assertEqual(enr_a.status, EnrollmentStatus.COMPLETED)
            ok, _ = is_enrollment_open(kelas)
            self.assertTrue(ok)


# ── GANJIL_GENAP lifecycle ────────────────────────────────────────────────

class GanjilGenapBatchTests(TestCase):
    def test_A_odd_weeks_B_even_weeks_14_day_steps(self):
        teacher, _, subj, period = _world()
        kelas = _make_kelas(
            teacher, subj, period, class_type=KelasType.GANJIL_GENAP,
            capacity=2, total_sessions=3, day='MONDAY',
        )
        s_a = _make_student('s_a')
        enr_a = Enrollment.objects.create(
            student_profile=s_a.student_profile, kelas=kelas,
            status=EnrollmentStatus.ACTIVE, price_at_enrollment=0,
        )
        anchor_new_batch(kelas)
        seat_a, _ = book_enrollment_into_current_batch(enr_a)
        self.assertEqual(seat_a, SEAT_GANJIL)

        # Window = 6 sessions (2 * N).
        sessions = list(
            Session.objects.filter(kelas=kelas).order_by('date')
        )
        self.assertEqual(len(sessions), 6)
        first_date = sessions[0].date

        a_bookings = list(
            SessionBooking.objects.filter(enrollment=enr_a)
            .select_related('session').order_by('session__date')
        )
        # A on weeks 1, 3, 5 -> dates offset 0, 14, 28.
        a_dates = [b.session.date for b in a_bookings]
        self.assertEqual(len(a_dates), 3)
        self.assertEqual(a_dates[0], first_date)
        self.assertEqual(a_dates[1], first_date + timedelta(days=14))
        self.assertEqual(a_dates[2], first_date + timedelta(days=28))

        # B joins; gets GENAP, weeks 2, 4, 6.
        s_b = _make_student('s_b')
        enr_b = Enrollment.objects.create(
            student_profile=s_b.student_profile, kelas=kelas,
            status=EnrollmentStatus.ACTIVE, price_at_enrollment=0,
        )
        seat_b, _ = book_enrollment_into_current_batch(enr_b)
        self.assertEqual(seat_b, SEAT_GENAP)
        b_dates = list(
            SessionBooking.objects.filter(enrollment=enr_b)
            .select_related('session')
            .order_by('session__date')
            .values_list('session__date', flat=True)
        )
        self.assertEqual(len(b_dates), 3)
        self.assertEqual(b_dates[0], first_date + timedelta(days=7))
        self.assertEqual(b_dates[1], first_date + timedelta(days=21))
        self.assertEqual(b_dates[2], first_date + timedelta(days=35))
        # B's last is one week after A's last.
        self.assertEqual(b_dates[-1] - a_dates[-1], timedelta(days=7))

    def test_B_may_join_until_week2_session(self):
        teacher, _, subj, period = _world()
        kelas = _make_kelas(
            teacher, subj, period, class_type=KelasType.GANJIL_GENAP,
            capacity=2, total_sessions=2, day='MONDAY',
        )
        s_a = _make_student('s_a')
        enr_a = Enrollment.objects.create(
            student_profile=s_a.student_profile, kelas=kelas,
            status=EnrollmentStatus.ACTIVE, price_at_enrollment=0,
        )
        anchor_new_batch(kelas)
        book_enrollment_into_current_batch(enr_a)
        state = batch_state(kelas)
        first = state['first_session_date']

        # Today between week 1 and week 2: B may join.
        between = first + timedelta(days=2)
        with mock.patch('sessions_app.services.timezone.localdate',
                        return_value=between):
            ok, reason = is_enrollment_open(kelas)
            self.assertTrue(ok, f'should be open before week-2; got {reason}')

        # Today on/after week 2 session: B cannot join.
        on_week2 = first + timedelta(days=7)
        with mock.patch('sessions_app.services.timezone.localdate',
                        return_value=on_week2):
            ok, reason = is_enrollment_open(kelas)
            self.assertFalse(ok)
            self.assertEqual(reason, 'GG_GENAP_PAST')

    def test_window_auto_completes_both_seats(self):
        teacher, _, subj, period = _world()
        kelas = _make_kelas(
            teacher, subj, period, class_type=KelasType.GANJIL_GENAP,
            capacity=2, total_sessions=2, day='MONDAY',
        )
        s_a = _make_student('s_a')
        s_b = _make_student('s_b')
        enr_a = Enrollment.objects.create(
            student_profile=s_a.student_profile, kelas=kelas,
            status=EnrollmentStatus.ACTIVE, price_at_enrollment=0,
        )
        anchor_new_batch(kelas)
        book_enrollment_into_current_batch(enr_a)
        enr_b = Enrollment.objects.create(
            student_profile=s_b.student_profile, kelas=kelas,
            status=EnrollmentStatus.ACTIVE, price_at_enrollment=0,
        )
        book_enrollment_into_current_batch(enr_b)
        state = batch_state(kelas)

        after = state['last_session_date'] + timedelta(days=1)
        with mock.patch('sessions_app.services.timezone.localdate',
                        return_value=after):
            flipped = sweep_finished_batches(kelas)
            self.assertEqual(flipped, 2)
            enr_a.refresh_from_db()
            enr_b.refresh_from_db()
            self.assertEqual(enr_a.status, EnrollmentStatus.COMPLETED)
            self.assertEqual(enr_b.status, EnrollmentStatus.COMPLETED)


# ── Makeup window constraint ─────────────────────────────────────────────

class MakeupDateInsideWindowTests(TestCase):
    def test_inside_window_accepted_outside_rejected(self):
        teacher, _, subj, period = _world()
        kelas = _make_kelas(
            teacher, subj, period, class_type=KelasType.GROUP,
            capacity=4, total_sessions=4, day='MONDAY',
        )
        s_a = _make_student('s_a')
        enr_a = Enrollment.objects.create(
            student_profile=s_a.student_profile, kelas=kelas,
            status=EnrollmentStatus.ACTIVE, price_at_enrollment=0,
        )
        anchor_new_batch(kelas)
        book_enrollment_into_current_batch(enr_a)
        state = batch_state(kelas)
        first, last = state['first_session_date'], state['last_session_date']

        # On window end: accepted.
        self.assertTrue(is_makeup_date_inside_window(kelas, last))
        # Mid-window: accepted.
        self.assertTrue(is_makeup_date_inside_window(kelas, first + timedelta(days=3)))
        # After window end: rejected.
        self.assertFalse(is_makeup_date_inside_window(kelas, last + timedelta(days=1)))


# ── Teacher slot exclusivity ─────────────────────────────────────────────

class TeacherWeeklySlotConflictTests(TestCase):
    def _build(self, username='t1'):
        teacher = User.objects.create(username=username, role=Role.TEACHER)
        cat = Category.objects.create(name='C-' + username)
        subj = Subject.objects.create(category=cat, name='S-' + username)
        today = timezone.localdate()
        period = AcademicPeriod.objects.create(
            year='2026' + username[-1], period_type=PeriodType.QUARTER,
            quarter=Quarter.Q1, name='P-' + username,
            start_date=today, end_date=today + timedelta(days=120),
        )
        kelas = Kelas.objects.create(
            teacher_profile=teacher.teacher_profile, subject=subj,
            academic_period=period, name='K-' + username,
            level=Level.SMA, start_date=today,
            end_date=today + timedelta(days=56),
            capacity=10, total_sessions=8,
        )
        Schedule.objects.create(
            kelas=kelas, day='MONDAY',
            start_time=time(15, 0), end_time=time(17, 0),
        )
        return teacher.teacher_profile, kelas

    def test_same_teacher_overlap_rejected(self):
        teacher, _kelas = self._build('t1')
        clash = teacher_weekly_slot_conflict(
            teacher, 'MONDAY', time(16, 0), time(18, 0),
        )
        self.assertIsNotNone(clash)

    def test_different_teacher_same_slot_allowed(self):
        self._build('t1')
        t2, k2 = self._build('t2')
        clash = teacher_weekly_slot_conflict(
            t2, 'MONDAY', time(15, 0), time(17, 0),
            exclude_kelas_id=k2.pk,
        )
        self.assertIsNone(clash)

    def test_back_to_back_not_overlap(self):
        teacher, _kelas = self._build('t1')
        clash = teacher_weekly_slot_conflict(
            teacher, 'MONDAY', time(17, 0), time(19, 0),
        )
        self.assertIsNone(clash)
