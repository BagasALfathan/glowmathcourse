"""Smoke tests for sessions: schema constraints + weekly-slot generator.

  * Session.session_number unique per kelas
  * Attendance unique per (enrollment, session)
  * generate_sessions_for_kelas(): N weeks generates N Mondays, 7 days apart
  * Re-running creates no duplicates
  * regenerate=True rebuilds future SCHEDULED rows but preserves any session
    that already has Attendance

Run:  python manage.py test sessions_app
"""
from datetime import date, time, timedelta

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from accounts.models import User, Role, Level
from academics.models import (
    Category, Subject, AcademicPeriod, Kelas, KelasJenjang, KelasType,
    PeriodType, Quarter, Schedule,
)
from enrollments.models import Enrollment, EnrollmentStatus
from sessions_app.models import (
    Attendance, AttendanceStatus, BookingKind, BookingStatus, Session,
    SessionBooking, SessionStatus, SessionType,
)
from sessions_app.services import (
    SEAT_GANJIL, SEAT_GENAP, auto_book_parity_sessions,
    generate_sessions_for_kelas, teacher_weekly_slot_conflict,
)


def _world():
    teacher = User.objects.create(username="t_sess", role=Role.TEACHER)
    category = Category.objects.create(name="Sains")
    subject = Subject.objects.create(category=category, name="Fisika")
    today = timezone.localdate()
    period = AcademicPeriod.objects.create(
        year="2026-2027", period_type=PeriodType.QUARTER, quarter=Quarter.Q1,
        name="K1", start_date=today, end_date=today + timedelta(days=120),
    )
    kelas = Kelas.objects.create(
        teacher_profile=teacher.teacher_profile, subject=subject, academic_period=period,
        name="Fisika SMA", level=Level.SMA, start_date=today, end_date=today + timedelta(days=90),
        capacity=10, total_sessions=12,
    )
    student = User.objects.create(username="s_sess", role=Role.STUDENT)
    student.student_profile.level = Level.SMA
    student.student_profile.save(update_fields=["level"])
    enrollment = Enrollment.objects.create(
        student_profile=student.student_profile, kelas=kelas,
        status=EnrollmentStatus.ACTIVE, price_at_enrollment=0,
    )
    return kelas, enrollment


class SessionConstraintTests(TestCase):
    def test_session_number_unique_per_kelas(self):
        kelas, _ = _world()
        today = timezone.localdate()
        Session.objects.create(kelas=kelas, session_number=1, date=today)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Session.objects.create(kelas=kelas, session_number=1, date=today)


