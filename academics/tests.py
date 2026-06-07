"""Regression tests for academics teacher class create/edit pages.

These exist to catch enum renames or default-value drift that breaks the
GET-render path. The previous batch-model rollout left four references to
the removed `KelasType.REGULAR` value in academics/views.py that only
surfaced at runtime; a simple GET probe would have caught it instantly.

Run:  python manage.py test academics
"""
from datetime import time, timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.models import (
    ApprovalStatus, Education, Level, Role, TeacherJenjang, User,
)
from academics.models import (
    AcademicPeriod, Category, Kelas, KelasStatus, KelasType, PeriodType,
    Quarter, Schedule, Subject,
)


def _build_teacher():
    teacher = User.objects.create(
        username='t_views', role=Role.TEACHER,
        approval_status=ApprovalStatus.APPROVED, is_active=True,
    )
    teacher.set_password('pass12345')
    teacher.save()
    tp = teacher.teacher_profile
    tp.education = Education.S1
    tp.specialization = 'Matematika'
    tp.experience_years = 5
    tp.save()
    TeacherJenjang.objects.get_or_create(teacher_profile=tp, level=Level.SMA)
    return teacher


def _make_kelas_for(teacher):
    cat = Category.objects.create(name='Cat')
    subj = Subject.objects.create(category=cat, name='Subj')
    today = timezone.localdate()
    period = AcademicPeriod.objects.create(
        year='2026', period_type=PeriodType.QUARTER, quarter=Quarter.Q1,
        name='P', start_date=today, end_date=today + timedelta(days=120),
        is_active=True,
    )
    kelas = Kelas.objects.create(
        teacher_profile=teacher.teacher_profile, subject=subj,
        academic_period=period, name='K-views',
        level=Level.SMA, class_type=KelasType.GROUP,
        start_date=today, end_date=today,
        capacity=8, total_sessions=4, status=KelasStatus.OPEN,
    )
    kelas.set_jenjang([Level.SMA])
    Schedule.objects.create(
        kelas=kelas, day='MONDAY',
        start_time=time(15, 0), end_time=time(17, 0),
    )
    return kelas


class TeacherClassFormGetTests(TestCase):
    """GET smoke tests for the teacher class create + edit pages.

    Purpose: surface enum renames or template/context drift the moment the
    page is rendered. A reference to a removed KelasType value would have
    raised on the first hit; this test forces the render in CI so it never
    ships.
    """

    @classmethod
    def setUpTestData(cls):
        cls.teacher = _build_teacher()
        cls.kelas = _make_kelas_for(cls.teacher)

    def setUp(self):
        ok = self.client.login(username='t_views', password='pass12345')
        self.assertTrue(ok, 'teacher login failed')

    def test_get_create_renders_200(self):
        r = self.client.get('/teacher/classes/create/')
        self.assertEqual(r.status_code, 200, f'create page failed: {r.status_code}')
        body = r.content.decode('utf-8', errors='replace')
        # Sanity: the three class-type radio pills are present.
        for label in ('Privat', 'Grup', 'Paket Ganjil Genap'):
            self.assertIn(label, body, f'missing class-type pill: {label}')

    def test_get_edit_renders_200(self):
        r = self.client.get(f'/teacher/classes/{self.kelas.pk}/edit/')
        self.assertEqual(r.status_code, 200, f'edit page failed: {r.status_code}')
        body = r.content.decode('utf-8', errors='replace')
        for label in ('Privat', 'Grup', 'Paket Ganjil Genap'):
            self.assertIn(label, body, f'missing class-type pill: {label}')
