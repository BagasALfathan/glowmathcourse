"""Populate Trista's account with realistic teaching data:
 5 classes (SD/SMP/SMA/SMA/UMUM), 8-12 students each, sessions + attendance
 (deliberately leaving ~30% unmarked to populate the 'belum diabsen' to-do),
 grades, partial monthly journals, and teacher ratings.

Idempotent.
"""
import random
from datetime import date, time, timedelta
from decimal import Decimal

from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import (
    User, TeacherProfile, TeacherJenjang, StudentProfile, Level, Role, ApprovalStatus,
)
from academics.models import (
    Kelas, Schedule, Subject, Category, AcademicPeriod, KelasStatus,
    PeriodType, Quarter,
)
from enrollments.models import Enrollment, EnrollmentStatus
from sessions_app.models import Session, Attendance, SessionStatus, SessionType, AttendanceStatus
from grades.models import Grade, GradeType
from journals.models import MonthlyJournal
from ratings.models import TeacherRating


CLASS_SPECS = [
    # (kelas name,                       subject,           level,    price,    total_sessions)
    ('Matematika SD - Dasar',            'Matematika SD',   'SD',     200_000,  24),
    ('Aljabar SMP - Pemantapan',         'Aljabar SMP',     'SMP',    300_000,  24),
    ('Matematika SMA - Reguler',         'Matematika SMA',  'SMA',    400_000,  24),
    ('Matematika UTBK Intensif',         'UTBK Matematika', 'SMA',    500_000,  28),
    ('Kalkulus Universitas',             'Kalkulus 1',      'UMUM',   500_000,  20),
]

START_HOURS = [9, 13, 15, 17]
RATING_COMMENTS_PRAISE = [
    'Penjelasan jelas, sabar mengajar. Terima kasih Bu!',
    'Metode mengajarnya bagus, mudah dipahami.',
    'Bu Trista sangat membantu saya memahami matematika.',
    'Recommended! Pengajar berpengalaman.',
    'Materi dijelaskan step by step.',
]


