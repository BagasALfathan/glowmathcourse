"""Smoke tests — session + attendance constraints.

  * Session.session_number unique per kelas
  * Attendance unique per (enrollment, session)

Run:  python manage.py test sessions_app
"""
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from accounts.models import User, Role, Level
from academics.models import (
    Category, Subject, AcademicPeriod, Kelas, PeriodType, Quarter,
)
from enrollments.models import Enrollment, EnrollmentStatus
from sessions_app.models import Session, Attendance, AttendanceStatus


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
