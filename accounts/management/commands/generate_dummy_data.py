"""
Generate full-stack dummy data for the GlowMathCourse system.

Populates every table in the database including the new ones introduced
in the ERD v4 upgrade: notifications, course_materials, journals,
ratings (TeacherRating + ClassRating), and billing (Invoice/Payment/Refund).

Usage:
    python manage.py generate_dummy_data            # additive
    python manage.py generate_dummy_data --clear    # wipe dummy data first
"""
import datetime
import random
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import (
    AdminProfile, ApprovalStatus, Education, Gender, Level, Role,
    StudentProfile, TeacherProfile, User,
)
from academics.models import (
    AcademicPeriod, Category, Day, Kelas, KelasStatus, PeriodType,
    Quarter, Schedule, Subject,
)
from enrollments.models import Enrollment, EnrollmentStatus
from sessions_app.models import (
    Attendance, AttendanceStatus, BookingStatus, Session, SessionBooking,
    SessionStatus, SessionType,
)
from grades.models import Grade, GradeType
from ratings.models import ClassRating, TeacherRating
from announcements.models import Announcement
from activity_logs.models import ActivityLog
from notifications.models import Notification, NotificationType
from course_materials.models import CourseMaterial, FileType
from journals.models import MonthlyJournal, NoteType, NoteVisibility, SessionNote
from billing.models import (
    Invoice, InvoiceStatus, Payment, PaymentGateway, PaymentMethod,
    PaymentStatus, Refund, RefundStatus,
)


# ── Lookups ────────────────────────────────────────────────────────────────────

STUDENT_FIRST_NAMES = [
    'Andi', 'Budi', 'Citra', 'Dian', 'Eko', 'Fajar', 'Gita', 'Hana',
    'Indra', 'Joko', 'Kiki', 'Lina', 'Mita', 'Nanda', 'Oki', 'Putri',
    'Rafi', 'Sari', 'Tono', 'Umi', 'Vina', 'Wawan', 'Xena', 'Yogi', 'Zara',
    'Agus', 'Bayu', 'Cici', 'Dito', 'Elsa', 'Fani', 'Gilang', 'Hesti',
    'Ivan', 'Julia', 'Kevin', 'Lisa', 'Mario', 'Nina', 'Oscar',
    'Prita', 'Qori', 'Rizal', 'Sinta', 'Teguh', 'Ulfa', 'Vito', 'Wulan',
    'Yanti', 'Zaki',
]
STUDENT_LAST_NAMES = [
    'Pratama', 'Santoso', 'Wijaya', 'Kusuma', 'Hidayat', 'Rahayu',
    'Setiawan', 'Nugroho', 'Purnama', 'Hartono', 'Susanto', 'Wibowo',
    'Kurniawan', 'Hakim', 'Saputra', 'Lestari', 'Dewi', 'Utama',
    'Permana', 'Firmansyah',
]
TEACHER_FIRST_NAMES = [
    'Ahmad', 'Benny', 'Cahya', 'Dewi', 'Eko', 'Farida', 'Guntur',
    'Hendra', 'Irma', 'Jaya', 'Kartika', 'Lukman', 'Maya', 'Nuri',
    'Oka', 'Putro', 'Rini', 'Suharto', 'Tina', 'Umar',
]
TEACHER_LAST_NAMES = [
    'Budiman', 'Cahyono', 'Darmawan', 'Effendi', 'Fauzi', 'Gunawan',
    'Hasanah', 'Ibrahim', 'Jauhari', 'Kusno', 'Latif', 'Mahmud',
    'Nasution', 'Oesman', 'Prabowo', 'Qodir', 'Rachman', 'Salim',
    'Tanjung', 'Usman',
]
SCHOOLS = [
    'SDN 01 Merdeka', 'SDN 02 Nusantara', 'SDN 03 Bangsa',
    'SMPN 01 Harapan', 'SMPN 02 Cerdas', 'SMPN 03 Mandiri',
    'SMAN 01 Unggul', 'SMAN 02 Prestasi', 'SMAN 03 Gemilang',
]
SPECIALIZATIONS = [
    'Matematika', 'Fisika', 'Kimia', 'Biologi',
    'Bahasa Indonesia', 'Bahasa Inggris', 'Ekonomi', 'Sejarah',
]
ADMIN_DEPARTMENTS = ['Operasional', 'Keuangan', 'Akademik', 'Pemasaran']

