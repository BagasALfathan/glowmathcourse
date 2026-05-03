"""
Management command: python manage.py smoke_test
Creates test users for each role, visits every URL as that role,
and reports HTTP status codes.
"""
from django.contrib.auth import get_user_model
from django.test import Client
from django.core.management.base import BaseCommand
from django.urls import reverse

from academics.models import Kelas, Subject, Category, AcademicPeriod, Level, KelasStatus
from enrollments.models import Enrollment, EnrollmentStatus
from grades.models import Grade, GradeType
from sessions_app.models import Session, SessionStatus
from ratings.models import Rating

User = get_user_model()

# ── URL list: (label, url_name, kwargs, roles_to_test, expected_min_status)
# expected_min_status = 200 for success, 302 for redirect-only
URLS = [
    # ── Public / Auth
    ('Login page',             'accounts:login',           {},                           ['anon'],    200),
    ('Register page',          'accounts:register',        {},                           ['anon'],    200),
    ('Register student',       'accounts:register_student',{},                           ['anon'],    200),
    ('Register teacher',       'accounts:register_teacher',{},                           ['anon'],    200),
    ('Waiting page',           'accounts:waiting',         {},                           ['anon'],    200),

    # ── Dashboard
    ('Dashboard router',       'dashboard:router',         {},                           ['student','teacher','admin'], 302),
    ('Student dashboard',      'dashboard:student',        {},                           ['student'], 200),
    ('Teacher dashboard',      'dashboard:teacher',        {},                           ['teacher'], 200),
    ('Admin dashboard',        'dashboard:admin',          {},                           ['admin'],   200),

    # ── Profile
    ('Profile view',           'accounts:profile',         {},                           ['student','teacher','admin'], 200),
    ('Profile edit',           'accounts:profile_edit',    {},                           ['student','teacher','admin'], 200),

    # ── Student: classes
    ('Class browse',           'academics:class_browse',   {},                           ['student'], 200),
    ('Class detail',           'academics:class_detail',   {'pk': '__kelas_pk__'},       ['student'], 200),

    # ── Student: enrollments
    ('My classes',             'enrollments:my_classes',   {},                           ['student'], 200),

    # ── Student: grades
    ('My grades',              'grades:my_grades',         {},                           ['student'], 200),
    ('My grades detail',       'grades:my_grades_detail',  {'kelas_id': '__kelas_pk__'}, ['student'], 200),

    # ── Student: attendance
    ('My attendance',          'sessions:my_attendance',   {},                           ['student'], 200),
    ('My attendance detail',   'sessions:my_attendance_detail', {'kelas_id': '__kelas_pk__'}, ['student'], 200),

    # ── Teacher: classes
    ('Teacher classes',        'academics:teacher_classes',{},                           ['teacher'], 200),
    ('Teacher class create',   'academics:teacher_class_create', {},                    ['teacher'], 200),
    ('Teacher class edit',     'academics:teacher_class_edit', {'pk': '__kelas_pk__'},  ['teacher'], 200),
    ('Teacher class students', 'academics:teacher_class_students', {'pk': '__kelas_pk__'}, ['teacher'], 200),

    # ── Teacher: sessions
    ('Teacher sessions',       'sessions_app:teacher_sessions', {'pk': '__kelas_pk__'}, ['teacher'], 200),
    ('Teacher session create', 'sessions_app:teacher_session_create', {'kelas_id': '__kelas_pk__'}, ['teacher'], 200),
    ('Teacher attendance',     'sessions_app:teacher_attendance', {'pk': '__session_pk__'}, ['teacher'], 200),

    # ── Teacher: grades
    ('Teacher grades',         'grades:teacher_grades',    {'pk': '__kelas_pk__'},       ['teacher'], 200),
    ('Teacher grade create',   'grades:teacher_grade_create', {},                        ['teacher'], 200, '?kelas_id=__kelas_pk__'),
    ('Teacher grade edit',     'grades:teacher_grade_edit', {'pk': '__grade_pk__'},      ['teacher'], 200),

    # ── Teacher: grades overview
    ('Teacher grades overview','grades:teacher_grades_overview', {},                     ['teacher'], 200),
    # ── Teacher: attendance overview
    ('Teacher attendance overview', 'sessions_app:teacher_attendance_overview', {},      ['teacher'], 200),
    # ── Teacher: ratings
    ('Teacher ratings',        'ratings:teacher_ratings',  {},                           ['teacher'], 200),

    # ── Admin panel
    ('Admin pending users',    'admin_panel:pending_users',{},                           ['admin'],   200),
    ('Admin users list',       'admin_panel:users_list',   {},                           ['admin'],   200),
    ('Admin user detail',      'admin_panel:user_detail',  {'user_id': '__student_pk__'},['admin'],   200),
    ('Admin user edit',        'admin_panel:user_edit',    {'user_id': '__student_pk__'},['admin'],   200),
    ('Admin classes list',     'admin_panel:classes_list', {},                           ['admin'],   200),
    ('Admin enrollments list', 'admin_panel:enrollments_list', {},                       ['admin'],   200),
    ('Admin categories list',  'admin_panel:categories_list', {},                        ['admin'],   200),
    ('Admin subjects list',    'admin_panel:subjects_list',{},                           ['admin'],   200),
    ('Admin periods list',     'admin_panel:periods_list', {},                           ['admin'],   200),
    ('Admin grades list',      'admin_panel:grades_list',  {},                           ['admin'],   200),
    ('Admin ratings list',     'admin_panel:ratings_list', {},                           ['admin'],   200),
    ('Admin logs list',        'admin_panel:logs_list',    {},                           ['admin'],   200),
]


