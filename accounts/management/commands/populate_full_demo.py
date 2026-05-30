"""Populate comprehensive demo data for Phase 3A — idempotent + deterministic.

Usage:
    python manage.py populate_full_demo               # full populate, additive
    python manage.py populate_full_demo --reset       # wipe non-superuser data first
    python manage.py populate_full_demo --quick       # smaller dataset for fast testing
    python manage.py populate_full_demo --seed=123    # custom random seed (default 42)
"""
import random
from datetime import date, time, timedelta
from decimal import Decimal

from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone


class Command(BaseCommand):
    help = 'Populate comprehensive demo data for Phase 3A. Idempotent + deterministic.'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true', help='Wipe non-superuser content first.')
        parser.add_argument('--quick', action='store_true', help='Smaller, faster dataset.')
        parser.add_argument('--seed', type=int, default=42, help='Random seed (default: 42).')

    # ──────────────────────────────────────────────────────────────────────
    def handle(self, *args, **opts):
        seed = opts['seed']
        random.seed(seed)
        self.quick = bool(opts.get('quick'))

        self.NUM_CLASSES_NEW = 6 if self.quick else 18
        self.NUM_TEACHERS_TO_ENRICH = 10 if self.quick else 40
        self.NUM_SESSIONS_PER_CLASS = 8 if self.quick else 16
        self.NUM_JOURNAL_MONTHS = 2 if self.quick else 3

        self._h(f'GlowMath populate_full_demo (seed={seed}, quick={self.quick})')

        if opts.get('reset'):
            self._reset_data()

        try:
            with transaction.atomic():
                self._ensure_categories_and_subjects()
                self._enrich_teachers()
                self._ensure_academic_period()
                self._populate_classes()
                self._populate_schedules()
                self._populate_sessions()
                self._populate_enrollments()
                self._populate_session_bookings()
                self._populate_attendances()
                self._populate_grades()
                self._populate_ratings()
                self._ensure_rafael_completed()  # AFTER ratings so promoted enr stays unrated
                self._populate_journals()
                self._populate_announcements()
                self._populate_activity_logs()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\nERROR: {e}'))
            raise

        cache.clear()
        self.stdout.write('  [OK] All caches cleared\n')
        self._print_summary()
        self.stdout.write(self.style.SUCCESS('\n[DONE] populate_full_demo complete.\n'))

    def _h(self, text):
        self.stdout.write(self.style.SUCCESS('\n' + '=' * 60))
        self.stdout.write(self.style.SUCCESS(f'  {text}'))
        self.stdout.write(self.style.SUCCESS('=' * 60 + '\n'))

    def _ok(self, text):
        self.stdout.write(self.style.SUCCESS(f'  [OK] {text}'))

    # ── RESET ─────────────────────────────────────────────────────────────
    def _reset_data(self):
        from academics.models import Kelas, Schedule
        from activity_logs.models import ActivityLog
        from announcements.models import Announcement
        from enrollments.models import Enrollment
        from grades.models import Grade
        from journals.models import MonthlyJournal
        from ratings.models import ClassRating, TeacherRating
        from sessions_app.models import Attendance, Session

        self.stdout.write('Resetting non-superuser content...')
        ActivityLog.objects.all().delete()
        Attendance.objects.all().delete()
        Grade.objects.all().delete()
        MonthlyJournal.objects.all().delete()
        TeacherRating.objects.all().delete()
        ClassRating.objects.all().delete()
        Session.objects.all().delete()
        Schedule.objects.all().delete()
        Enrollment.objects.all().delete()
        Kelas.objects.all().delete()
        Announcement.objects.all().delete()
        self._ok('Reset complete')

    # ── 1. Categories + Subjects ──────────────────────────────────────────
    def _ensure_categories_and_subjects(self):
        from academics.models import Category, Subject

        cat_general, _ = Category.objects.get_or_create(
            name='Akademik Umum', defaults={'is_active': True}
        )

        subjects = [
            ('Matematika',         '🧮'),
            ('Fisika',             '⚛️'),
            ('Kimia',              '🧪'),
            ('Biologi',            '🧬'),
            ('Bahasa Inggris',     '🇬🇧'),
            ('Bahasa Indonesia',   '🇮🇩'),
            ('IPA Terpadu',        '🔬'),
            ('IPS Terpadu',        '🌍'),
            ('Matematika Dasar',   '➕'),
            ('Calistung',          '📝'),
        ]
        created = 0
        for name, icon in subjects:
            obj, was_created = Subject.objects.get_or_create(
                name=name,
                defaults={'category': cat_general, 'icon': icon, 'is_active': True},
            )
            if was_created:
                created += 1
            elif not obj.icon:
                obj.icon = icon
                obj.save(update_fields=['icon'])
        self._ok(f'Subjects ensured ({created} new)')

    # ── 2. Enrich teachers (bio, spec, experience, jenjang) ───────────────
    def _enrich_teachers(self):
        from accounts.models import (
            ApprovalStatus, Education, Level, TeacherJenjang, TeacherProfile,
        )

        SPECS = [
            'Matematika SMA & UTBK', 'Fisika SMP-SMA', 'Kimia SMA',
            'Biologi SMA', 'Bahasa Inggris (TOEFL/IELTS)', 'Bahasa Indonesia',
            'Matematika SD-SMP', 'Calistung TK', 'Persiapan UTBK Saintek',
            'Conversational English', 'Statistika & Probabilitas',
        ]
        BIOS = [
            'Pengajar berpengalaman dengan dedikasi membantu siswa meraih potensi terbaiknya. Saya percaya setiap anak bisa cerdas dengan pendekatan yang tepat.',
            'Lulusan universitas top dengan pengalaman 8+ tahun di pendidikan formal & non-formal. Suka pakai analogi sehari-hari untuk konsep sulit.',
            'Specialist pembimbingan UTBK & olimpiade. Track record siswa diterima PTN top. Materi terkurasi sesuai kurikulum terbaru.',
            'Mengajar dengan metode student-centered, fokus pada pemahaman konsep bukan hafalan. Banyak latihan soal HOTS untuk asah analisis.',
            'Pengajar yang sabar dan komunikatif. Selalu siap menjawab pertanyaan kapan pun. Materi dijelaskan step-by-step sampai siswa benar-benar paham.',
            'Alumni Indonesia Mengajar 2018. Cinta mengajar dan terus belajar pedagogi modern. Pernah workshop di Singapura dan Australia.',
            'Pendidik dengan fokus literasi & numerasi. Pengalaman ngajar di Jepang dan Indonesia. Sertifikasi TESOL dari University of Edinburgh.',
        ]
        EDUCATIONS = [Education.S1, Education.S1, Education.S1, Education.S2, Education.S2, Education.S3]
        ALL_LEVELS = [Level.TK, Level.SD, Level.SMP, Level.SMA, Level.UMUM]

        teachers = list(
            TeacherProfile.objects
            .filter(user__approval_status=ApprovalStatus.APPROVED)
            .select_related('user')
            .order_by('id')[:self.NUM_TEACHERS_TO_ENRICH]
        )
        enriched_count = 0
        jenjang_created = 0
        for tp in teachers:
            updates = {}
            if not tp.bio:
                updates['bio'] = random.choice(BIOS)
            if not tp.specialization:
                updates['specialization'] = random.choice(SPECS)
            if not tp.education:
                updates['education'] = random.choice(EDUCATIONS)
            if not tp.experience_years:
                updates['experience_years'] = random.randint(2, 15)
            if updates:
                for k, v in updates.items():
                    setattr(tp, k, v)
                tp.save()
                enriched_count += 1
            # Assign 1–3 jenjang
            num_j = random.randint(1, 3)
            chosen = random.sample(ALL_LEVELS, num_j)
            for lvl in chosen:
                _, was_created = TeacherJenjang.objects.get_or_create(
                    teacher_profile=tp, level=lvl,
                )
                if was_created:
                    jenjang_created += 1
        self._ok(f'Teachers enriched: {enriched_count}, new jenjang rows: {jenjang_created}')

    # ── 3. Academic Period ────────────────────────────────────────────────
    def _ensure_academic_period(self):
        from academics.models import AcademicPeriod, PeriodType, Quarter
        today = timezone.localdate()
        year_str = str(today.year)
        period, created = AcademicPeriod.objects.get_or_create(
            year=year_str,
            quarter=Quarter.Q2,
            period_type=PeriodType.QUARTER,
            defaults={
                'name': f'Q2 {year_str}',
                'start_date': date(today.year, 4, 1),
                'end_date': date(today.year, 6, 30),
                'is_active': True,
            },
        )
        self.current_period = period
        self._ok(f'AcademicPeriod ready ({"new" if created else "existing"}: {period.name})')

    # ── 4. Classes ────────────────────────────────────────────────────────
    def _populate_classes(self):
        from academics.models import Kelas, KelasStatus, Subject
        from accounts.models import (
            ApprovalStatus, Level, TeacherJenjang, TeacherProfile,
        )

        templates = [
            # (level, subject_name, name, capacity, price, status)
            (Level.TK,   'Calistung',          'Calistung Ceria TK A',                8,  200000, KelasStatus.OPEN),
            (Level.SD,   'Matematika Dasar',   'Matematika SD Kelas 1-3 Asyik',      15,  300000, KelasStatus.OPEN),
            (Level.SD,   'Bahasa Inggris',     'English for Kids SD',                10,  400000, KelasStatus.OPEN),
            (Level.SMP,  'Matematika',         'Matematika SMP Komprehensif',        18,  450000, KelasStatus.OPEN),
            (Level.SMP,  'Fisika',             'Fisika SMP Dasar',                   15,  450000, KelasStatus.OPEN),
            (Level.SMP,  'IPA Terpadu',        'IPA Terpadu SMP',                    20,  400000, KelasStatus.OPEN),
            (Level.SMA,  'Matematika',         'Matematika UTBK Intensif',           15,  500000, KelasStatus.OPEN),
            (Level.SMA,  'Matematika',         'Matematika Peminatan IPA Kelas 12',  12,  550000, KelasStatus.OPEN),
            (Level.SMA,  'Fisika',             'Fisika UTBK Saintek',                15,  550000, KelasStatus.OPEN),
            (Level.SMA,  'Kimia',              'Kimia UTBK Reguler',                 15,  550000, KelasStatus.OPEN),
            (Level.SMA,  'Biologi',            'Biologi UTBK Saintek',               15,  550000, KelasStatus.OPEN),
            (Level.SMA,  'Bahasa Inggris',     'Bahasa Inggris UTBK',                15,  480000, KelasStatus.OPEN),
            (Level.UMUM, 'Matematika',         'Statistika & Probabilitas',          15,  550000, KelasStatus.OPEN),
            (Level.UMUM, 'Bahasa Inggris',     'TOEFL Preparation iBT',              15,  750000, KelasStatus.OPEN),
            (Level.UMUM, 'Bahasa Inggris',     'IELTS Academic Reguler',             12,  800000, KelasStatus.OPEN),
            (Level.UMUM, 'Bahasa Inggris',     'Business English Conversation',      10,  700000, KelasStatus.OPEN),
            # Two FULL classes for testing the locked-CTA / waitlist UX
            (Level.SMA,  'Matematika',         'Matematika UTBK Premium (FULL)',      6,  800000, KelasStatus.FULL),
            (Level.UMUM, 'Bahasa Inggris',     'TOEFL Express Bootcamp (FULL)',       5, 1000000, KelasStatus.FULL),
        ][: self.NUM_CLASSES_NEW]

        # Pre-fetch teachers grouped by jenjang
        teachers_by_level = {lvl: [] for lvl in [Level.TK, Level.SD, Level.SMP, Level.SMA, Level.UMUM]}
        for tj in TeacherJenjang.objects.select_related('teacher_profile__user').filter(
            teacher_profile__user__approval_status=ApprovalStatus.APPROVED,
        ):
            if tj.level in teachers_by_level:
                teachers_by_level[tj.level].append(tj.teacher_profile)
        # De-dupe
        for lvl in teachers_by_level:
            seen = set()
            teachers_by_level[lvl] = [
                t for t in teachers_by_level[lvl]
                if (t.pk not in seen and not seen.add(t.pk))
            ]
        # Fallback pool
        fallback_pool = list(TeacherProfile.objects.filter(
            user__approval_status=ApprovalStatus.APPROVED
        ))

        today = timezone.localdate()
        created = 0
        for level, subj_name, name, capacity, price, status in templates:
            try:
                subject = Subject.objects.get(name=subj_name)
            except Subject.DoesNotExist:
                continue
            candidates = teachers_by_level.get(level) or fallback_pool
            if not candidates:
                continue
            teacher = random.choice(candidates)
            # Future-dated to keep them enrollable + COMPLETED-able
            start_date = today + timedelta(days=random.randint(7, 45))
            end_date = start_date + timedelta(days=random.randint(90, 150))
            _, was_created = Kelas.objects.get_or_create(
                name=name,
                defaults={
                    'subject': subject,
                    'teacher_profile': teacher,
                    'level': level,
                    'capacity': capacity,
                    'price': Decimal(price),
                    'status': status,
                    'academic_period': self.current_period,
                    'start_date': start_date,
                    'end_date': end_date,
                    'total_sessions': self.NUM_SESSIONS_PER_CLASS,
                    'description': (
                        f'Kelas {name} untuk jenjang {level}. Diasuh oleh pengajar '
                        f'berpengalaman dengan materi terkurasi, banyak latihan soal HOTS, '
                        f'dan simulasi rutin untuk persiapan ujian.'
                    ),
                },
            )
            if was_created:
                created += 1
        self._ok(f'Classes: {created} new, {len(templates) - created} already existed')

    # ── 5. Schedules ──────────────────────────────────────────────────────
    def _populate_schedules(self):
        from academics.models import Day, Kelas, Schedule

        DAYS = [Day.MONDAY, Day.TUESDAY, Day.WEDNESDAY, Day.THURSDAY, Day.FRIDAY, Day.SATURDAY]
        SLOTS = [
            (time(8, 0),  time(10, 0)),
            (time(10, 0), time(12, 0)),
            (time(13, 0), time(15, 0)),
            (time(15, 30), time(17, 30)),
            (time(16, 0), time(18, 0)),
            (time(18, 0), time(20, 0)),
            (time(19, 0), time(21, 0)),
        ]
        no_sched = (
            Kelas.objects
            .filter(is_deleted=False)
            .exclude(pk__in=Schedule.objects.values_list('kelas_id', flat=True).distinct())
        )
        created = 0
        for kelas in no_sched:
            num_days = random.randint(2, 3)
            picked_days = random.sample(DAYS, num_days)
            start, end = random.choice(SLOTS)
            for day in picked_days:
                _, was_created = Schedule.objects.get_or_create(
                    kelas=kelas, day=day, start_time=start,
                    defaults={'end_time': end, 'room': ''},
                )
                if was_created:
                    created += 1
        self._ok(f'Schedules: {created} new')

    # ── 6. Sessions ───────────────────────────────────────────────────────
    def _populate_sessions(self):
        from academics.models import Kelas
        from sessions_app.models import Session, SessionStatus

        TOPICS = {
            'Matematika':       ['Bilangan & Operasi', 'Aljabar Dasar', 'Geometri', 'Trigonometri', 'Statistika', 'Probabilitas', 'Logaritma', 'Limit', 'Turunan', 'Integral'],
            'Fisika':           ['Kinematika', 'Dinamika', 'Energi & Usaha', 'Momentum', 'Fluida', 'Termodinamika', 'Gelombang', 'Listrik', 'Magnet', 'Atom'],
            'Kimia':            ['Struktur Atom', 'Ikatan Kimia', 'Stoikiometri', 'Larutan', 'Asam Basa', 'Termokimia', 'Redoks', 'Kimia Organik'],
            'Biologi':          ['Sel & Jaringan', 'Ekologi', 'Genetika', 'Evolusi', 'Sistem Pencernaan', 'Sistem Saraf', 'Imunitas'],
            'Bahasa Inggris':   ['Tenses Review', 'Reading Comprehension', 'Vocabulary Building', 'Grammar In Context', 'Listening Practice', 'TOEFL Strategies', 'Essay Writing'],
            'Bahasa Indonesia': ['Struktur Kalimat', 'Paragraf Argumentatif', 'Teks Eksposisi', 'Karya Sastra', 'EYD/PUEBI'],
            'default':          ['Pengenalan Materi', 'Latihan Soal', 'Pembahasan', 'Quiz Mingguan', 'Review Materi', 'Mid Test', 'Final Test'],
        }
        DAY_MAP = {'MONDAY': 0, 'TUESDAY': 1, 'WEDNESDAY': 2, 'THURSDAY': 3, 'FRIDAY': 4, 'SATURDAY': 5}

        today = timezone.localdate()
        now_t = timezone.now().time()
        total_created = 0

        # All non-deleted classes
        kelases = list(
            Kelas.objects.filter(is_deleted=False)
            .select_related('subject')
            .prefetch_related('schedules')
        )
        for kelas in kelases:
            schedules = list(kelas.schedules.all())
            if not schedules:
                continue
            existing = Session.objects.filter(kelas=kelas).count()
            if existing >= self.NUM_SESSIONS_PER_CLASS:
                continue
            target_topics = TOPICS.get(kelas.subject.name, TOPICS['default'])
            need = self.NUM_SESSIONS_PER_CLASS - existing
            # Start ~4 weeks ago so we have past + future sessions
            cursor = (kelas.start_date or today) - timedelta(days=28)
            made = 0
            sess_n = existing + 1
            steps = 0
            while made < need and steps < 200:
                weekday = cursor.weekday()
                hit = [s for s in schedules if DAY_MAP.get(s.day, -1) == weekday]
                if hit:
                    sched = hit[0]
                    topic = target_topics[(existing + made) % len(target_topics)]
                    # Status by date
                    if cursor < today:
                        status = SessionStatus.COMPLETED
                    elif cursor == today and sched.start_time < now_t:
                        status = SessionStatus.COMPLETED
                    else:
                        status = SessionStatus.SCHEDULED
                    _, was_created = Session.objects.get_or_create(
                        kelas=kelas, date=cursor, start_time=sched.start_time,
                        defaults={
                            'end_time': sched.end_time,
                            'session_number': sess_n,
                            'topic': topic,
                            'status': status,
                            'capacity': kelas.capacity,
                            'meeting_url': (
                                f'https://zoom.us/j/demo-{kelas.pk}-{sess_n}'
                                if random.random() > 0.4 else ''
                            ),
                        },
                    )
                    if was_created:
                        total_created += 1
                    sess_n += 1
                    made += 1
                cursor += timedelta(days=1)
                steps += 1
        self._ok(f'Sessions: {total_created} new')

    # ── 7. Enrollments ────────────────────────────────────────────────────
    def _populate_enrollments(self):
        from academics.models import Kelas, KelasStatus
        from accounts.models import ApprovalStatus, Level, StudentProfile
        from enrollments.models import Enrollment, EnrollmentStatus

        students_by_level = {}
        for lvl in [Level.TK, Level.SD, Level.SMP, Level.SMA, Level.UMUM]:
            students_by_level[lvl] = list(
                StudentProfile.objects.filter(
                    user__approval_status=ApprovalStatus.APPROVED,
                    user__is_active=True,
                    user__is_deleted=False,
                    level=lvl,
                )
            )
        kelases = list(
            Kelas.objects.filter(is_deleted=False)
            .exclude(status=KelasStatus.CLOSED)
        )
        total_created = 0
        for kelas in kelases:
            level_pool = students_by_level.get(kelas.level) or []
            if not level_pool:
                continue
            existing_active = Enrollment.objects.filter(
                kelas=kelas, status=EnrollmentStatus.ACTIVE, is_deleted=False
            ).count()
            # Target: FULL kelas → 100%, otherwise 35–85% of capacity
            if kelas.status == KelasStatus.FULL:
                target = kelas.capacity
            else:
                target = int(kelas.capacity * random.uniform(0.35, 0.85))
            needed = max(0, target - existing_active)
            if not needed:
                continue
            enrolled_ids = set(
                Enrollment.objects.filter(kelas=kelas)
                .values_list('student_profile_id', flat=True)
            )
            free_students = [s for s in level_pool if s.pk not in enrolled_ids]
            random.shuffle(free_students)
            for s in free_students[:needed]:
                # Status mix — but if kelas is FULL, force ACTIVE
                if kelas.status == KelasStatus.FULL:
                    status = EnrollmentStatus.ACTIVE
                else:
                    r = random.random()
                    if r < 0.72:
                        status = EnrollmentStatus.ACTIVE
                    elif r < 0.92:
                        status = EnrollmentStatus.COMPLETED
                    else:
                        status = EnrollmentStatus.DROPPED
                try:
                    _, was_created = Enrollment.objects.get_or_create(
                        student_profile=s, kelas=kelas,
                        defaults={
                            'status': status,
                            'price_at_enrollment': kelas.price,
                        },
                    )
                    if was_created:
                        total_created += 1
                except Exception:
                    continue
        self._ok(f'Enrollments: {total_created} new')

    # ── 7b. Ensure Rafael has 1 unrated COMPLETED enrollment ──────────────
    def _ensure_rafael_completed(self):
        from accounts.models import User
        from enrollments.models import Enrollment, EnrollmentStatus
        from ratings.models import ClassRating, TeacherRating

        try:
            rafael = User.objects.get(username='rafaeladhikabagasalfathan')
        except User.DoesNotExist:
            return
        if not hasattr(rafael, 'student_profile'):
            return
        sp = rafael.student_profile
        # Already have an unrated COMPLETED? Done.
        completed_unrated = (
            Enrollment.objects
            .filter(student_profile=sp, status=EnrollmentStatus.COMPLETED, is_deleted=False)
            .exclude(pk__in=TeacherRating.objects.values_list('enrollment_id', flat=True))
            .first()
        )
        if completed_unrated:
            self._ok(f'Rafael already has unrated COMPLETED enrollment #{completed_unrated.pk}')
            return
        # Otherwise pick a COMPLETED (any) and strip its ratings, or promote ACTIVE.
        target = (
            Enrollment.objects
            .filter(student_profile=sp, status=EnrollmentStatus.COMPLETED, is_deleted=False)
            .first()
        )
        if not target:
            target = (
                Enrollment.objects
                .filter(student_profile=sp, status=EnrollmentStatus.ACTIVE, is_deleted=False)
                .first()
            )
            if target:
                target.status = EnrollmentStatus.COMPLETED
                target.save(update_fields=['status', 'updated_at'])
        if target:
            TeacherRating.objects.filter(enrollment=target).delete()
            ClassRating.objects.filter(enrollment=target).delete()
            self._ok(f'Ensured Rafael enrollment #{target.pk} is COMPLETED + unrated (for Rate Teacher test)')

    # ── 7c. Session-level bookings ─────────────────────────────────────────
    # Phase 3R schema unlock — for every ACTIVE Enrollment, seed a
    # SessionBooking(kind=AUTO) row for every REGULAR Session in that
    # enrollment's kelas. Capacity-respecting (skips full sessions) and
    # idempotent via get_or_create on unique_together (enrollment, session).
    # MAKEUP/OPTIONAL bookings remain historical (already kind='MAKEUP'
    # via the 0002 data migration).
    def _populate_session_bookings(self):
        from django.db.models import Count
        from enrollments.models import Enrollment, EnrollmentStatus
        from sessions_app.models import (
            BookingKind, BookingStatus, Session, SessionBooking, SessionType,
        )

        active_enrollments = (
            Enrollment.objects
            .filter(status=EnrollmentStatus.ACTIVE, is_deleted=False)
            .select_related('kelas')
        )
        # Pre-fetch REGULAR sessions grouped by kelas to avoid N+1.
        regular_sessions_by_kelas = {}
        for s in Session.objects.filter(session_type=SessionType.REGULAR).order_by('kelas_id', 'session_number'):
            regular_sessions_by_kelas.setdefault(s.kelas_id, []).append(s)

        # Track per-session booked count so capacity is respected across the
        # whole seed pass (not just per-DB hit).
        per_session_count = dict(
            SessionBooking.objects
            .filter(status=BookingStatus.BOOKED, is_deleted=False)
            .values('session_id')
            .annotate(n=Count('id'))
            .values_list('session_id', 'n')
        )

        created = 0
        skipped_capacity = 0
        for enr in active_enrollments:
            for sess in regular_sessions_by_kelas.get(enr.kelas_id, []):
                cap = sess.capacity or 0
                if cap > 0 and per_session_count.get(sess.id, 0) >= cap:
                    skipped_capacity += 1
                    continue
                _, was_created = SessionBooking.objects.get_or_create(
                    enrollment=enr,
                    session=sess,
                    defaults={
                        'status': BookingStatus.BOOKED,
                        'kind': BookingKind.AUTO,
                    },
                )
                if was_created:
                    per_session_count[sess.id] = per_session_count.get(sess.id, 0) + 1
                    created += 1
        self._ok(
            f'SessionBookings (kind=AUTO): {created} new'
            + (f' ({skipped_capacity} skipped — session at capacity)' if skipped_capacity else '')
        )

    # ── 8. Attendances ────────────────────────────────────────────────────
    def _populate_attendances(self):
        from enrollments.models import Enrollment, EnrollmentStatus
        from sessions_app.models import Attendance, AttendanceStatus, Session, SessionStatus

        completed = (
            Session.objects.filter(status=SessionStatus.COMPLETED)
            .select_related('kelas')
        )
        marker = None  # marked_by is FK to User, but optional. We leave blank.
        total_created = 0
        for sess in completed:
            enrollments = list(
                Enrollment.objects.filter(
                    kelas=sess.kelas,
                    status__in=[EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED],
                    is_deleted=False,
                )
            )
            existing_ids = set(
                Attendance.objects.filter(session=sess).values_list('enrollment_id', flat=True)
            )
            for enr in enrollments:
                if enr.pk in existing_ids:
                    continue
                r = random.random()
                if r < 0.80:
                    st = AttendanceStatus.PRESENT
                elif r < 0.92:
                    st = AttendanceStatus.PERMITTED
                else:
                    st = AttendanceStatus.ABSENT
                Attendance.objects.create(
                    session=sess,
                    enrollment=enr,
                    status=st,
                    marked_by=marker,
                )
                total_created += 1
        self._ok(f'Attendances: {total_created} new')

    # ── 9. Grades ─────────────────────────────────────────────────────────
    def _populate_grades(self):
        from enrollments.models import Enrollment, EnrollmentStatus
        from grades.models import Grade, GradeType

        # Grade.clean() requires session for QUIZ/ASSIGNMENT. To keep
        # this code simple + safe we only create MIDTERM + FINAL grades
        # (no session FK required). Both have explicit grade_type.
        enrollments = (
            Enrollment.objects
            .filter(status__in=[EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED], is_deleted=False)
            .select_related('kelas__teacher_profile')
        )
        total = 0
        for enr in enrollments:
            existing = Grade.objects.filter(enrollment=enr).count()
            if existing >= 4:
                continue
            graded_by = enr.kelas.teacher_profile
            for gt in (GradeType.MIDTERM, GradeType.FINAL):
                if Grade.objects.filter(enrollment=enr, grade_type=gt, session__isnull=True).exists():
                    continue
                # Bell-curve score around 80
                raw = random.gauss(80, 9)
                score = max(40, min(100, raw))
                Grade.objects.create(
                    enrollment=enr,
                    grade_type=gt,
                    score=Decimal(f'{score:.1f}'),
                    graded_by_teacher=graded_by,
                    notes='',
                )
                total += 1
        self._ok(f'Grades: {total} new (MIDTERM + FINAL only — quiz/assignment skipped)')

    # ── 10. Ratings (TeacherRating + ClassRating) ─────────────────────────
    def _populate_ratings(self):
        from enrollments.models import Enrollment, EnrollmentStatus
        from ratings.models import ClassRating, TeacherRating

        T_COMMENTS = [
            'Pengajar sabar dan jelas. Recommended!',
            'Cara menjelaskan mudah dipahami. Materi tertata baik.',
            'Sangat membantu memahami konsep yang sulit.',
            'Pengajar profesional dan responsif terhadap pertanyaan.',
            'Mengajar dengan penuh semangat dan inspiratif.',
            'Penjelasan jelas, banyak contoh latihan. Worth it!',
            'Cukup membantu, semoga makin interaktif di kelas berikutnya.',
            'Mantap! Score saya naik banyak setelah ikut kelas ini.',
        ]
        C_COMMENTS = [
            'Materi lengkap dan terstruktur. Latihannya menantang.',
            'Jadwal pas, harga worth it untuk kualitas yang didapat.',
            'Banyak latihan soal HOTS. Simulasi rutin sangat membantu.',
            'Kelas yang bagus untuk persiapan ujian. Recommended.',
            'Konten kelas berkualitas, sesuai ekspektasi.',
            'Cukup memuaskan, tapi bisa lebih banyak materi tambahan.',
            'Worth every penny. Materi update dengan kurikulum terbaru.',
        ]
        completed = (
            Enrollment.objects
            .filter(status=EnrollmentStatus.COMPLETED, is_deleted=False)
            .select_related('kelas__teacher_profile')
        )
        t_new = c_new = 0
        for enr in completed:
            # Only rate ~70% of completed enrollments — leaves some empty for realism
            if random.random() > 0.70:
                continue
            # Skewed-high distribution
            r = random.random()
            t_score = 5 if r < 0.50 else 4 if r < 0.80 else 3 if r < 0.95 else random.choice([1, 2])
            r2 = random.random()
            c_score = 5 if r2 < 0.45 else 4 if r2 < 0.80 else 3 if r2 < 0.95 else random.choice([1, 2])

            _, was_created = TeacherRating.objects.get_or_create(
                enrollment=enr,
                defaults={
                    'teacher_profile': enr.kelas.teacher_profile,
                    'score': t_score,
                    'comment': random.choice(T_COMMENTS) if random.random() > 0.3 else '',
                },
            )
            if was_created:
                t_new += 1
            _, was_created = ClassRating.objects.get_or_create(
                enrollment=enr,
                defaults={
                    'kelas': enr.kelas,
                    'score': c_score,
                    'comment': random.choice(C_COMMENTS) if random.random() > 0.3 else '',
                },
            )
            if was_created:
                c_new += 1
        self._ok(f'Ratings: TeacherRating {t_new} new, ClassRating {c_new} new')

    # ── 11. Monthly Journals ──────────────────────────────────────────────
    def _populate_journals(self):
        from enrollments.models import Enrollment, EnrollmentStatus
        from journals.models import MonthlyJournal

        SUMMARIES = [
            'Bulan ini siswa menunjukkan progress signifikan dalam pemahaman materi. Aktif bertanya dan partisipasi diskusi baik.',
            'Siswa mulai menguasai konsep dasar. Latihan soal mandiri sudah konsisten dengan akurasi 80%+.',
            'Kemampuan analisis siswa meningkat. Mulai bisa kerjakan soal HOTS dengan strategi sendiri. Perlu lebih percaya diri.',
            'Bulan ini siswa fokus pada perbaikan miskonsepsi awal. Hasil quiz terakhir naik dari 65 ke 78.',
            'Siswa rajin hadir dan disiplin latihan. Direkomendasikan untuk ikut try out simulasi UTBK bulan depan.',
        ]
        TOPICS = [
            'Aljabar dan Pertidaksamaan',
            'Geometri Bangun Datar dan Ruang',
            'Trigonometri Lanjut',
            'Statistika Deskriptif',
            'Limit dan Turunan Fungsi',
        ]
        STRENGTHS = [
            'Cepat menangkap konsep baru, aktif berdiskusi.',
            'Konsisten mengerjakan PR & rajin bertanya.',
            'Kemampuan analisis soal HOTS makin baik.',
            'Manajemen waktu pengerjaan latihan rapi.',
        ]
        IMPROV = [
            'Perlu menambah latihan soal aplikasi konsep.',
            'Bisa lebih percaya diri menjawab di kelas.',
            'Tingkatkan ketelitian dalam perhitungan akhir.',
            'Coba review materi minggu lalu sebelum sesi baru.',
        ]
        today = timezone.localdate()
        enrollments = Enrollment.objects.filter(
            status__in=[EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED],
            is_deleted=False,
        ).select_related('kelas__teacher_profile')
        total = 0
        for enr in enrollments:
            for offset in range(self.NUM_JOURNAL_MONTHS):
                target = today.replace(day=15) - timedelta(days=30 * offset)
                _, was_created = MonthlyJournal.objects.get_or_create(
                    enrollment=enr,
                    year=target.year,
                    month=target.month,
                    defaults={
                        'written_by_teacher': enr.kelas.teacher_profile,
                        'summary': random.choice(SUMMARIES),
                        'topics_covered': random.choice(TOPICS),
                        'strengths': random.choice(STRENGTHS),
                        'areas_for_improvement': random.choice(IMPROV),
                    },
                )
                if was_created:
                    total += 1
        self._ok(f'MonthlyJournals: {total} new')

    # ── 12. Announcements ─────────────────────────────────────────────────
    def _populate_announcements(self):
        from accounts.models import Role, User
        from announcements.models import Announcement

        admin = (
            User.objects
            .filter(role=Role.ADMIN, is_active=True)
            .order_by('-is_superuser', 'id')
            .first()
        )
        if not admin:
            return
        items = [
            ('🎉 Kelas Baru: TOEFL iBT Intensive!',
             'Kami baru saja membuka kelas TOEFL iBT Intensive khusus untuk persiapan tes resmi. '
             'Daftar sekarang, dapatkan diskon early bird hingga 20%!',
             'ALL'),
            ('📚 Tips Belajar Efektif untuk UTBK',
             'Halo siswa SMA! Berikut 5 tips belajar efektif menjelang UTBK: '
             '1) Buat jadwal harian, 2) Latihan soal rutin, 3) Cukup tidur, '
             '4) Konsultasi rutin dengan guru, 5) Tetap semangat!',
             'STUDENT'),
            ('⚠️ Pemeliharaan Sistem Sabtu Malam',
             'Sistem akan maintenance pada Sabtu, 25 Mei 2026, jam 23:00–01:00 WIB. '
             'Mohon maaf atas ketidaknyamanannya.',
             'ALL'),
            ('🏆 Selamat untuk Para Juara Kelas Bulan Ini!',
             'Selamat kepada Andi, Sari, dan Bagas yang berhasil meraih nilai tertinggi bulan ini. '
             'Pertahankan prestasinya 👏',
             'ALL'),
        ]
        new = 0
        for title, content, target in items:
            _, was_created = Announcement.objects.get_or_create(
                title=title,
                defaults={
                    'content': content,
                    'author': admin,
                    'target_role': target,
                    'is_active': True,
                },
            )
            if was_created:
                new += 1
        self._ok(f'Announcements: {new} new')

    # ── 13. Activity Logs ─────────────────────────────────────────────────
    def _populate_activity_logs(self):
        from accounts.models import User
        from activity_logs.models import ActivityLog

        if ActivityLog.objects.count() > 50:
            self._ok('ActivityLog already populated (skip)')
            return
        users = list(User.objects.filter(is_active=True).order_by('id')[:30])
        if not users:
            return
        ACTIONS = ['login', 'created', 'updated', 'rated', 'approved']
        TARGETS = ['enrollment', 'rating', 'session', 'user', 'kelas']
        IPS = ['127.0.0.1', '192.168.1.45', '110.137.89.12', '36.78.234.5', '203.142.65.78']
        for _ in range(50):
            ActivityLog.objects.create(
                user=random.choice(users),
                action=random.choice(ACTIONS),
                target_type=random.choice(TARGETS),
                ip_address=random.choice(IPS),
                user_agent='Mozilla/5.0 (compatible; demo data)',
            )
        self._ok('ActivityLog: 50 new')

    # ── Summary ───────────────────────────────────────────────────────────
    def _print_summary(self):
        from accounts.models import StudentProfile, TeacherProfile, User
        from academics.models import Kelas
        from enrollments.models import Enrollment, EnrollmentStatus
        from grades.models import Grade
        from journals.models import MonthlyJournal
        from ratings.models import ClassRating, TeacherRating
        from sessions_app.models import Attendance, Session
        self.stdout.write(self.style.SUCCESS('\nSUMMARY:'))
        self.stdout.write(f'  Users:                {User.objects.count():>4}')
        self.stdout.write(f'    Students:           {StudentProfile.objects.count():>4}')
        self.stdout.write(f'    Teachers:           {TeacherProfile.objects.count():>4}')
        self.stdout.write(f'  Kelas:                {Kelas.objects.filter(is_deleted=False).count():>4}')
        self.stdout.write(f'  Enrollments:          {Enrollment.objects.count():>4}')
        self.stdout.write(f'    ACTIVE:             {Enrollment.objects.filter(status=EnrollmentStatus.ACTIVE).count():>4}')
        self.stdout.write(f'    COMPLETED:          {Enrollment.objects.filter(status=EnrollmentStatus.COMPLETED).count():>4}')
        self.stdout.write(f'    DROPPED:            {Enrollment.objects.filter(status=EnrollmentStatus.DROPPED).count():>4}')
        self.stdout.write(f'  Sessions:             {Session.objects.count():>4}')
        self.stdout.write(f'  Attendances:          {Attendance.objects.count():>4}')
        self.stdout.write(f'  Grades:               {Grade.objects.count():>4}')
        self.stdout.write(f'  TeacherRating:        {TeacherRating.objects.count():>4}')
        self.stdout.write(f'  ClassRating:          {ClassRating.objects.count():>4}')
        self.stdout.write(f'  MonthlyJournals:      {MonthlyJournal.objects.count():>4}')