CATEGORIES = {
    'IPA':    'Ilmu Pengetahuan Alam',
    'IPS':    'Ilmu Pengetahuan Sosial',
    'Bahasa': 'Bahasa dan Sastra',
    'Umum':   'Mata Pelajaran Umum',
}
SUBJECTS = {
    'IPA':    ['Matematika', 'Fisika', 'Kimia', 'Biologi'],
    'IPS':    ['Ekonomi', 'Sejarah', 'Geografi'],
    'Bahasa': ['Bahasa Indonesia', 'Bahasa Inggris'],
    'Umum':   ['PKN', 'Seni Budaya'],
}

CLASS_TOPICS = [
    'Aljabar Dasar', 'Persamaan Linear', 'Bilangan Bulat',
    'Statistika', 'Probabilitas', 'Trigonometri',
    'Kinematika', 'Hukum Newton', 'Energi & Usaha',
    'Sel & Jaringan', 'Genetika', 'Ekosistem',
    'Reaksi Redoks', 'Asam Basa', 'Hidrokarbon',
    'Cerpen Indonesia', 'Puisi Modern', 'Grammar Tenses',
]

NOTIFICATION_TEMPLATES = {
    NotificationType.GRADE:        ('Nilai baru', 'Nilai ujian {kelas} telah dipublikasi.'),
    NotificationType.SESSION:      ('Sesi mendatang', 'Pertemuan {kelas} akan dimulai besok.'),
    NotificationType.PAYMENT:      ('Pengingat pembayaran', 'Faktur {invoice} jatuh tempo dalam 3 hari.'),
    NotificationType.ANNOUNCEMENT: ('Pengumuman baru', 'Ada pengumuman baru dari admin.'),
    NotificationType.ENROLLMENT:   ('Pendaftaran disetujui', 'Pendaftaran ke {kelas} berhasil.'),
    NotificationType.RATING:       ('Penilaian baru', 'Penilaian baru diterima untuk {kelas}.'),
    NotificationType.OTHER:        ('Pemberitahuan', 'Ada pembaruan untuk akun Anda.'),
}

MATERIAL_TITLES = [
    'Modul Pengantar', 'Latihan Soal Bab 1', 'Ringkasan Materi UTS',
    'Rangkuman Rumus', 'Soal Kuis Mingguan', 'Materi Tambahan',
    'Pembahasan Soal UAS', 'Lembar Kerja', 'Video Pembelajaran',
    'Catatan Diskusi', 'Materi Praktikum',
]


# ── Helper utilities ───────────────────────────────────────────────────────────

def _safe_get_or_create(model, **lookup_and_defaults):
    """Like get_or_create but separates lookup vs defaults sanely."""
    defaults = lookup_and_defaults.pop('defaults', {})
    return model.objects.get_or_create(defaults=defaults, **lookup_and_defaults)