def resolve_kwargs(kwargs, pks):
    """Replace placeholder strings with real PKs."""
    return {k: pks.get(v, v) if isinstance(v, str) else v for k, v in kwargs.items()}


class Command(BaseCommand):
    help = 'Smoke-test every page for every role and report HTTP status codes.'

    def handle(self, *args, **options):
        self.stdout.write('\n=== GlowMathCourse URL Smoke Test ===\n')

        # ── Create / fetch test users
        pw = 'TestPass123!'

        # Admin
        admin_user, _ = User.objects.get_or_create(
            username='_test_admin',
            defaults={'role': 'ADMIN', 'is_staff': True, 'is_active': True, 'email': 'admin@test.com'}
        )
        admin_user.set_password(pw); admin_user.is_active = True; admin_user.save()
        try:
            admin_user.admin_profile
        except Exception:
            from accounts.models import AdminProfile
            AdminProfile.objects.get_or_create(user=admin_user)

        # Teacher
        teacher_user, _ = User.objects.get_or_create(
            username='_test_teacher',
            defaults={'role': 'TEACHER', 'is_active': True, 'email': 'teacher@test.com',
                      'first_name': 'Test', 'last_name': 'Teacher'}
        )
        teacher_user.set_password(pw); teacher_user.is_active = True; teacher_user.save()
        try:
            teacher_user.teacher_profile
        except Exception:
            from accounts.models import TeacherProfile
            TeacherProfile.objects.get_or_create(user=teacher_user)

        # Student
        student_user, _ = User.objects.get_or_create(
            username='_test_student',
            defaults={'role': 'STUDENT', 'is_active': True, 'email': 'student@test.com',
                      'first_name': 'Test', 'last_name': 'Student'}
        )
        student_user.set_password(pw); student_user.is_active = True; student_user.save()
        try:
            sp = student_user.student_profile
            sp.level = Level.SMP; sp.save()
        except Exception:
            from accounts.models import StudentProfile
            StudentProfile.objects.get_or_create(user=student_user, defaults={'level': Level.SMP})

        # ── Create / fetch test data
        from datetime import date
        period, _ = AcademicPeriod.objects.get_or_create(
            name='Test Period',
            defaults={
                'year': '2026', 'quarter': 'Q1', 'is_active': True,
                'start_date': date(2026, 1, 1), 'end_date': date(2026, 12, 31),
            }
        )
        category, _ = Category.objects.get_or_create(name='Test Category')
        subject, _ = Subject.objects.get_or_create(
            name='Test Subject',
            defaults={'category': category}
        )
        kelas, _ = Kelas.objects.get_or_create(
            name='Test Kelas',
            defaults={
                'subject': subject,
                'teacher': teacher_user,
                'level': Level.SMP,
                'capacity': 10,
                'total_sessions': 10,
                'status': KelasStatus.OPEN,
                'academic_period': period,
                'is_deleted': False,
                'start_date': date(2026, 1, 1),
                'end_date': date(2026, 12, 31),
            }
        )
        enrollment, _ = Enrollment.objects.get_or_create(
            student=student_user,
            kelas=kelas,
            defaults={'status': EnrollmentStatus.ACTIVE, 'is_deleted': False}
        )
        session, _ = Session.objects.get_or_create(
            kelas=kelas,
            session_number=1,
            defaults={
                'status': SessionStatus.COMPLETED,
                'topic': 'Test Session',
                'date': date(2026, 3, 1),
            }
        )
        grade, _ = Grade.objects.get_or_create(
            enrollment=enrollment,
            grade_type=GradeType.QUIZ,
            defaults={'score': 85.0}
        )

        pks = {
            '__kelas_pk__': kelas.pk,
            '__session_pk__': session.pk,
            '__grade_pk__': grade.pk,
            '__student_pk__': student_user.pk,
            '__teacher_pk__': teacher_user.pk,
        }

        clients = {
            'anon': Client(SERVER_NAME='localhost'),
            'student': Client(SERVER_NAME='localhost'),
            'teacher': Client(SERVER_NAME='localhost'),
            'admin': Client(SERVER_NAME='localhost'),
        }
        clients['student'].login(username='_test_student', password=pw)
        clients['teacher'].login(username='_test_teacher', password=pw)
        clients['admin'].login(username='_test_admin', password=pw)

        results = {'ok': [], 'warn': [], 'fail': []}

        for entry_tuple in URLS:
            label, url_name, raw_kwargs, roles, expected = entry_tuple[:5]
            qs_template = entry_tuple[5] if len(entry_tuple) > 5 else ''
            kwargs = resolve_kwargs(raw_kwargs, pks)
            try:
                url = reverse(url_name, kwargs=kwargs)
            except Exception as e:
                results['fail'].append(f'REVERSE FAIL  {label} ({url_name}): {e}')
                continue

            # Resolve query string placeholders
            if qs_template:
                for placeholder, val in pks.items():
                    qs_template = qs_template.replace(placeholder, str(val))
                url = url + qs_template

            for role in roles:
                client = clients[role]
                try:
                    resp = client.get(url, follow=False)
                    status = resp.status_code
                    ok = status in (200, 302)
                    tag = 'OK  ' if ok else 'FAIL'
                    entry = f'{tag}  [{role:7s}] {status}  {url}  ({label})'
                    if ok:
                        results['ok'].append(entry)
                    else:
                        results['fail'].append(entry)
                except Exception as e:
                    results['fail'].append(f'ERROR [{role:7s}] {url}  ({label}): {e}')

        # Report
        total = len(results['ok']) + len(results['warn']) + len(results['fail'])
        self.stdout.write(f'\nResults: {len(results["ok"])}/{total} OK, {len(results["fail"])} FAILED\n')

        if results['fail']:
            self.stdout.write('\n--- FAILURES ---')
            for f in results['fail']:
                self.stdout.write(f'  {f}')
        else:
            self.stdout.write('All pages returned 200 or 302. No failures.\n')

        self.stdout.write('\n--- FULL RESULTS ---')
        for entry in results['ok']:
            self.stdout.write(f'  {entry}')
