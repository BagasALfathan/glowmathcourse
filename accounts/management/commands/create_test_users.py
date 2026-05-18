"""Create 3 known test users (Rafael, Trista, GlowMath) for manual QA.

Idempotent: re-running won't create duplicates and won't change passwords for
existing users (use --reset-passwords to force).
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import (
    User, Role, ApprovalStatus, Level,
    StudentProfile, TeacherProfile, TeacherJenjang, AdminProfile,
)


PW = 'ikanbuvivid'


class Command(BaseCommand):
    help = 'Create 3 fixed test users: 1 student (UMUM), 1 teacher, 1 admin.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset-passwords',
            action='store_true',
            help="If user already exists, reset its password and approval/role flags.",
        )

    def handle(self, *args, **opts):
        reset = opts['reset_passwords']
        with transaction.atomic():
            self._upsert_student(reset)
            self._upsert_teacher(reset)
            self._upsert_admin(reset)

        self.stdout.write(self.style.SUCCESS('\n=== TEST CREDENTIALS ==='))
        self.stdout.write(f'Student (UMUM): rafaeladhikabagasalfathan / {PW}')
        self.stdout.write(f'Teacher:        candrarinitristaharidewati / {PW}')
        self.stdout.write(f'Admin:          glowmathcourse / {PW}')

    # ─── Student ────────────────────────────────────────────────────────────
    def _upsert_student(self, reset):
        username = 'rafaeladhikabagasalfathan'
        user, created = User.objects.get_or_create(
            username=username,
            defaults=dict(
                email='rafael@glowmathclass.com',
                first_name='Rafael Adhika',
                last_name='Bagas Alfathan',
                role=Role.STUDENT,
                approval_status=ApprovalStatus.APPROVED,
                is_active=True,
            ),
        )
        if created:
            user.set_password(PW)
            user.save()
            self.stdout.write(f'✓ Created student: {username}')
        else:
            if reset:
                user.set_password(PW)
                user.role = Role.STUDENT
                user.approval_status = ApprovalStatus.APPROVED
                user.is_active = True
                user.save()
                self.stdout.write(f'[UPD] Reset student:   {username}')
            else:
                self.stdout.write(f'[--]  Exists student:  {username} (use --reset-passwords to update)')

        # Profile: signal already created an empty StudentProfile when role=STUDENT
        profile, _ = StudentProfile.objects.get_or_create(user=user)
        profile.level = Level.UMUM
        profile.school_name = 'Universitas'
        # school_grade is PositiveSmallIntegerField — can't hold "Mahasiswa"; leave null
        profile.school_grade = None
        profile.save()

    # ─── Teacher ────────────────────────────────────────────────────────────
    def _upsert_teacher(self, reset):
        username = 'candrarinitristaharidewati'
        user, created = User.objects.get_or_create(
            username=username,
            defaults=dict(
                email='trista@glowmathclass.com',
                first_name='Candrarini Trista',
                last_name='Hari Dewati',
                role=Role.TEACHER,
                approval_status=ApprovalStatus.APPROVED,
                is_active=True,
            ),
        )
        if created:
            user.set_password(PW)
            user.save()
            self.stdout.write(f'✓ Created teacher: {username}')
        else:
            if reset:
                user.set_password(PW)
                user.role = Role.TEACHER
                user.approval_status = ApprovalStatus.APPROVED
                user.is_active = True
                user.save()
                self.stdout.write(f'[UPD] Reset teacher:   {username}')
            else:
                self.stdout.write(f'[--]  Exists teacher:  {username} (use --reset-passwords to update)')

        profile, _ = TeacherProfile.objects.get_or_create(user=user)
        profile.education = 'S1'
        profile.specialization = 'Matematika'
        profile.experience_years = 5
        profile.bio = 'Guru matematika berpengalaman.'
        profile.save()

        for level in (Level.SD, Level.SMP, Level.SMA):
            TeacherJenjang.objects.get_or_create(teacher_profile=profile, level=level)

    # ─── Admin ──────────────────────────────────────────────────────────────
    def _upsert_admin(self, reset):
        username = 'glowmathcourse'
        user, created = User.objects.get_or_create(
            username=username,
            defaults=dict(
                email='admin@glowmathclass.com',
                first_name='GlowMath',
                last_name='Course',
                role=Role.ADMIN,
                approval_status=ApprovalStatus.APPROVED,
                is_active=True,
                is_staff=True,
                is_superuser=True,
            ),
        )
        if created:
            user.set_password(PW)
            user.save()
            self.stdout.write(f'✓ Created admin:   {username}')
        else:
            if reset:
                user.set_password(PW)
                user.role = Role.ADMIN
                user.approval_status = ApprovalStatus.APPROVED
                user.is_active = True
                user.is_staff = True
                user.is_superuser = True
                user.save()
                self.stdout.write(f'[UPD] Reset admin:     {username}')
            else:
                self.stdout.write(f'[--]  Exists admin:    {username} (use --reset-passwords to update)')

        profile, _ = AdminProfile.objects.get_or_create(user=user)
        profile.department = 'Management'
        profile.save()
