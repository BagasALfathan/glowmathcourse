"""Smoke tests — grade validation rules (grades.models.Grade).

  * QUIZ / ASSIGNMENT require a session (Grade.clean)
  * MIDTERM / FINAL do not require a session
  * score must be within 0..100 (validators run on full_clean)

Run:  python manage.py test grades
"""
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from accounts.models import User, Role, Level
from academics.models import (
    Category, Subject, AcademicPeriod, Kelas, PeriodType, Quarter,
)
from enrollments.models import Enrollment, EnrollmentStatus
from sessions_app.models import Session
from grades.models import Grade, GradeType


def _enrollment_and_session():
    teacher = User.objects.create(username="t_grade", role=Role.TEACHER)
    category = Category.objects.create(name="Sains")
    subject = Subject.objects.create(category=category, name="Kimia")
    today = timezone.localdate()
    period = AcademicPeriod.objects.create(
        year="2026-2027", period_type=PeriodType.QUARTER, quarter=Quarter.Q1,
        name="K1", start_date=today, end_date=today + timedelta(days=120),
    )
    kelas = Kelas.objects.create(
        teacher_profile=teacher.teacher_profile, subject=subject, academic_period=period,
        name="Kimia SMA", level=Level.SMA, start_date=today, end_date=today + timedelta(days=90),
        capacity=10, total_sessions=12,
    )
    student = User.objects.create(username="s_grade", role=Role.STUDENT)
    student.student_profile.level = Level.SMA
    student.student_profile.save(update_fields=["level"])
    enrollment = Enrollment.objects.create(
        student_profile=student.student_profile, kelas=kelas,
        status=EnrollmentStatus.ACTIVE, price_at_enrollment=0,
    )
    session = Session.objects.create(kelas=kelas, session_number=1, date=today)
    return enrollment, session


class GradeValidationTests(TestCase):
    def setUp(self):
        self.enrollment, self.session = _enrollment_and_session()

    def test_quiz_without_session_invalid(self):
        g = Grade(enrollment=self.enrollment, grade_type=GradeType.QUIZ, score=Decimal("80"))
        with self.assertRaises(ValidationError):
            g.full_clean()

    def test_quiz_with_session_valid(self):
        g = Grade(
            enrollment=self.enrollment, session=self.session,
            grade_type=GradeType.QUIZ, score=Decimal("80"),
        )
        g.full_clean()  # should not raise

    def test_final_without_session_valid(self):
        g = Grade(enrollment=self.enrollment, grade_type=GradeType.FINAL, score=Decimal("90"))
        g.full_clean()  # should not raise

    def test_score_above_100_invalid(self):
        g = Grade(
            enrollment=self.enrollment, session=self.session,
            grade_type=GradeType.QUIZ, score=Decimal("150"),
        )
        with self.assertRaises(ValidationError):
            g.full_clean()
