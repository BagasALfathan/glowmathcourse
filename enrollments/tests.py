"""Smoke tests — enrollment business rules.

Exercises the real enroll view (enrollments.views.enroll) plus the DB-level
uniqueness guard:
  * level mismatch          -> rejected, no enrollment row
  * capacity full           -> rejected, no enrollment row
  * happy path              -> ACTIVE enrollment created
  * duplicate student+kelas -> IntegrityError (unique constraint)

Run:  python manage.py test enrollments
"""
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from accounts.models import User, Role, Level
from academics.models import (
    Category, Subject, AcademicPeriod, Kelas, KelasStatus, PeriodType, Quarter,
)
from enrollments.models import Enrollment, EnrollmentStatus


def make_kelas(level=Level.SMA, capacity=2, status=KelasStatus.OPEN):
    teacher = User.objects.create(username="t_enr", role=Role.TEACHER)
    category = Category.objects.create(name="Sains")
    subject = Subject.objects.create(category=category, name="Matematika")
    today = timezone.localdate()
    period = AcademicPeriod.objects.create(
        year="2026-2027",
        period_type=PeriodType.QUARTER,
        quarter=Quarter.Q1,
        name="Kuartal 1 2026",
        start_date=today,
        end_date=today + timedelta(days=120),
        is_active=True,
    )
    return Kelas.objects.create(
        teacher_profile=teacher.teacher_profile,
        subject=subject,
        academic_period=period,
        name="Matematika SMA Pagi",
        level=level,
        start_date=today + timedelta(days=7),   # future -> enrollment open
        end_date=today + timedelta(days=90),
        capacity=capacity,
        total_sessions=12,
        status=status,
    )


def make_student(username, level=Level.SMA):
    u = User.objects.create(
        username=username, role=Role.STUDENT, approval_status="APPROVED", is_active=True
    )
    u.student_profile.level = level
    u.student_profile.save(update_fields=["level"])
    return u


class EnrollViewRuleTests(TestCase):
    def setUp(self):
        self.kelas = make_kelas(level=Level.SMA, capacity=1)

    def _active_count(self):
        return Enrollment.objects.filter(
            kelas=self.kelas, status=EnrollmentStatus.ACTIVE, is_deleted=False
        ).count()

    def test_level_mismatch_rejected(self):
        sd_student = make_student("sd_kid", level=Level.SD)
        self.client.force_login(sd_student)
        self.client.post(f"/enroll/{self.kelas.pk}/")
        self.assertEqual(self._active_count(), 0)

    def test_happy_path_creates_active_enrollment(self):
        student = make_student("sma_kid", level=Level.SMA)
        self.client.force_login(student)
        resp = self.client.post(f"/enroll/{self.kelas.pk}/")
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(self._active_count(), 1)

    def test_capacity_full_rejected(self):
        # Fill the single seat directly, then a second student tries via the view.
        first = make_student("first_kid", level=Level.SMA)
        Enrollment.objects.create(
            student_profile=first.student_profile,
            kelas=self.kelas,
            status=EnrollmentStatus.ACTIVE,
            price_at_enrollment=0,
        )
        second = make_student("second_kid", level=Level.SMA)
        self.client.force_login(second)
        self.client.post(f"/enroll/{self.kelas.pk}/")
        self.assertEqual(self._active_count(), 1)  # still just the first student

    def test_non_student_forbidden(self):
        teacher = User.objects.create(username="t_block", role=Role.TEACHER)
        self.client.force_login(teacher)
        resp = self.client.post(f"/enroll/{self.kelas.pk}/")
        self.assertEqual(resp.status_code, 403)


class EnrollmentConstraintTests(TestCase):
    def test_duplicate_student_kelas_blocked(self):
        kelas = make_kelas()
        student = make_student("dup_kid", level=kelas.level)
        Enrollment.objects.create(
            student_profile=student.student_profile, kelas=kelas, price_at_enrollment=0
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Enrollment.objects.create(
                    student_profile=student.student_profile,
                    kelas=kelas,
                    price_at_enrollment=0,
                )
