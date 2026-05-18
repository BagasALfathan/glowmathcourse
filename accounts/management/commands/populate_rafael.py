"""Populate Rafael's account with realistic UMUM-level data:
 6 classes available, 6 enrollments (mix statuses), sessions+attendance+grades+journals,
 ratings on COMPLETED, and a handful of notifications.

Idempotent: re-running won't double-up (get_or_create / exists() guards).
"""
import random
from datetime import date, time, timedelta
from decimal import Decimal

from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Avg
from django.utils import timezone

from accounts.models import (
    User, TeacherProfile, TeacherJenjang, StudentProfile, Level, Role, ApprovalStatus,
)
from academics.models import (
    Kelas, Schedule, Subject, Category, AcademicPeriod, KelasStatus,
    PeriodType, Quarter, Day,
)
from enrollments.models import Enrollment, EnrollmentStatus
from sessions_app.models import Session, Attendance, SessionStatus, SessionType, AttendanceStatus
from grades.models import Grade, GradeType
from journals.models import MonthlyJournal
from ratings.models import TeacherRating, ClassRating
from notifications.models import Notification, NotificationType


UMUM_SUBJECTS = [
    ('UTBK Matematika',      'Persiapan UTBK Matematika Saintek'),
    ('TOEFL Preparation',    'Persiapan tes TOEFL iBT'),
    ('IELTS Academic',       'Persiapan IELTS Academic'),
    ('Statistika Lanjut',    'Statistika untuk mahasiswa & profesional'),
    ('Kalkulus Universitas', 'Kalkulus 1 & 2 untuk mahasiswa S1'),
    ('Bahasa Inggris Bisnis','Business English untuk profesional'),
]

START_HOURS = [8, 10, 14, 16, 19]
DURATION_HOURS = 2

DAYS = [d for d, _ in Day.choices]
WEEKDAY_TO_DAY = ['MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY', 'SUNDAY']