class Command(BaseCommand):
    help = "Populate Trista's teaching data (5 classes, students, sessions, grades, ratings)."

    @transaction.atomic
    def handle(self, *args, **opts):
        random.seed(7)

        trista_user = User.objects.filter(username='candrarinitristaharidewati').first()
        if not trista_user:
            self.stderr.write('User "candrarinitristaharidewati" missing. Run create_test_users first.')
            return
        trista = trista_user.teacher_profile

        # Ensure full jenjang coverage including UMUM
        for level in (Level.SD, Level.SMP, Level.SMA, Level.UMUM):
            TeacherJenjang.objects.get_or_create(teacher_profile=trista, level=level)

        period = self._ensure_period()
        cat = self._ensure_mate_category()
        classes = self._ensure_classes(trista, period, cat)
        self._enroll_students(classes)
        sess_summary = self._create_sessions(classes)
        att_summary = self._create_attendance(classes)
        grades_count = self._create_grades(classes, trista)
        journals_summary = self._create_journals(classes, trista)
        ratings_count = self._create_ratings(classes, trista)

        # Bust caches the dashboard relies on
        cache.delete(f'teacher_attention_{trista.pk}')
        cache.delete('top_teachers_dashboard')

        self._print_summary(
            trista, sess_summary, att_summary, grades_count,
            journals_summary, ratings_count,
        )

    # ── Setup ───────────────────────────────────────────────────────────────

    def _ensure_period(self):
        period = AcademicPeriod.objects.filter(is_active=True).first()
        if period:
            return period
        today = date.today()
        return AcademicPeriod.objects.create(
            name=f'{today.year} Q2',
            year=str(today.year),
            period_type=PeriodType.QUARTER,
            quarter=Quarter.Q2,
            start_date=date(today.year, 4, 1),
            end_date=date(today.year, 6, 30),
            is_active=True,
        )

    def _ensure_mate_category(self):
        cat, _ = Category.objects.get_or_create(
            name='Matematika',
            defaults={'description': 'Mata pelajaran matematika & turunannya', 'is_active': True},
        )
        return cat

    def _ensure_classes(self, teacher, period, category):
        today = date.today()
        start = today - timedelta(days=30)
        end = today + timedelta(days=60)
        result = []
        for kelas_name, subj_name, level, price, total in CLASS_SPECS:
            subj = Subject.objects.filter(name=subj_name, category=category).first()
            if not subj:
                subj = Subject.objects.create(
                    name=subj_name, category=category,
                    description=f'Kelas {subj_name}', is_active=True,
                )
            kelas = Kelas.objects.filter(
                name=kelas_name, teacher_profile=teacher, is_deleted=False,
            ).first()
            if kelas:
                # Force-correct fields that the middleware may have touched
                changed = []
                if kelas.total_sessions != total:
                    kelas.total_sessions = total; changed.append('total_sessions')
                if kelas.status != KelasStatus.OPEN:
                    kelas.status = KelasStatus.OPEN; changed.append('status')
                if kelas.end_date < today + timedelta(days=14):
                    kelas.end_date = end; changed.append('end_date')
                if changed:
                    kelas.save(update_fields=changed + ['updated_at'])
                result.append(kelas)
                continue
            kelas = Kelas.objects.create(
                name=kelas_name,
                subject=subj,
                teacher_profile=teacher,
                academic_period=period,
                level=level,
                capacity=15,
                total_sessions=total,
                start_date=start,
                end_date=end,
                status=KelasStatus.OPEN,
                price=Decimal(price),
                description=f'Kelas {subj_name} untuk {level}',
            )
            picked_days = random.sample(
                ['MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY'], 2,
            )
            for d in picked_days:
                h = random.choice(START_HOURS)
                Schedule.objects.create(
                    kelas=kelas, day=d,
                    start_time=time(h, 0),
                    end_time=time(h + 1, 30),
                )
            self.stdout.write(f'  + class created: {kelas.name} ({level})')
            result.append(kelas)
        return result

    # ── Enroll students ────────────────────────────────────────────────────

    def _enroll_students(self, classes):
        rafael = StudentProfile.objects.filter(user__username='rafaeladhikabagasalfathan').first()
        for kelas in classes:
            level_students = list(
                StudentProfile.objects
                .filter(
                    user__role=Role.STUDENT,
                    user__approval_status=ApprovalStatus.APPROVED,
                    user__is_deleted=False,
                    level=kelas.level,
                )
                .select_related('user')
            )
            if kelas.level == Level.UMUM and rafael and rafael not in level_students:
                level_students.append(rafael)
            if not level_students:
                self.stdout.write(f'  ! no students available for level={kelas.level}')
                continue
            n = min(random.randint(8, 12), len(level_students))
            picked = random.sample(level_students, n)
            for sp in picked:
                Enrollment.objects.get_or_create(
                    student_profile=sp, kelas=kelas,
                    defaults={
                        'status': random.choices(
                            [EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED],
                            weights=[90, 10],
                        )[0],
                        'price_at_enrollment': kelas.price,
                    },
                )

    # ── Sessions ───────────────────────────────────────────────────────────

    def _create_sessions(self, classes):
        today = date.today()
        horizon = today + timedelta(days=14)
        WEEKDAY = ['MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY', 'SUNDAY']
        total_created = 0
        for kelas in classes:
            schedules = list(kelas.schedules.all())
            if not schedules:
                continue
            by_day = {s.day: s for s in schedules}
            cursor = kelas.start_date
            num = Session.objects.filter(kelas=kelas).count() + 1
            while num <= kelas.total_sessions and cursor <= min(kelas.end_date, horizon):
                day_key = WEEKDAY[cursor.weekday()]
                sched = by_day.get(day_key)
                if sched:
                    _, created = Session.objects.get_or_create(
                        kelas=kelas, session_number=num,
                        defaults={
                            'date': cursor,
                            'start_time': sched.start_time,
                            'end_time': sched.end_time,
                            'topic': f'Pertemuan {num} — {kelas.subject.name}',
                            'capacity': 15,
                            'status': (
                                SessionStatus.COMPLETED if cursor < today
                                else SessionStatus.SCHEDULED
                            ),
                            'session_type': SessionType.REGULAR,
                        },
                    )
                    if created:
                        total_created += 1
                    num += 1
                cursor += timedelta(days=1)
        return {'created': total_created}

    # ── Attendance: mark ~70% of completed sessions (leave 30% unmarked) ───

    def _create_attendance(self, classes):
        marked, breakdown = 0, {AttendanceStatus.PRESENT: 0, AttendanceStatus.PERMITTED: 0, AttendanceStatus.ABSENT: 0}
        for kelas in classes:
            completed = list(
                Session.objects.filter(kelas=kelas, status=SessionStatus.COMPLETED)
                .order_by('date')
            )
            n_to_mark = int(len(completed) * 0.7)
            for sess in completed[:n_to_mark]:
                for enr in Enrollment.objects.filter(kelas=kelas, status=EnrollmentStatus.ACTIVE):
                    if Attendance.objects.filter(enrollment=enr, session=sess).exists():
                        continue
                    status = random.choices(
                        [AttendanceStatus.PRESENT, AttendanceStatus.PERMITTED, AttendanceStatus.ABSENT],
                        weights=[75, 15, 10],
                    )[0]
                    Attendance.objects.create(
                        enrollment=enr, session=sess, status=status,
                        marked_by=kelas.teacher_profile.user,
                    )
                    marked += 1
                    breakdown[status] += 1
        return {'marked': marked, 'breakdown': breakdown}

    # ── Grades ─────────────────────────────────────────────────────────────

    def _create_grades(self, classes, teacher):
        total = 0
        for kelas in classes:
            completed_sessions = list(
                Session.objects.filter(kelas=kelas, status=SessionStatus.COMPLETED)
            )
            for enr in Enrollment.objects.filter(kelas=kelas, status=EnrollmentStatus.ACTIVE):
                existing = Grade.objects.filter(enrollment=enr).count()
                target = random.randint(3, 5)
                for _ in range(max(0, target - existing)):
                    score = round(random.choices(
                        [random.randint(55, 75), random.randint(76, 90), random.randint(91, 100)],
                        weights=[20, 60, 20],
                    )[0])
                    gtype = random.choice([GradeType.QUIZ, GradeType.ASSIGNMENT, GradeType.MIDTERM])
                    session = None
                    if gtype in (GradeType.QUIZ, GradeType.ASSIGNMENT):
                        if not completed_sessions:
                            gtype = GradeType.MIDTERM
                        else:
                            session = random.choice(completed_sessions)
                    Grade.objects.create(
                        enrollment=enr, session=session, grade_type=gtype,
                        score=Decimal(score),
                        notes=f'{gtype.label}',
                        graded_by_teacher=teacher,
                    )
                    total += 1
        return total

    # ── Journals (only first 3 classes, 60% of students) ──────────────────

    def _create_journals(self, classes, teacher):
        last_month = date.today().replace(day=1) - timedelta(days=1)
        created, skipped = 0, 0
        for kelas in classes[:3]:
            active = list(Enrollment.objects.filter(kelas=kelas, status=EnrollmentStatus.ACTIVE))
            cutoff = int(len(active) * 0.6)
            for enr in active[:cutoff]:
                _, was_created = MonthlyJournal.objects.get_or_create(
                    enrollment=enr, month=last_month.month, year=last_month.year,
                    defaults={
                        'written_by_teacher': teacher,
                        'summary': (
                            f"{enr.student_profile.user.first_name or enr.student_profile.user.username} "
                            f"menunjukkan progress baik di {kelas.subject.name}. "
                            f"Perlu lebih banyak latihan soal aplikasi."
                        ),
                        'topics_covered': f'Bab 1-3 dari kurikulum {kelas.subject.name}',
                        'strengths': 'Aktif bertanya, kemampuan analisis baik',
                        'areas_for_improvement': 'Manajemen waktu saat ujian, latihan soal kompleks',
                        'published_at': timezone.now(),
                    },
                )
                if was_created:
                    created += 1
            skipped += len(active) - cutoff
        return {'created': created, 'pending': skipped}

    # ── Ratings ─────────────────────────────────────────────────────────────

    def _create_ratings(self, classes, teacher):
        total = 0
        # COMPLETED enrollments first
        completed_enrs = (
            Enrollment.objects
            .filter(kelas__teacher_profile=teacher, status=EnrollmentStatus.COMPLETED)
        )
        for enr in completed_enrs:
            _, created = TeacherRating.objects.get_or_create(
                enrollment=enr,
                defaults={
                    'teacher_profile': teacher,
                    'score': random.choices([4, 5], weights=[30, 70])[0],
                    'comment': random.choice(RATING_COMMENTS_PRAISE),
                },
            )
            if created:
                total += 1
        # Plus a handful from random ACTIVE enrollments for review-count diversity
        active_enrs = (
            Enrollment.objects
            .filter(kelas__teacher_profile=teacher, status=EnrollmentStatus.ACTIVE)
            .order_by('?')[:15]
        )
        for enr in active_enrs:
            _, created = TeacherRating.objects.get_or_create(
                enrollment=enr,
                defaults={
                    'teacher_profile': teacher,
                    'score': random.choices([3, 4, 5], weights=[10, 30, 60])[0],
                    'comment': 'Pengajar yang baik.',
                },
            )
            if created:
                total += 1
        return total

    # ── Summary ─────────────────────────────────────────────────────────────

    def _print_summary(self, teacher, sess, att, grades, journals, ratings):
        from django.db.models import Count
        today = date.today()
        wk_start = today - timedelta(days=today.weekday())
        wk_end = wk_start + timedelta(days=6)

        total_classes = Kelas.objects.filter(teacher_profile=teacher, is_deleted=False).count()
        total_students = (
            Enrollment.objects
            .filter(kelas__teacher_profile=teacher, status=EnrollmentStatus.ACTIVE)
            .values('student_profile').distinct().count()
        )
        sessions_this_week = Session.objects.filter(
            kelas__teacher_profile=teacher, date__gte=wk_start, date__lte=wk_end,
        ).count()
        total_ratings = TeacherRating.objects.filter(teacher_profile=teacher).count()
        bd = att['breakdown']

        self.stdout.write(self.style.SUCCESS('\n=== TRISTA DATA SUMMARY ==='))
        self.stdout.write(f'Total classes        : {total_classes}')
        self.stdout.write(f'Active students      : {total_students}')
        self.stdout.write(f'Sessions this week   : {sessions_this_week}')
        self.stdout.write(f"Today's sessions     : {Session.objects.filter(kelas__teacher_profile=teacher, date=today).count()}")
        self.stdout.write(f'Sessions created     : +{sess["created"]} (this run)')
        self.stdout.write(f'Attendance marked    : +{att["marked"]} (Hadir {bd[AttendanceStatus.PRESENT]} / Izin {bd[AttendanceStatus.PERMITTED]} / Alpha {bd[AttendanceStatus.ABSENT]})')
        self.stdout.write(f'Grades               : +{grades}')
        self.stdout.write(f'Journals             : +{journals["created"]}  ({journals["pending"]} still pending — fills the "belum ditulis" to-do)')
        self.stdout.write(f'Total ratings        : {total_ratings}')
        self.stdout.write(self.style.SUCCESS('\nLogin at /guru/login/'))
        self.stdout.write('  Username: candrarinitristaharidewati')
        self.stdout.write('  Password: ikanbuvivid')