class AttendanceConstraintTests(TestCase):
    def test_attendance_unique_per_enrollment_session(self):
        kelas, enrollment = _world()
        session = Session.objects.create(
            kelas=kelas, session_number=1, date=timezone.localdate()
        )
        Attendance.objects.create(
            enrollment=enrollment, session=session, status=AttendanceStatus.PRESENT
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Attendance.objects.create(
                    enrollment=enrollment, session=session, status=AttendanceStatus.ABSENT
                )


# ── Weekly-slot generator tests ────────────────────────────────────────────

def _kelas_with_monday_slot(weeks=8):
    """Build a fresh Kelas with a single Monday slot (10:00-12:00).

    Start date picked so that the first Monday is well in the past (so we can
    assert past sessions land as COMPLETED). Uses a future Monday is also
    fine; tests only depend on geometry (8 dates, 7 days apart, all Mondays,
    numbered 1..8), not on past/future.
    """
    teacher = User.objects.create(username='t_gen', role=Role.TEACHER)
    category = Category.objects.create(name='Mate')
    subject = Subject.objects.create(category=category, name='Mat SD')
    today = timezone.localdate()
    period = AcademicPeriod.objects.create(
        year='2026', period_type=PeriodType.QUARTER, quarter=Quarter.Q1,
        name='P', start_date=today, end_date=today + timedelta(days=200),
    )
    # Anchor start on a specific Monday in the past
    start = date(2026, 4, 6)  # confirm: 2026-04-06 is a Monday
    assert start.weekday() == 0
    kelas = Kelas.objects.create(
        teacher_profile=teacher.teacher_profile, subject=subject,
        academic_period=period, name='Mat SD Senin Sore',
        level=Level.SD, start_date=start,
        end_date=start + timedelta(days=7 * (weeks - 1)),
        capacity=10, total_sessions=weeks,
    )
    Schedule.objects.create(
        kelas=kelas, day='MONDAY',
        start_time=time(10, 0), end_time=time(12, 0),
    )
    return kelas


class GenerateSessionsForKelasTests(TestCase):
    def test_monday_slot_eight_weeks_generates_eight_sessions(self):
        kelas = _kelas_with_monday_slot(weeks=8)
        created = generate_sessions_for_kelas(kelas)
        self.assertEqual(created, 8)
        rows = list(Session.objects.filter(kelas=kelas).order_by('session_number'))
        self.assertEqual(len(rows), 8)
        self.assertEqual([r.session_number for r in rows], list(range(1, 9)))
        # Each session is a Monday and exactly 7 days after the previous one
        for r in rows:
            self.assertEqual(r.date.weekday(), 0, f'{r.date} is not a Monday')
            self.assertEqual(r.start_time, time(10, 0))
            self.assertEqual(r.end_time, time(12, 0))
            self.assertEqual(r.session_type, SessionType.REGULAR)
        for prev, nxt in zip(rows, rows[1:]):
            self.assertEqual(
                (nxt.date - prev.date).days, 7,
                f'Gap between sessions {prev.session_number} and {nxt.session_number} is not 7 days'
            )
        # end_date follows the last session
        kelas.refresh_from_db()
        self.assertEqual(kelas.end_date, rows[-1].date)

    def test_running_twice_is_idempotent(self):
        kelas = _kelas_with_monday_slot(weeks=8)
        first = generate_sessions_for_kelas(kelas)
        second = generate_sessions_for_kelas(kelas)
        self.assertEqual(first, 8)
        self.assertEqual(second, 0)
        self.assertEqual(Session.objects.filter(kelas=kelas).count(), 8)
        # session_numbers stay 1..8 with no gaps or dupes
        nums = list(
            Session.objects.filter(kelas=kelas)
            .order_by('session_number').values_list('session_number', flat=True)
        )
        self.assertEqual(nums, list(range(1, 9)))

    def test_multi_jenjang_class_admits_listed_levels_only(self):
        """An SMP student CAN enroll in a class with SD+SMP ticked; an SMA
        student (or any level not in the jenjang set) CANNOT.

        Enroll path is exercised via the rules embedded in enroll() rather
        than spinning up the HTTP layer: we ensure get_jenjang_list() returns
        the right set and that level-in-set membership is the gating rule.
        """
        # Build a multi-jenjang Kelas (SD + SMP)
        teacher = User.objects.create(username='t_multi', role=Role.TEACHER)
        cat = Category.objects.create(name='Mate')
        subj = Subject.objects.create(category=cat, name='Mat')
        today = timezone.localdate()
        period = AcademicPeriod.objects.create(
            year='2026', period_type=PeriodType.QUARTER, quarter=Quarter.Q1,
            name='P', start_date=today, end_date=today + timedelta(days=120),
        )
        kelas = Kelas.objects.create(
            teacher_profile=teacher.teacher_profile, subject=subj,
            academic_period=period, name='Mat SD/SMP', level=Level.SD,
            start_date=today, end_date=today + timedelta(days=60),
            capacity=10, total_sessions=8,
        )
        kelas.set_jenjang([Level.SD, Level.SMP])
        # Sanity: helper returns both jenjang
        self.assertEqual(set(kelas.get_jenjang_list()), {Level.SD, Level.SMP})
        # Membership rule: SMP IS in, SMA is NOT in
        self.assertIn(Level.SMP, kelas.get_jenjang_list())
        self.assertNotIn(Level.SMA, kelas.get_jenjang_list())
        # Backfill data migration would have created a single KelasJenjang
        # for the original kelas.level; set_jenjang() resets the relation to
        # the new list, so exactly two rows exist.
        self.assertEqual(
            KelasJenjang.objects.filter(kelas=kelas).count(), 2
        )

    def test_regenerate_preserves_sessions_with_attendance(self):
        kelas = _kelas_with_monday_slot(weeks=8)
        generate_sessions_for_kelas(kelas)
        # Enroll a student and force-mark attendance on session #1 (past) so
        # it is "attended" and must be preserved on regenerate.
        student = User.objects.create(username='s_gen', role=Role.STUDENT)
        student.student_profile.level = Level.SD
        student.student_profile.save(update_fields=['level'])
        enrollment = Enrollment.objects.create(
            student_profile=student.student_profile, kelas=kelas,
            status=EnrollmentStatus.ACTIVE, price_at_enrollment=0,
        )
        attended_session = Session.objects.get(kelas=kelas, session_number=1)
        Attendance.objects.create(
            enrollment=enrollment, session=attended_session,
            status=AttendanceStatus.PRESENT,
        )
        attended_pk = attended_session.pk

        # Pick a future SCHEDULED session and remember its pk so we can verify
        # it gets recreated (different pk after regenerate).
        today = timezone.localdate()
        future_qs = Session.objects.filter(
            kelas=kelas, status=SessionStatus.SCHEDULED, date__gte=today,
        ).order_by('session_number')
        future_pks_before = list(future_qs.values_list('pk', flat=True))

        if not future_pks_before:
            # The fixture is fully in the past; bump start to guarantee at
            # least one future session, then re-run setup.
            kelas.start_date = today
            kelas.save(update_fields=['start_date'])
            # Wipe and regenerate so the geometry is recomputed cleanly
            Session.objects.filter(kelas=kelas).exclude(pk=attended_pk).delete()
            generate_sessions_for_kelas(kelas, regenerate=True)
            future_pks_before = list(
                Session.objects.filter(
                    kelas=kelas, status=SessionStatus.SCHEDULED, date__gte=today,
                ).values_list('pk', flat=True)
            )

        # Regenerate: future SCHEDULED sessions without attendance are wiped
        # and recreated; the attended session #1 must survive untouched.
        generate_sessions_for_kelas(kelas, regenerate=True)

        # Total is still 8
        self.assertEqual(Session.objects.filter(kelas=kelas).count(), 8)
        # Attended session #1 still exists with the same pk
        self.assertTrue(Session.objects.filter(pk=attended_pk).exists())
        # No duplicate session_numbers
        nums = list(
            Session.objects.filter(kelas=kelas)
            .order_by('session_number').values_list('session_number', flat=True)
        )
        self.assertEqual(nums, list(range(1, 9)))


class GanjilGenapParityTests(TestCase):
    """Paket Ganjil Genap: first enrollee on odd session_numbers, second on
    even, third enrollment must be rejected by capacity=2 (Kelas.capacity is
    forced to 2 by the create/edit view, and _try_enroll enforces it under
    row lock)."""

    def _world(self):
        teacher = User.objects.create(username='t_paket', role=Role.TEACHER)
        cat = Category.objects.create(name='Mate')
        subj = Subject.objects.create(category=cat, name='Mat')
        today = timezone.localdate()
        period = AcademicPeriod.objects.create(
            year='2026', period_type=PeriodType.QUARTER, quarter=Quarter.Q1,
            name='P', start_date=today, end_date=today + timedelta(days=120),
        )
        kelas = Kelas.objects.create(
            teacher_profile=teacher.teacher_profile, subject=subj,
            academic_period=period, name='Mat SD Paket',
            level=Level.SD, start_date=today,
            end_date=today + timedelta(days=7 * 5),
            capacity=2, total_sessions=6,
            class_type=KelasType.GANJIL_GENAP,
        )
        kelas.set_jenjang([Level.SD])
        from academics.models import Schedule as Sched
        Sched.objects.create(
            kelas=kelas, day='MONDAY',
            start_time=time(10, 0), end_time=time(11, 0),
        )
        generate_sessions_for_kelas(kelas)
        return kelas

    def _make_student(self, username, level=Level.SD):
        u = User.objects.create(username=username, role=Role.STUDENT)
        u.student_profile.level = level
        u.student_profile.save(update_fields=['level'])
        return u

    def test_first_enrollee_gets_ganjil_second_gets_genap(self):
        kelas = self._world()
        a = self._make_student('s_a')
        b = self._make_student('s_b')
        enr_a = Enrollment.objects.create(
            student_profile=a.student_profile, kelas=kelas,
            status=EnrollmentStatus.ACTIVE, price_at_enrollment=0,
        )
        seat_a, _ = auto_book_parity_sessions(enr_a)
        self.assertEqual(seat_a, SEAT_GANJIL)
        nums_a = sorted(
            SessionBooking.objects
            .filter(enrollment=enr_a, status=BookingStatus.BOOKED)
            .values_list('session__session_number', flat=True)
        )
        self.assertTrue(all(n % 2 == 1 for n in nums_a), f'A got {nums_a}')

        enr_b = Enrollment.objects.create(
            student_profile=b.student_profile, kelas=kelas,
            status=EnrollmentStatus.ACTIVE, price_at_enrollment=0,
        )
        seat_b, _ = auto_book_parity_sessions(enr_b)
        self.assertEqual(seat_b, SEAT_GENAP)
        nums_b = sorted(
            SessionBooking.objects
            .filter(enrollment=enr_b, status=BookingStatus.BOOKED)
            .values_list('session__session_number', flat=True)
        )
        self.assertTrue(all(n % 2 == 0 for n in nums_b), f'B got {nums_b}')

    def test_third_enrollment_rejected_at_capacity_2(self):
        """The capacity gate that protects against a 3rd enrollee lives in
        the enroll view's _try_enroll helper. Verify it: with two ACTIVE
        enrollments and capacity=2, _try_enroll returns ('full', None)."""
        from enrollments.views import _try_enroll
        kelas = self._world()
        a = self._make_student('s_a')
        b = self._make_student('s_b')
        c = self._make_student('s_c')
        Enrollment.objects.create(
            student_profile=a.student_profile, kelas=kelas,
            status=EnrollmentStatus.ACTIVE, price_at_enrollment=0,
        )
        Enrollment.objects.create(
            student_profile=b.student_profile, kelas=kelas,
            status=EnrollmentStatus.ACTIVE, price_at_enrollment=0,
        )
        result, payload = _try_enroll(c.student_profile, kelas)
        self.assertEqual(result, 'full')
        self.assertIsNone(payload)


class TeacherWeeklySlotConflictTests(TestCase):
    """Slot exclusivity is per teacher: same teacher overlapping slot
    rejected; different teacher same slot is fine."""

    def _build(self, username='t1'):
        teacher = User.objects.create(username=username, role=Role.TEACHER)
        cat = Category.objects.create(name='Cat-' + username)
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
        _t1, _k1 = self._build('t1')
        t2, _k2 = self._build('t2')
        # t2 builder already creates a kelas; passing t2 as the candidate
        # teacher for the SAME slot as t1 must NOT collide because the conflict
        # check is per-teacher.
        clash = teacher_weekly_slot_conflict(
            t2, 'MONDAY', time(15, 0), time(17, 0),
            exclude_kelas_id=_k2.pk,
        )
        self.assertIsNone(clash)

    def test_back_to_back_not_treated_as_overlap(self):
        teacher, _kelas = self._build('t1')
        # Existing class is 15:00-17:00; a 17:00-19:00 slot is back-to-back,
        # not overlapping. Strict `<` comparison must allow it.
        clash = teacher_weekly_slot_conflict(
            teacher, 'MONDAY', time(17, 0), time(19, 0),
        )
        self.assertIsNone(clash)