class Command(BaseCommand):
    help = "Populate Rafael's account with realistic UMUM-level data."

    @transaction.atomic
    def handle(self, *args, **opts):
        random.seed(42)

        rafael = User.objects.filter(username='rafaeladhikabagasalfathan').first()
        if not rafael:
            self.stderr.write('User "rafaeladhikabagasalfathan" missing. Run create_test_users first.')
            return
        rafael_profile = rafael.student_profile

        period = self._ensure_period()
        umum_cat = self._ensure_umum_category()
        subjects = self._ensure_umum_subjects(umum_cat)
        teachers = self._ensure_umum_teachers()
        kelases = self._ensure_umum_classes(period, subjects, teachers)

        enrollments = self._enroll_rafael(rafael_profile, kelases)
        sessions_summary = self._create_sessions_and_attendance(enrollments)
        grades_summary = self._create_grades(enrollments)
        journals_summary = self._create_monthly_journals(enrollments)
        ratings_summary = self._create_ratings(enrollments)
        notifications_count = self._create_notifications(rafael)

        # Bust the cached top_teachers so the dashboard re-runs the query
        cache.delete('top_teachers_dashboard')

        self._print_summary(
            rafael, enrollments, sessions_summary, grades_summary,
            journals_summary, ratings_summary, notifications_count,
        )

    # ─── Setup helpers ──────────────────────────────────────────────────────

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

    def _ensure_umum_category(self):
        cat, _ = Category.objects.get_or_create(
            name='Umum',
            defaults={'description': 'Materi untuk umum/dewasa', 'is_active': True},
        )
        return cat

    def _ensure_umum_subjects(self, category):
        out = []
        for name, desc in UMUM_SUBJECTS:
            subj, _ = Subject.objects.get_or_create(
                name=name,
                defaults={'category': category, 'description': desc, 'is_active': True},
            )
            out.append(subj)
        return out

    def _ensure_umum_teachers(self):
        """Ensure 6 approved teachers have UMUM in their TeacherJenjang."""
        trista = TeacherProfile.objects.filter(user__username='candrarinitristaharidewati').first()
        chosen = [trista] if trista else []
        more = (
            TeacherProfile.objects
            .filter(user__role=Role.TEACHER, user__approval_status=ApprovalStatus.APPROVED)
            .exclude(pk=trista.pk if trista else 0)
            .select_related('user')[:5]
        )
        chosen.extend(list(more))
        for tp in chosen:
            if tp:
                TeacherJenjang.objects.get_or_create(teacher_profile=tp, level=Level.UMUM)
        return [t for t in chosen if t]

    def _ensure_umum_classes(self, period, subjects, teachers):
        """Create one OPEN UMUM kelas per (subject, teacher). Idempotent by name+period.

        IMPORTANT: total_sessions=24 (not 16) so that `update_expired_classes()`
        step 3 (auto-close when created_count==total_sessions==completed_count)
        does NOT fire. We only generate ~12 sessions per kelas, leaving the
        course intentionally "in progress".
        """
        today = date.today()
        start = today - timedelta(days=30)
        end = today + timedelta(days=60)
        kelases = []
        for i, (subj, teacher) in enumerate(zip(subjects, (teachers * 2)[:len(subjects)])):
            name = f'{subj.name} - Reguler'
            existing = Kelas.objects.filter(
                name=name, level=Level.UMUM, academic_period=period, is_deleted=False,
            ).first()
            if existing:
                # Force-correct fields that the auto-close middleware may have touched
                changed = []
                if existing.total_sessions != 24:
                    existing.total_sessions = 24; changed.append('total_sessions')
                if existing.status != KelasStatus.OPEN:
                    existing.status = KelasStatus.OPEN; changed.append('status')
                if existing.end_date < today + timedelta(days=14):
                    existing.end_date = end; changed.append('end_date')
                if changed:
                    existing.save(update_fields=changed + ['updated_at'])
                kelases.append(existing)
                continue
            kelas = Kelas.objects.create(
                name=name,
                subject=subj,
                teacher_profile=teacher,
                academic_period=period,
                level=Level.UMUM,
                capacity=20,
                total_sessions=24,
                start_date=start,
                end_date=end,
                status=KelasStatus.OPEN,
                price=Decimal('500000'),
                description=f'Kelas {subj.name} untuk mahasiswa dan umum.',
            )
            # Two non-overlapping session times per week
            chosen_days = random.sample(DAYS, 2)
            for day in chosen_days:
                sh = random.choice(START_HOURS)
                Schedule.objects.create(
                    kelas=kelas,
                    day=day,
                    start_time=time(sh, 0),
                    end_time=time(min(sh + DURATION_HOURS, 21), 0),
                )
            kelases.append(kelas)
            self.stdout.write(f'  + class created: {kelas.name}')
        return kelases

    # ─── Enroll Rafael ──────────────────────────────────────────────────────

    def _enroll_rafael(self, profile, kelases):
        statuses = [
            EnrollmentStatus.ACTIVE, EnrollmentStatus.ACTIVE,
            EnrollmentStatus.ACTIVE, EnrollmentStatus.ACTIVE,
            EnrollmentStatus.COMPLETED, EnrollmentStatus.DROPPED,
        ]
        out = []
        for kelas, status in zip(kelases, statuses):
            enr, created = Enrollment.objects.get_or_create(
                student_profile=profile,
                kelas=kelas,
                defaults={'status': status, 'price_at_enrollment': kelas.price},
            )
            # If created previously with a different status, force update once
            if not created and enr.status != status:
                enr.status = status
                enr.save(update_fields=['status', 'updated_at'])
            out.append(enr)
        return out

    # ─── Sessions + attendance ──────────────────────────────────────────────

    def _create_sessions_and_attendance(self, enrollments):
        today = date.today()
        horizon = today + timedelta(days=14)
        sess_total, att_total = 0, 0
        att_breakdown = {AttendanceStatus.PRESENT: 0, AttendanceStatus.PERMITTED: 0, AttendanceStatus.ABSENT: 0}

        for enr in enrollments:
            kelas = enr.kelas
            schedules = list(kelas.schedules.all())
            if not schedules:
                continue
            schedule_by_day = {s.day: s for s in schedules}

            cursor = kelas.start_date
            num = 1
            while num <= kelas.total_sessions and cursor <= min(kelas.end_date, horizon):
                day_key = WEEKDAY_TO_DAY[cursor.weekday()]
                sched = schedule_by_day.get(day_key)
                if sched:
                    session, created = Session.objects.get_or_create(
                        kelas=kelas, session_number=num,
                        defaults={
                            'date': cursor,
                            'start_time': sched.start_time,
                            'end_time': sched.end_time,
                            'topic': f'Pertemuan {num} — {kelas.subject.name}',
                            'capacity': 20,
                            'status': (
                                SessionStatus.COMPLETED if cursor < today else SessionStatus.SCHEDULED
                            ),
                            'session_type': SessionType.REGULAR,
                        },
                    )
                    if created:
                        sess_total += 1
                    # Attendance for past + COMPLETED only, against Rafael's enrollment if ACTIVE/COMPLETED
                    if (
                        session.status == SessionStatus.COMPLETED
                        and enr.status != EnrollmentStatus.DROPPED
                    ):
                        att_status = random.choices(
                            [AttendanceStatus.PRESENT, AttendanceStatus.PERMITTED, AttendanceStatus.ABSENT],
                            weights=[75, 15, 10],
                        )[0]
                        _, att_created = Attendance.objects.get_or_create(
                            enrollment=enr, session=session,
                            defaults={
                                'status': att_status,
                                'marked_by': kelas.teacher_profile.user,
                            },
                        )
                        if att_created:
                            att_total += 1
                            att_breakdown[att_status] += 1
                    num += 1
                cursor += timedelta(days=1)
        return {
            'sessions': sess_total,
            'attendance': att_total,
            'breakdown': att_breakdown,
        }

    # ─── Grades ─────────────────────────────────────────────────────────────

    def _create_grades(self, enrollments):
        total = 0
        for enr in enrollments:
            if enr.status == EnrollmentStatus.DROPPED:
                continue
            existing_count = Grade.objects.filter(enrollment=enr).count()
            target = random.randint(4, 6)
            to_create = max(0, target - existing_count)
            completed_sessions = list(
                Session.objects.filter(kelas=enr.kelas, status=SessionStatus.COMPLETED)
            )
            for i in range(to_create):
                gtype = random.choice([
                    GradeType.QUIZ, GradeType.ASSIGNMENT,
                    GradeType.MIDTERM, GradeType.FINAL,
                ])
                # Score: weighted toward 70-95
                score = round(random.choices(
                    [random.randint(60, 75), random.randint(76, 90), random.randint(91, 100)],
                    weights=[20, 60, 20],
                )[0])
                # QUIZ/ASSIGNMENT need a session per Grade.clean()
                session = None
                if gtype in (GradeType.QUIZ, GradeType.ASSIGNMENT):
                    if not completed_sessions:
                        # Can't create QUIZ/ASSIGNMENT without a session — fall back to MIDTERM
                        gtype = GradeType.MIDTERM
                    else:
                        session = random.choice(completed_sessions)
                Grade.objects.create(
                    enrollment=enr,
                    session=session,
                    grade_type=gtype,
                    score=Decimal(score),
                    notes=f'{gtype.label} #{existing_count + i + 1}',
                    graded_by_teacher=enr.kelas.teacher_profile,
                )
                total += 1
        return total

    # ─── Monthly journals ───────────────────────────────────────────────────

    def _create_monthly_journals(self, enrollments):
        total = 0
        # last month's first day
        first_of_month = date.today().replace(day=1)
        last_month_end = first_of_month - timedelta(days=1)
        m, y = last_month_end.month, last_month_end.year
        for enr in enrollments:
            if enr.status == EnrollmentStatus.DROPPED:
                continue
            _, created = MonthlyJournal.objects.get_or_create(
                enrollment=enr, month=m, year=y,
                defaults={
                    'written_by_teacher': enr.kelas.teacher_profile,
                    'summary': (
                        f'Rafael menunjukkan progress yang baik dalam {enr.kelas.subject.name}. '
                        f'Pemahaman konsep dasar sudah baik, perlu lebih banyak latihan '
                        f'untuk topik yang lebih kompleks.'
                    ),
                    'topics_covered': f'Bab 1-3 dari {enr.kelas.subject.name}, latihan soal, diskusi grup.',
                    'strengths': 'Aktif dalam diskusi, mau bertanya, kemampuan analisis baik.',
                    'areas_for_improvement': 'Manajemen waktu saat mengerjakan soal, perlu lebih banyak latihan soal aplikasi.',
                    'published_at': timezone.now(),
                },
            )
            if created:
                total += 1
        return total

    # ─── Ratings (only on COMPLETED) ────────────────────────────────────────

    def _create_ratings(self, enrollments):
        teacher_count, class_count = 0, 0
        for enr in enrollments:
            if enr.status != EnrollmentStatus.COMPLETED:
                continue
            _, tcreated = TeacherRating.objects.get_or_create(
                enrollment=enr,
                defaults={
                    'teacher_profile': enr.kelas.teacher_profile,
                    'score': random.choices([4, 5], weights=[30, 70])[0],
                    'comment': 'Penjelasan jelas dan mudah dipahami. Recommended!',
                },
            )
            _, ccreated = ClassRating.objects.get_or_create(
                enrollment=enr,
                defaults={
                    'kelas': enr.kelas,
                    'score': random.choices([4, 5], weights=[30, 70])[0],
                    'comment': 'Materi tersusun rapi, cocok untuk persiapan ujian.',
                },
            )
            if tcreated:
                teacher_count += 1
            if ccreated:
                class_count += 1
        return {'teacher': teacher_count, 'class': class_count}

    # ─── Notifications ──────────────────────────────────────────────────────

    def _create_notifications(self, user):
        # Spec uses "JOURNAL" type which isn't in NotificationType — map to OTHER
        rows = [
            (NotificationType.GRADE,        'Nilai baru tersedia',         'Quiz Matematika kamu sudah dinilai: 88.', False),
            (NotificationType.SESSION,      'Sesi hari ini',               'Pertemuan #8 Matematika dimulai jam 14:00.', False),
            (NotificationType.OTHER,        'Laporan bulanan tersedia',    'Lihat progress kamu bulan lalu.', True),
            (NotificationType.ANNOUNCEMENT, 'Try Out UTBK Gratis',         'Pendaftaran terbuka untuk siswa SMA.', False),
            (NotificationType.ENROLLMENT,   'Pendaftaran disetujui',       'Selamat datang di TOEFL Preparation.', True),
        ]
        total = 0
        for ntype, title, msg, is_read in rows:
            _, created = Notification.objects.get_or_create(
                user=user, title=title,
                defaults={
                    'type': ntype,
                    'message': msg,
                    'is_read': is_read,
                    'read_at': timezone.now() if is_read else None,
                },
            )
            if created:
                total += 1
        return total

    # ─── Summary ────────────────────────────────────────────────────────────

    def _print_summary(self, rafael, enrollments, sess, grades, journals, ratings, notif):
        active = sum(1 for e in enrollments if e.status == EnrollmentStatus.ACTIVE)
        completed = sum(1 for e in enrollments if e.status == EnrollmentStatus.COMPLETED)
        dropped = sum(1 for e in enrollments if e.status == EnrollmentStatus.DROPPED)

        today = date.today()
        rafael_profile = rafael.student_profile
        active_enr_ids = [e.id for e in enrollments if e.status == EnrollmentStatus.ACTIVE]
        today_sessions = (
            Session.objects
            .filter(kelas__enrollments__id__in=active_enr_ids, date=today, status=SessionStatus.SCHEDULED)
            .distinct()
            .count()
        )

        avg_grade = (
            Grade.objects
            .filter(enrollment__student_profile=rafael_profile)
            .aggregate(avg=Avg('score'))['avg']
        )
        avg_grade_str = f'{float(avg_grade):.1f}' if avg_grade is not None else '—'

        bd = sess['breakdown']

        self.stdout.write(self.style.SUCCESS('\n=== RAFAEL DATA SUMMARY ==='))
        self.stdout.write(f'Enrollments      : {len(enrollments)} (ACTIVE: {active}, COMPLETED: {completed}, DROPPED: {dropped})')
        self.stdout.write(f'Sessions created : +{sess["sessions"]} (this run)')
        self.stdout.write(f'Total sessions   : {Session.objects.filter(kelas__enrollments__student_profile=rafael_profile).distinct().count()}')
        self.stdout.write(f"Today's sessions : {today_sessions}")
        self.stdout.write(f'Attendance       : +{sess["attendance"]} (Hadir {bd[AttendanceStatus.PRESENT]} / Izin {bd[AttendanceStatus.PERMITTED]} / Alpha {bd[AttendanceStatus.ABSENT]})')
        self.stdout.write(f'Grades           : +{grades} (avg score: {avg_grade_str})')
        self.stdout.write(f'Monthly journals : +{journals}')
        self.stdout.write(f'Ratings          : +{ratings["teacher"]} teacher + {ratings["class"]} class')
        self.stdout.write(f'Notifications    : +{notif}')
        self.stdout.write(self.style.SUCCESS('\nLogin at http://localhost:8765/'))
        self.stdout.write('  Username: rafaeladhikabagasalfathan')
        self.stdout.write('  Password: ikanbuvivid')