# ── Command ────────────────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = 'Generate full-stack dummy data covering all tables in the system.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear', action='store_true',
            help='Delete dummy data (users with dummy usernames + their dependencies) first.',
        )

    def handle(self, *args, **options):
        random.seed(42)
        self.stats = {}

        if options['clear']:
            self._clear()

        with transaction.atomic():
            self._seed_categories_subjects()
            self._seed_academic_period()
            self._seed_admin()
            self._seed_students(count=50)
            self._seed_teachers(count=15)
            self._seed_pending_users(count=5)
            self._seed_classes(per_teacher=2)
            self._seed_enrollments_and_sessions()
            self._seed_grades()
            self._seed_attendance_and_bookings()
            self._seed_ratings()
            self._seed_announcements()
            self._seed_notifications()
            self._seed_course_materials()
            self._seed_journals_and_notes()
            self._seed_invoices_and_payments()

        self._summary()

    # ── Cleanup ───────────────────────────────────────────────────────────────

    def _clear(self):
        self.stdout.write('Clearing dummy data...')
        deleted_users = User.objects.filter(
            username__regex=r'^(student|teacher|pending|admin)\d{3}$'
        ).delete()
        self.stdout.write(f'  Removed users (+ cascaded children): {deleted_users[0]}')

    # ── Seeders ───────────────────────────────────────────────────────────────

    def _seed_categories_subjects(self):
        self.stdout.write('Seeding categories & subjects...')
        cat_objs = {}
        for name, desc in CATEGORIES.items():
            cat, _ = Category.objects.get_or_create(
                name=name, defaults={'description': desc}
            )
            cat_objs[name] = cat
        for cat_name, subject_names in SUBJECTS.items():
            for sname in subject_names:
                Subject.objects.get_or_create(name=sname, category=cat_objs[cat_name])
        self.stats['categories'] = Category.objects.count()
        self.stats['subjects']   = Subject.objects.count()

    def _seed_academic_period(self):
        self.stdout.write('Seeding academic periods...')
        today = timezone.localdate()
        # Quarter-style period (active)
        AcademicPeriod.objects.get_or_create(
            year='2026-2027', quarter=Quarter.Q1,
            defaults={
                'period_type': PeriodType.QUARTER,
                'name': 'Q1 2026-2027',
                'start_date': today.replace(month=1, day=1),
                'end_date':   today.replace(month=3, day=31),
                'is_active': True,
            },
        )
        # Semester-style period (inactive demo)
        AcademicPeriod.objects.get_or_create(
            year='2025-2026', semester='GANJIL',
            defaults={
                'period_type': PeriodType.SEMESTER,
                'name': 'Semester Ganjil 2025-2026',
                'start_date': datetime.date(2025, 8, 1),
                'end_date':   datetime.date(2026, 1, 15),
                'is_active': False,
            },
        )
        self.stats['academic_periods'] = AcademicPeriod.objects.count()

    def _seed_admin(self):
        self.stdout.write('Seeding admin account...')
        admin, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'first_name': 'Admin',
                'last_name': 'Bimbel',
                'email': 'admin@glow.bimbel',
                'role': Role.ADMIN,
                'approval_status': ApprovalStatus.APPROVED,
                'is_staff': True,
                'is_superuser': True,
                'phone': '081200000000',
            },
        )
        if created:
            admin.set_password('admin1234')
            admin.save()
        # Ensure AdminProfile fields are set
        admin.admin_profile.department = random.choice(ADMIN_DEPARTMENTS)
        admin.admin_profile.permissions = {'all': True}
        admin.admin_profile.save()
        self.stats['admins'] = User.objects.filter(role=Role.ADMIN).count()

    def _seed_students(self, count=50):
        self.stdout.write(f'Seeding {count} students...')
        created_n = 0
        for i in range(1, count + 1):
            username = f'student{i:03d}'
            if User.objects.filter(username=username).exists():
                continue
            first = random.choice(STUDENT_FIRST_NAMES)
            last  = random.choice(STUDENT_LAST_NAMES)
            level = random.choice([Level.SD, Level.SMP, Level.SMA])
            if level == Level.SD:
                grade, school = random.randint(1, 6),  random.choice([s for s in SCHOOLS if s.startswith('SDN')])
            elif level == Level.SMP:
                grade, school = random.randint(7, 9),  random.choice([s for s in SCHOOLS if s.startswith('SMPN')])
            else:
                grade, school = random.randint(10, 12), random.choice([s for s in SCHOOLS if s.startswith('SMAN')])

            user = User.objects.create_user(
                username=username, password='murid123',
                first_name=first, last_name=last,
                email=f'{username}@dummy.glow',
                role=Role.STUDENT,
                approval_status=ApprovalStatus.APPROVED,
                phone=f'0812{random.randint(10000000, 99999999)}',
            )
            profile = user.student_profile
            profile.level         = level
            profile.school_name   = school
            profile.school_grade  = grade
            profile.parent_name   = f'Orang Tua {last}'
            profile.parent_phone  = f'0813{random.randint(10000000, 99999999)}'
            profile.address       = f'Jl. Dummy No. {i}, Jakarta'
            # date_of_birth: roughly age-appropriate
            today = timezone.localdate()
            est_age = {'SD': 9, 'SMP': 13, 'SMA': 16}[level] + random.randint(-1, 2)
            profile.date_of_birth = today.replace(year=today.year - est_age)
            profile.gender        = random.choice([Gender.MALE, Gender.FEMALE])
            profile.save()
            created_n += 1
        self.stats['students'] = User.objects.filter(role=Role.STUDENT).count()

    def _seed_teachers(self, count=15):
        self.stdout.write(f'Seeding {count} teachers...')
        for i in range(1, count + 1):
            username = f'teacher{i:03d}'
            if User.objects.filter(username=username).exists():
                continue
            first = random.choice(TEACHER_FIRST_NAMES)
            last  = random.choice(TEACHER_LAST_NAMES)
            user = User.objects.create_user(
                username=username, password='teacher123',
                first_name=first, last_name=last,
                email=f'{username}@dummy.glow',
                role=Role.TEACHER,
                approval_status=ApprovalStatus.APPROVED,
                phone=f'0811{random.randint(10000000, 99999999)}',
            )
            profile = user.teacher_profile
            profile.specialization    = random.choice(SPECIALIZATIONS)
            profile.education         = random.choice([Education.S1, Education.S2])
            profile.experience_years  = random.randint(1, 15)
            profile.bio               = f'Pengajar {profile.specialization} berpengalaman.'
            profile.address           = f'Jl. Guru No. {i}, Jakarta'
            profile.hourly_rate       = Decimal(random.randrange(50_000, 200_001, 5_000))
            profile.bank_account      = f'BCA - {random.randint(1000000000, 9999999999)}'
            profile.save()
            # Pick 1-3 random jenjang for this teacher
            pool = [Level.TK, Level.SD, Level.SMP, Level.SMA, Level.UMUM]
            chosen = random.sample(pool, k=random.randint(1, 3))
            profile.set_jenjang(chosen)
        self.stats['teachers'] = User.objects.filter(role=Role.TEACHER).count()

    def _seed_pending_users(self, count=5):
        """Some PENDING and some REJECTED accounts for approval-flow demos."""
        for i in range(1, count + 1):
            username = f'pending{i:03d}'
            if User.objects.filter(username=username).exists():
                continue
            role   = random.choice([Role.STUDENT, Role.TEACHER])
            status = ApprovalStatus.PENDING if i <= 3 else ApprovalStatus.REJECTED
            User.objects.create_user(
                username=username, password='temp123',
                first_name='Calon', last_name=f'User{i}',
                email=f'{username}@dummy.glow',
                role=role, approval_status=status,
                phone=f'0810{random.randint(10000000, 99999999)}',
            )

    def _seed_classes(self, per_teacher=2):
        self.stdout.write(f'Seeding classes ({per_teacher} per teacher)...')
        active_period = AcademicPeriod.objects.filter(is_active=True).first()
        teachers = list(TeacherProfile.objects.all())
        subjects = list(Subject.objects.all())
        if not (teachers and subjects and active_period):
            return

        today = timezone.localdate()
        # Levels that map to Kelas (TK + UMUM kelas not built yet — fall back to SMA)
        _kelas_compatible = {Level.SD, Level.SMP, Level.SMA}
        for tp in teachers:
            taught_levels = tp.get_jenjang_list()
            jenjang = [lvl for lvl in taught_levels if lvl in _kelas_compatible] or [Level.SMA]

            for k_idx in range(per_teacher):
                level = random.choice(jenjang)
                subject = random.choice(subjects)
                # First class per teacher is "historical" (ended ~2 months ago),
                # second is "current/upcoming" (ongoing or starting soon)
                if k_idx == 0:
                    start_date = today - datetime.timedelta(days=random.randint(120, 180))
                    end_date   = start_date + datetime.timedelta(days=56)
                else:
                    start_offset = random.randint(-30, 20)
                    start_date = today + datetime.timedelta(days=start_offset)
                    end_date   = start_date + datetime.timedelta(days=56)
                # Closed if end_date already past
                if end_date < today:
                    status = KelasStatus.CLOSED
                else:
                    status = random.choice([KelasStatus.OPEN, KelasStatus.OPEN, KelasStatus.FULL])
                kelas = Kelas.objects.create(
                    teacher_profile=tp, subject=subject, academic_period=active_period,
                    name=f'{subject.name} {level} - Kelas {k_idx + 1}',
                    description=f'Kelas {subject.name} untuk siswa {level}.',
                    level=level,
                    start_date=start_date, end_date=end_date,
                    capacity=random.choice([8, 10, 12, 15]),
                    total_sessions=random.choice([6, 8, 10]),
                    price=Decimal(random.randrange(300_000, 1_500_001, 50_000)),
                    status=status,
                )
                # 1–2 weekly schedule slots
                used_days = random.sample(
                    [Day.MONDAY, Day.TUESDAY, Day.WEDNESDAY, Day.THURSDAY, Day.FRIDAY, Day.SATURDAY],
                    k=random.choice([1, 2]),
                )
                start_hour = random.randint(8, 17)
                for day in used_days:
                    start_t = datetime.time(start_hour, 0)
                    end_t   = datetime.time(start_hour + 1, 30)
                    Schedule.objects.create(
                        kelas=kelas, day=day,
                        start_time=start_t, end_time=end_t,
                        room=f'Room {random.choice("ABCD")}{random.randint(1, 4)}',
                    )
        self.stats['classes']   = Kelas.objects.count()
        self.stats['schedules'] = Schedule.objects.count()

    def _seed_enrollments_and_sessions(self):
        self.stdout.write('Seeding enrollments + sessions...')
        klasses = list(Kelas.objects.all())
        students = list(StudentProfile.objects.all())
        today = timezone.localdate()
        for kelas in klasses:
            # Students of matching level
            candidates = [s for s in students if s.level == kelas.level]
            if not candidates:
                continue
            n_enroll = min(len(candidates), random.randint(max(2, kelas.capacity // 2), kelas.capacity))
            picks = random.sample(candidates, n_enroll)
            for sp in picks:
                # Status: COMPLETED if class is closed, else mostly ACTIVE, few DROPPED
                if kelas.status == KelasStatus.CLOSED:
                    status = EnrollmentStatus.COMPLETED
                else:
                    status = random.choices(
                        [EnrollmentStatus.ACTIVE, EnrollmentStatus.DROPPED],
                        weights=[9, 1],
                    )[0]
                Enrollment.objects.create(
                    student_profile=sp, kelas=kelas,
                    status=status,
                    price_at_enrollment=kelas.price,
                    is_deleted=(status == EnrollmentStatus.DROPPED and random.random() < 0.5),
                )

            # Sessions — spread across class span
            total = kelas.total_sessions
            span_days = (kelas.end_date - kelas.start_date).days
            step = max(1, span_days // max(total, 1))
            schedules = list(kelas.schedules.all())
            for sess_n in range(1, total + 1):
                sdate = kelas.start_date + datetime.timedelta(days=step * (sess_n - 1))
                if sdate > today:
                    sstatus = SessionStatus.SCHEDULED
                else:
                    sstatus = random.choices(
                        [SessionStatus.COMPLETED, SessionStatus.CANCELLED],
                        weights=[9, 1],
                    )[0]
                sched = schedules[0] if schedules else None
                stype = random.choices(
                    [SessionType.REGULAR, SessionType.MAKEUP, SessionType.OPTIONAL],
                    weights=[8, 1, 1],
                )[0]
                Session.objects.create(
                    kelas=kelas,
                    session_number=sess_n,
                    date=sdate,
                    start_time=sched.start_time if sched else None,
                    end_time=sched.end_time if sched else None,
                    topic=random.choice(CLASS_TOPICS),
                    capacity=0 if stype == SessionType.REGULAR else random.choice([5, 8]),
                    session_type=stype,
                    meeting_url=f'https://meet.example.com/{kelas.pk}-{sess_n}' if random.random() < 0.3 else '',
                    status=sstatus,
                )
        self.stats['enrollments'] = Enrollment.objects.count()
        self.stats['sessions']    = Session.objects.count()

    def _seed_grades(self):
        self.stdout.write('Seeding grades...')
        enrollments = list(Enrollment.objects.filter(is_deleted=False))
        for e in enrollments:
            sessions = list(e.kelas.sessions.filter(status=SessionStatus.COMPLETED))
            # Each enrollment gets 2–5 grade entries
            for _ in range(random.randint(2, 5)):
                gtype = random.choice([
                    GradeType.QUIZ, GradeType.MIDTERM, GradeType.FINAL, GradeType.ASSIGNMENT,
                ])
                session = None
                if gtype in (GradeType.QUIZ, GradeType.ASSIGNMENT) and sessions:
                    session = random.choice(sessions)
                Grade.objects.create(
                    enrollment=e,
                    session=session,
                    grade_type=gtype,
                    score=Decimal(random.randint(50, 100)),
                    notes=random.choice(['Bagus', 'Perlu ditingkatkan', 'Sangat baik', '']),
                    graded_by_teacher=e.kelas.teacher_profile,
                )
        self.stats['grades'] = Grade.objects.count()

    def _seed_attendance_and_bookings(self):
        self.stdout.write('Seeding attendance + bookings...')
        att_count = 0
        bk_count = 0
        for e in Enrollment.objects.filter(is_deleted=False):
            sessions = list(e.kelas.sessions.all())
            for s in sessions:
                if s.session_type == SessionType.REGULAR:
                    if s.status == SessionStatus.COMPLETED:
                        Attendance.objects.get_or_create(
                            enrollment=e, session=s,
                            defaults={
                                'status': random.choices(
                                    [AttendanceStatus.PRESENT, AttendanceStatus.PERMITTED, AttendanceStatus.ABSENT],
                                    weights=[7, 2, 1],
                                )[0],
                                'marked_by': e.kelas.teacher_profile.user,
                            },
                        )
                        att_count += 1
                else:
                    # MAKEUP / OPTIONAL — random subset books
                    if random.random() < 0.4:
                        SessionBooking.objects.get_or_create(
                            enrollment=e, session=s,
                            defaults={'status': BookingStatus.BOOKED},
                        )
                        bk_count += 1
        self.stats['attendance']      = Attendance.objects.count()
        self.stats['session_bookings'] = SessionBooking.objects.count()

    def _seed_ratings(self):
        self.stdout.write('Seeding ratings (Teacher + Class)...')
        completed = list(Enrollment.objects.filter(
            status=EnrollmentStatus.COMPLETED, is_deleted=False,
        ))
        n_teacher = n_class = 0
        for e in completed:
            if random.random() < 0.8:
                TeacherRating.objects.get_or_create(
                    enrollment=e,
                    defaults={
                        'teacher_profile': e.kelas.teacher_profile,
                        'score': random.randint(3, 5),
                        'comment': random.choice([
                            'Guru sangat membantu', 'Penjelasan jelas',
                            'Cara mengajarnya bagus', '',
                        ]),
                        'is_anonymous': random.random() < 0.2,
                    },
                )
                n_teacher += 1
            if random.random() < 0.7:
                ClassRating.objects.get_or_create(
                    enrollment=e,
                    defaults={
                        'kelas': e.kelas,
                        'score': random.randint(3, 5),
                        'comment': random.choice(['Kelas seru', 'Materi padat', '', 'Recommended']),
                        'is_anonymous': random.random() < 0.2,
                    },
                )
                n_class += 1
        self.stats['teacher_ratings'] = TeacherRating.objects.count()
        self.stats['class_ratings']   = ClassRating.objects.count()

    def _seed_announcements(self):
        self.stdout.write('Seeding announcements...')
        admin = User.objects.filter(role=Role.ADMIN).first()
        if not admin:
            return
        templates = [
            ('Selamat Datang!', 'Selamat datang di GlowMathCourse. Periksa jadwal kelas Anda.', 'ALL'),
            ('Libur Nasional', 'Akan ada hari libur nasional minggu depan.', 'ALL'),
            ('Khusus Guru', 'Mohon update materi minggu ini.', 'TEACHER'),
            ('Pembayaran Q1', 'Mohon segera melakukan pembayaran kelas Q1.', 'STUDENT'),
            ('Event SMA', 'Workshop khusus siswa SMA.', 'STUDENT'),
        ]
        for title, content, target in templates:
            Announcement.objects.get_or_create(
                title=title,
                defaults={
                    'author': admin, 'content': content,
                    'target_role': target, 'is_pinned': random.random() < 0.3,
                    'is_active': True,
                },
            )
        self.stats['announcements'] = Announcement.objects.count()

    def _seed_notifications(self):
        self.stdout.write('Seeding notifications...')
        users = list(User.objects.exclude(role=Role.ADMIN))
        if not users:
            return
        n = 0
        for user in users:
            for _ in range(random.randint(1, 3)):
                ntype = random.choice(list(NotificationType.values))
                title, msg = NOTIFICATION_TEMPLATES.get(
                    ntype, NOTIFICATION_TEMPLATES[NotificationType.OTHER],
                )
                Notification.objects.create(
                    user=user, type=ntype,
                    title=title,
                    message=msg.format(kelas='Matematika', invoice='INV-2026-00001'),
                    is_read=random.random() < 0.4,
                    read_at=(timezone.now() if random.random() < 0.3 else None),
                )
                n += 1
        self.stats['notifications'] = Notification.objects.count()

    def _seed_course_materials(self):
        self.stdout.write('Seeding course materials...')
        klasses = list(Kelas.objects.all())
        for kelas in klasses:
            uploader = kelas.teacher_profile.user
            for _ in range(random.randint(1, 3)):
                title = random.choice(MATERIAL_TITLES)
                # Use a placeholder file path (we don't actually upload)
                CourseMaterial.objects.create(
                    kelas=kelas,
                    session=random.choice(list(kelas.sessions.all()) or [None]),
                    uploaded_by=uploader,
                    title=f'{title} — {kelas.subject.name}',
                    description=f'Dokumen pembelajaran {title}.',
                    file=f'course_materials/2026/05/{title.lower().replace(" ", "_")}.pdf',
                    file_type=FileType.PDF,
                    file_size=random.randint(50_000, 5_000_000),
                    is_visible=True,
                )
        self.stats['course_materials'] = CourseMaterial.objects.count()

    def _seed_journals_and_notes(self):
        self.stdout.write('Seeding monthly journals + session notes...')
        completed_enrollments = list(Enrollment.objects.filter(
            status__in=[EnrollmentStatus.COMPLETED, EnrollmentStatus.ACTIVE], is_deleted=False,
        ))
        today = timezone.localdate()
        for e in completed_enrollments[:20]:
            for back in range(3):
                ym_month = today.month - back
                ym_year = today.year
                if ym_month <= 0:
                    ym_month += 12
                    ym_year -= 1
                MonthlyJournal.objects.get_or_create(
                    enrollment=e, month=ym_month, year=ym_year,
                    defaults={
                        'written_by_teacher': e.kelas.teacher_profile,
                        'summary': 'Siswa menunjukkan progress yang konsisten bulan ini.',
                        'topics_covered': 'Aljabar, fungsi linear, persamaan kuadrat.',
                        'strengths': 'Cepat memahami konsep baru.',
                        'areas_for_improvement': 'Perlu lebih teliti dalam perhitungan.',
                        'viewed_by_parent': random.random() < 0.5,
                        'published_at': timezone.now(),
                    },
                )

        sessions_pool = list(Session.objects.filter(status=SessionStatus.COMPLETED)[:200])
        for _ in range(40):
            if not sessions_pool:
                break
            s = random.choice(sessions_pool)
            enrollment = Enrollment.objects.filter(kelas=s.kelas, is_deleted=False).first()
            if not enrollment:
                continue
            SessionNote.objects.create(
                session=s, enrollment=enrollment,
                written_by_teacher=s.kelas.teacher_profile,
                note_type=random.choice(list(NoteType.values)),
                content=random.choice([
                    'Siswa aktif bertanya.',
                    'Perlu perhatian khusus untuk topik ini.',
                    'Memahami materi dengan baik.',
                    'Kurang fokus selama sesi.',
                ]),
                visibility=random.choice(list(NoteVisibility.values)),
            )
        self.stats['monthly_journals'] = MonthlyJournal.objects.count()
        self.stats['session_notes']    = SessionNote.objects.count()

    def _seed_invoices_and_payments(self):
        self.stdout.write('Seeding invoices, payments, refunds...')
        enrollments = list(Enrollment.objects.filter(is_deleted=False)[:50])
        today = timezone.localdate()
        inv_paid = inv_unpaid = inv_overdue = 0
        for e in enrollments:
            base = Decimal(e.price_at_enrollment or 500_000)
            inv = Invoice.objects.create(
                enrollment=e,
                amount=base,
                tax_amount=Decimal('0.00'),
                discount_amount=Decimal('0.00'),
                due_date=today + datetime.timedelta(days=random.randint(-14, 30)),
            )
            roll = random.random()
            if roll < 0.55:
                inv.status = InvoiceStatus.PAID
                inv.paid_at = timezone.now()
                inv.save(update_fields=['status', 'paid_at', 'updated_at'])
                inv_paid += 1
                # Matching payment
                Payment.objects.create(
                    invoice=inv,
                    amount=inv.total_amount,
                    method=random.choice(list(PaymentMethod.values)),
                    gateway=random.choice(list(PaymentGateway.values)),
                    status=PaymentStatus.SUCCESS,
                    paid_at=inv.paid_at,
                    transaction_id=f'TX-{inv.invoice_number}-{random.randint(1000, 9999)}',
                )
            elif inv.due_date < today:
                inv.status = InvoiceStatus.OVERDUE
                inv.save(update_fields=['status', 'updated_at'])
                inv_overdue += 1
            else:
                inv_unpaid += 1
        # Refunds — 5 of them, mixed statuses
        paid_payments = list(Payment.objects.filter(status=PaymentStatus.SUCCESS)[:5])
        admin = User.objects.filter(role=Role.ADMIN).first()
        for i, pmt in enumerate(paid_payments):
            status = random.choice(list(RefundStatus.values))
            Refund.objects.create(
                payment=pmt, invoice=pmt.invoice,
                amount=pmt.amount,
                reason='Permintaan refund dari siswa (demo).',
                status=status,
                requested_by=admin,
                approved_by=(admin if status in (RefundStatus.APPROVED, RefundStatus.PROCESSED) else None),
                approved_at=(timezone.now() if status in (RefundStatus.APPROVED, RefundStatus.PROCESSED) else None),
                processed_at=(timezone.now() if status == RefundStatus.PROCESSED else None),
                rejection_reason=('Tidak sesuai kebijakan' if status == RefundStatus.REJECTED else ''),
            )
        self.stats['invoices'] = Invoice.objects.count()
        self.stats['payments'] = Payment.objects.count()
        self.stats['refunds']  = Refund.objects.count()
        self.stats['invoices_paid']    = inv_paid
        self.stats['invoices_unpaid']  = inv_unpaid
        self.stats['invoices_overdue'] = inv_overdue

    # ── Summary ───────────────────────────────────────────────────────────────

    def _summary(self):
        s = self.stats
        self.stdout.write(self.style.SUCCESS('\n=== Dummy data generated ==='))
        self.stdout.write(f"Users:")
        self.stdout.write(f"  Admins              : {s.get('admins', 0)}")
        self.stdout.write(f"  Students            : {s.get('students', 0)}")
        self.stdout.write(f"  Teachers            : {s.get('teachers', 0)}")
        self.stdout.write(f"  (incl. pending/rejected demo accounts)")
        self.stdout.write(f"\nAcademics:")
        self.stdout.write(f"  Categories          : {s.get('categories', 0)}")
        self.stdout.write(f"  Subjects            : {s.get('subjects', 0)}")
        self.stdout.write(f"  Academic periods    : {s.get('academic_periods', 0)}")
        self.stdout.write(f"  Classes             : {s.get('classes', 0)}")
        self.stdout.write(f"  Schedules           : {s.get('schedules', 0)}")
        self.stdout.write(f"\nEnrollments / Sessions:")
        self.stdout.write(f"  Enrollments         : {s.get('enrollments', 0)}")
        self.stdout.write(f"  Sessions            : {s.get('sessions', 0)}")
        self.stdout.write(f"  Attendance records  : {s.get('attendance', 0)}")
        self.stdout.write(f"  Session bookings    : {s.get('session_bookings', 0)}")
        self.stdout.write(f"  Grades              : {s.get('grades', 0)}")
        self.stdout.write(f"\nNew tables:")
        self.stdout.write(f"  Notifications       : {s.get('notifications', 0)}")
        self.stdout.write(f"  Course materials    : {s.get('course_materials', 0)}")
        self.stdout.write(f"  Monthly journals    : {s.get('monthly_journals', 0)}")
        self.stdout.write(f"  Session notes       : {s.get('session_notes', 0)}")
        self.stdout.write(f"  Teacher ratings     : {s.get('teacher_ratings', 0)}")
        self.stdout.write(f"  Class ratings       : {s.get('class_ratings', 0)}")
        self.stdout.write(f"  Announcements       : {s.get('announcements', 0)}")
        self.stdout.write(f"\nBilling:")
        self.stdout.write(f"  Invoices            : {s.get('invoices', 0)} "
                          f"(paid={s.get('invoices_paid', 0)}, "
                          f"unpaid={s.get('invoices_unpaid', 0)}, "
                          f"overdue={s.get('invoices_overdue', 0)})")
        self.stdout.write(f"  Payments            : {s.get('payments', 0)}")
        self.stdout.write(f"  Refunds             : {s.get('refunds', 0)}")
        self.stdout.write(f"\nLogins:")
        self.stdout.write(f"  admin / admin1234")
        self.stdout.write(f"  student001 / murid123")
        self.stdout.write(f"  teacher001 / teacher123")
