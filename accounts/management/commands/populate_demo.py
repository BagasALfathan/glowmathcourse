"""Populate a named demo cohort for client demos.

Creates / updates 7 demo accounts (rafael + trista already exist via
create_test_users + populate_rafael / populate_trista; this command adds five
more students across all five jenjang) and gives each new student full,
realistic data: 2 enrollments (one COMPLETED + one ACTIVE), sessions,
attendance, grades, one MonthlyJournal, one TeacherRating + ClassRating on the
COMPLETED enrollment, and a handful of notifications.

Idempotent: re-running will not duplicate users, profiles, classes, sessions,
attendance, grades, journals, or ratings (guarded by get_or_create / exists()
like the existing populate_* commands).

Run order (against the dev DB):
    python manage.py create_test_users
    python manage.py populate_rafael
    python manage.py populate_trista
    python manage.py populate_demo
"""
import random
from datetime import date, time, timedelta
from decimal import Decimal

from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import (
    ApprovalStatus, Education, Gender, Level, Role,
    StudentProfile, TeacherJenjang, TeacherProfile, User,
)
from academics.models import (
    AcademicPeriod, Category, Kelas, KelasStatus, KelasType, PeriodType,
    Quarter, Schedule, Subject,
)
from enrollments.models import Enrollment, EnrollmentStatus
from grades.models import Grade, GradeType
from journals.models import MonthlyJournal
from notifications.models import Notification, NotificationType
from ratings.models import ClassRating, TeacherRating
from sessions_app.models import (
    Attendance, AttendanceStatus, Session, SessionStatus, SessionType,
)
from django.db import models
from sessions_app.services import (
    SEAT_GANJIL, SEAT_GENAP, anchor_new_batch, auto_book_parity_sessions,
    book_enrollment_into_current_batch, generate_sessions_for_kelas,
)


PASSWORD = 'ikanbuvivid'

# Match populate_rafael's day map
WEEKDAY_TO_DAY = [
    'MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY',
    'FRIDAY', 'SATURDAY', 'SUNDAY',
]


# ── Demo student specs (rafael excluded — handled by populate_rafael) ──────

DEMO_STUDENTS = [
    {
        'username': 'bimdarmawa',
        'email': 'bimdarmawa@gmail.com',
        'first': 'Bim',
        'last': 'Darmawa',
        'level': Level.SMA,
        'school': 'SMA Negeri 8 Jakarta',
        'grade': 11,
        'gender': Gender.MALE,
        'parent_name': 'Bapak Hendra Darmawa',
        'parent_phone': '0812' + '99887701',
        'phone': '0821' + '11220001',
        'address': 'Jl. Bukit Duri Tanjakan No. 14, Jakarta Selatan',
        'note': None,
    },
    {
        'username': 'yohanes',
        'email': 'yohanes@gmail.com',
        'first': 'Yohanes',
        'last': 'Praditya',
        # Level stays SMA because SMK is not a valid Level value — we record
        # the SMK context in school_name and the note below.
        'level': Level.SMA,
        'school': 'SMK Negeri 26 Jakarta (Teknik Komputer & Jaringan)',
        'grade': 11,
        'gender': Gender.MALE,
        'parent_name': 'Bapak Yulius Praditya',
        'parent_phone': '0813' + '55667702',
        'phone': '0821' + '11220002',
        'address': 'Jl. Pedati No. 8, Jakarta Timur',
        'note': 'Siswa SMK (jurusan TKJ) — level disimpan sebagai SMA karena SMK belum tersedia di pilihan jenjang.',
    },
    {
        'username': 'dianfera',
        'email': 'dianfera@gmail.com',
        'first': 'Dian',
        'last': 'Fera Anggraini',
        'level': Level.SMP,
        'school': 'SMP Negeri 3 Jakarta',
        'grade': 8,
        'gender': Gender.FEMALE,
        'parent_name': 'Ibu Sri Anggraini',
        'parent_phone': '0856' + '11223303',
        'phone': '0821' + '11220003',
        'address': 'Jl. Cikini Raya No. 22, Jakarta Pusat',
        'note': None,
    },
    {
        'username': 'gracia',
        'email': 'gracia@gmail.com',
        'first': 'Gracia',
        'last': 'Putri Maharani',
        'level': Level.SD,
        'school': 'SD Negeri Menteng 02',
        'grade': 4,
        'gender': Gender.FEMALE,
        'parent_name': 'Ibu Maharani Lestari',
        'parent_phone': '0877' + '33445504',
        'phone': '0821' + '11220004',
        'address': 'Jl. Menteng Raya No. 5, Jakarta Pusat',
        'note': None,
    },
    {
        'username': 'azriel',
        'email': 'azriel@gmail.com',
        'first': 'Azriel',
        'last': 'Hakim',
        'level': Level.TK,
        'school': 'TK Cendana Jakarta',
        'grade': 2,  # TK B
        'gender': Gender.MALE,
        'parent_name': 'Bapak Faisal Hakim',
        'parent_phone': '0857' + '22334405',
        'phone': '0821' + '11220005',
        'address': 'Jl. Cipete Selatan No. 17, Jakarta Selatan',
        'note': None,
    },
]

# Realistic year-from-grade offsets per jenjang
AGE_BY_LEVEL = {
    Level.TK: 5,
    Level.SD: 7,    # + grade-1 → grade 4 = age 10
    Level.SMP: 12,  # + (grade-7) → grade 8 = age 13
    Level.SMA: 15,  # + (grade-10) → grade 11 = age 16
    Level.UMUM: 20,
}


# ── Extra classes that need to exist so each student has 2 same-jenjang options
# ── (populate_trista creates only 1 SD + 1 SMP; we need a 2nd of each)

EXTRA_TRISTA_CLASSES = [
    # (kelas name,                 subject,         subject_desc,                  level,    price,    weeks)
    ('Calistung SD - Pengayaan',   'Calistung SD',  'Calistung pengayaan SD',      'SD',     220_000,  8),
    ('Geometri SMP - Pengayaan',   'Geometri SMP',  'Geometri dan bangun ruang SMP', 'SMP',  320_000,  8),
]

# TK teacher + 2 classes (TK is not covered by Trista or any existing seeder)
TK_CLASSES = [
    ('Calistung Ceria TK A',  'Calistung TK',  'Membaca, menulis, berhitung TK',  220_000, 8),
    ('Berhitung Asyik TK',    'Berhitung TK',  'Pengenalan angka dan operasi dasar', 220_000, 8),
]


class Command(BaseCommand):
    help = 'Populate the named demo cohort (5 new students) for client demo.'

    @transaction.atomic
    def handle(self, *args, **opts):
        random.seed(11)

        # ── 1. Update rafael + trista gmail addresses (do NOT touch passwords)
        self._update_named_emails()

        # ── 2. Locate Trista; bail if create_test_users hasn't run
        trista_user = User.objects.filter(username='candrarinitristaharidewati').first()
        if not trista_user:
            self.stderr.write(
                'User "candrarinitristaharidewati" missing. '
                'Run create_test_users + populate_trista first.'
            )
            return
        trista = trista_user.teacher_profile

        # ── 3. Setup shared structures
        period = self._ensure_period()
        cat_mate = self._ensure_category('Matematika', 'Mata pelajaran matematika & turunannya')
        cat_tk = self._ensure_category('Calistung & TK', 'Materi untuk jenjang TK')

        # ── 4. Make sure Trista has a 2nd SD and 2nd SMP class
        extra_trista_kelases = self._ensure_extra_trista_classes(trista, period, cat_mate)

        # ── 5. Create the TK teacher + 2 TK classes
        tk_teacher = self._ensure_tk_teacher()
        tk_kelases = self._ensure_tk_classes(tk_teacher, period, cat_tk)

        # ── 6. Upsert the 5 demo students (idempotent)
        for spec in DEMO_STUDENTS:
            self._upsert_student(spec)

        # ── 7. Per-student full data
        results = {}
        for spec in DEMO_STUDENTS:
            user = User.objects.get(username=spec['username'])
            kelases = self._pick_kelases_for(spec['level'], trista, extra_trista_kelases, tk_kelases)
            if len(kelases) < 2:
                self.stderr.write(
                    f'  ! Not enough kelases for {user.username} ({spec["level"]}); '
                    f'got {len(kelases)}'
                )
                continue
            r = self._populate_student(user, kelases[:2])
            results[user.username] = r

        # ── 7b. Feature demos (multi-jenjang + Paket Ganjil Genap)
        feature_demo = self._populate_feature_demo_classes(trista, period)

        # ── 7c. Batch-lifecycle demos (one PRIVAT / GROUP / GG in mixed states)
        feature_demo['batch_lifecycle'] = self._populate_batch_lifecycle_demos(
            trista, period,
        )

        # ── 8. Confirm rafael's data (already populated by populate_rafael)
        rafael = User.objects.filter(username='rafaeladhikabagasalfathan').first()
        rafael_summary = self._rafael_check(rafael) if rafael else None

        # ── 9. Cache busting + summary
        cache.delete('top_teachers_dashboard')
        self._print_summary(results, rafael_summary, feature_demo)

    # ─── Feature demos: multi-jenjang + Paket Ganjil Genap ──────────────────

    def _populate_feature_demo_classes(self, trista, period):
        """Create two showcase classes and seat the demo students.

        1) MULTI-JENJANG: Trista runs "Matematika Lintas SD-SMP" - one weekly
           slot accepting BOTH SD and SMP students. gracia (SD) + dianfera
           (SMP) both enrolled.
        2) PAKET GANJIL GENAP: Trista runs "Matematika SMA Paket Ganjil-Genap"
           - bimdarmawa gets the ganjil seat, yohanes the genap seat.

        Idempotent: re-running won't duplicate the kelas, the schedule, the
        enrollments, or the parity bookings.
        """
        from academics.models import KelasJenjang  # noqa: F401 (sanity)

        results = {'multi_jenjang': None, 'ganjil_genap': None}
        cat = self._ensure_category('Matematika', 'Mata pelajaran matematika.')

        # 1) Multi-jenjang class
        # Idempotency keyed on (teacher_profile, name) - NOT academic_period.
        # cleanup_demo can collapse active periods between runs, which would
        # otherwise let a second copy of this kelas slip past the lookup.
        multi_name = 'Matematika Lintas SD-SMP'
        multi = Kelas.objects.filter(
            teacher_profile=trista, name=multi_name, is_deleted=False,
        ).order_by('id').first()
        if not multi:
            subj = self._ensure_subject(
                'Matematika Lintas', 'Lintas jenjang SD-SMP', cat,
            )
            today = date.today()
            multi = Kelas.objects.create(
                teacher_profile=trista,
                subject=subj,
                academic_period=period,
                name=multi_name,
                description='Kelas lintas jenjang SD-SMP oleh Bu Trista.',
                level=Level.SD,
                class_type=KelasType.GROUP,
                start_date=today - timedelta(days=14),
                end_date=today + timedelta(days=7 * 7),
                capacity=10,
                total_sessions=8,
                price=Decimal('300000'),
                status=KelasStatus.OPEN,
            )
            Schedule.objects.create(
                kelas=multi, day='THURSDAY',
                start_time=time(16, 0), end_time=time(17, 30),
            )
            self.stdout.write(f'  + multi-jenjang class created: {multi.name}')
        multi.set_jenjang([Level.SD, Level.SMP])
        generate_sessions_for_kelas(multi)

        gracia = User.objects.filter(username='gracia').first()
        dianfera = User.objects.filter(username='dianfera').first()
        if gracia and dianfera:
            for student in (gracia, dianfera):
                enr, _ = Enrollment.objects.get_or_create(
                    student_profile=student.student_profile,
                    kelas=multi,
                    defaults={
                        'status': EnrollmentStatus.ACTIVE,
                        'price_at_enrollment': multi.price,
                    },
                )
                if enr.status != EnrollmentStatus.ACTIVE:
                    enr.status = EnrollmentStatus.ACTIVE
                    enr.save(update_fields=['status', 'updated_at'])
                # AUTO booking fanout for REGULAR class
                from sessions_app.views import _auto_book_regular_sessions
                _auto_book_regular_sessions(enr)
            results['multi_jenjang'] = {
                'kelas': multi.name,
                'jenjang': multi.get_jenjang_display(),
                'students': [gracia.username, dianfera.username],
            }

        # 2) Paket Ganjil Genap class - same idempotency keying as above.
        gg_name = 'Matematika SMA Paket Ganjil-Genap'
        gg = Kelas.objects.filter(
            teacher_profile=trista, name=gg_name, is_deleted=False,
        ).order_by('id').first()
        if not gg:
            subj = self._ensure_subject(
                'Matematika Paket SMA', 'Paket khusus dua siswa', cat,
            )
            today = date.today()
            gg = Kelas.objects.create(
                teacher_profile=trista,
                subject=subj,
                academic_period=period,
                name=gg_name,
                description='Kelas paket dua siswa, satu kursi ganjil + satu kursi genap.',
                level=Level.SMA,
                class_type=KelasType.GANJIL_GENAP,
                start_date=today - timedelta(days=14),
                end_date=today + timedelta(days=7 * 7),
                capacity=2,
                total_sessions=8,
                price=Decimal('600000'),
                status=KelasStatus.OPEN,
            )
            Schedule.objects.create(
                kelas=gg, day='FRIDAY',
                start_time=time(17, 0), end_time=time(19, 0),
            )
            self.stdout.write(f'  + Paket Ganjil-Genap class created: {gg.name}')
        gg.set_jenjang([Level.SMA])
        # Force capacity to 2 in case a re-run touched it.
        if gg.capacity != 2:
            gg.capacity = 2
            gg.save(update_fields=['capacity', 'updated_at'])
        generate_sessions_for_kelas(gg)

        bim = User.objects.filter(username='bimdarmawa').first()
        yohanes = User.objects.filter(username='yohanes').first()
        gg_summary = {'kelas': gg.name, 'jenjang': 'SMA', 'seats': []}
        if bim and yohanes:
            for student, want_seat in [(bim, SEAT_GANJIL), (yohanes, SEAT_GENAP)]:
                enr, _ = Enrollment.objects.get_or_create(
                    student_profile=student.student_profile,
                    kelas=gg,
                    defaults={
                        'status': EnrollmentStatus.ACTIVE,
                        'price_at_enrollment': gg.price,
                    },
                )
                if enr.status != EnrollmentStatus.ACTIVE:
                    enr.status = EnrollmentStatus.ACTIVE
                    enr.save(update_fields=['status', 'updated_at'])
                seat, _ = auto_book_parity_sessions(enr, seat=want_seat)
                gg_summary['seats'].append({
                    'student': student.username,
                    'seat': seat or '-',
                })
            results['ganjil_genap'] = gg_summary

        return results

    # ─── Batch-lifecycle demos (PRIVAT / GROUP / GANJIL_GENAP) ───────────────

    def _populate_batch_lifecycle_demos(self, trista, period):
        """Seed three demo kelas that show the batch lifecycle:
          - PRIVAT (Privat Demo) : OPEN, no batch anchored.
          - GROUP  (Grup Demo)   : batch mid-run, one student enrolled.
          - GG     (GG Demo)     : batch just-completed; the next browse will
                                   sweep the enrollments to COMPLETED and the
                                   slot becomes OPEN again.

        Idempotent: re-running normalizes state (won't double-seed enrollments
        or sessions).
        """
        from sessions_app.models import (
            BookingKind, BookingStatus, Session, SessionBooking, SessionStatus,
            SessionType,
        )

        results = {}
        cat = self._ensure_category('Matematika', 'Mata pelajaran matematika.')
        for lvl in (Level.SMA,):
            TeacherJenjang.objects.get_or_create(teacher_profile=trista, level=lvl)

        # 1) PRIVAT - OPEN
        privat_name = 'Matematika SMA Privat Demo'
        privat = Kelas.objects.filter(
            teacher_profile=trista, name=privat_name, is_deleted=False,
        ).first()
        if not privat:
            subj = self._ensure_subject(
                'Matematika Privat SMA', 'Kelas privat 1 siswa', cat,
            )
            today = date.today()
            privat = Kelas.objects.create(
                teacher_profile=trista, subject=subj,
                academic_period=period, name=privat_name,
                description='Demo kelas Privat - paket 4 pertemuan.',
                level=Level.SMA, class_type=KelasType.PRIVAT,
                start_date=today, end_date=today,
                capacity=1, total_sessions=4,
                price=Decimal('400000'), status=KelasStatus.OPEN,
            )
            privat.set_jenjang([Level.SMA])
            Schedule.objects.create(
                kelas=privat, day='TUESDAY',
                start_time=time(16, 0), end_time=time(17, 30),
            )
        results['privat'] = {'kelas': privat.name, 'state': 'OPEN (no batch anchored)'}

        # 2) GROUP - batch mid-run
        group_name = 'Matematika SMA Grup Demo'
        group = Kelas.objects.filter(
            teacher_profile=trista, name=group_name, is_deleted=False,
        ).first()
        if not group:
            subj = self._ensure_subject(
                'Matematika Grup SMA', 'Kelas grup demo', cat,
            )
            today = date.today()
            group = Kelas.objects.create(
                teacher_profile=trista, subject=subj,
                academic_period=period, name=group_name,
                description='Demo kelas Grup - paket 4 pertemuan, batch mid-run.',
                level=Level.SMA, class_type=KelasType.GROUP,
                start_date=today, end_date=today,
                capacity=6, total_sessions=4,
                price=Decimal('250000'), status=KelasStatus.OPEN,
            )
            group.set_jenjang([Level.SMA])
            Schedule.objects.create(
                kelas=group, day='WEDNESDAY',
                start_time=time(15, 30), end_time=time(17, 0),
            )
        # Anchor a mid-run batch: 4 weekly sessions starting 1 week ago.
        anchor_first = date.today() - timedelta(days=7)
        # Snap to that weekday so dates align with the slot.
        # (Wednesday = 2; if today's day-of-week is not aligned, just use
        # anchor_first as-is for demo purposes.)
        max_num = (
            Session.objects.filter(kelas=group)
            .aggregate(m=models.Max('session_number'))['m'] or 0
        )
        existing = Session.objects.filter(kelas=group).count()
        if existing < 4:
            for i in range(4 - existing):
                d = anchor_first + timedelta(days=7 * (existing + i))
                sess_num = max_num + i + 1
                Session.objects.get_or_create(
                    kelas=group, session_number=sess_num,
                    defaults={
                        'date': d,
                        'start_time': time(15, 30), 'end_time': time(17, 0),
                        'session_type': SessionType.REGULAR,
                        'status': SessionStatus.COMPLETED if d < date.today() else SessionStatus.SCHEDULED,
                        'capacity': group.capacity,
                    },
                )
        # Enroll bimdarmawa + create AUTO bookings for the batch sessions
        bim = User.objects.filter(username='bimdarmawa').first()
        if bim:
            enr, _ = Enrollment.objects.get_or_create(
                student_profile=bim.student_profile, kelas=group,
                defaults={
                    'status': EnrollmentStatus.ACTIVE,
                    'price_at_enrollment': group.price,
                },
            )
            if enr.status != EnrollmentStatus.ACTIVE:
                enr.status = EnrollmentStatus.ACTIVE
                enr.save(update_fields=['status', 'updated_at'])
            for s in Session.objects.filter(
                kelas=group, session_type=SessionType.REGULAR,
            ):
                SessionBooking.objects.get_or_create(
                    enrollment=enr, session=s,
                    defaults={
                        'status': BookingStatus.BOOKED,
                        'kind': BookingKind.AUTO,
                    },
                )
        results['group'] = {
            'kelas': group.name, 'state': 'batch mid-run (1 enrollee)',
        }

        # 3) GANJIL_GENAP - batch just-completed (window all in the past)
        gg_name_late = 'Matematika SMA GG Demo (selesai)'
        gg_late = Kelas.objects.filter(
            teacher_profile=trista, name=gg_name_late, is_deleted=False,
        ).first()
        if not gg_late:
            subj = self._ensure_subject(
                'Matematika GG Demo SMA', 'Demo GG yang sudah selesai', cat,
            )
            today = date.today()
            gg_late = Kelas.objects.create(
                teacher_profile=trista, subject=subj,
                academic_period=period, name=gg_name_late,
                description='Demo GG dengan batch yang baru selesai - akan reopen via sweep.',
                level=Level.SMA, class_type=KelasType.GANJIL_GENAP,
                start_date=today, end_date=today,
                capacity=2, total_sessions=2,  # window = 4 weeks
                price=Decimal('500000'), status=KelasStatus.OPEN,
            )
            gg_late.set_jenjang([Level.SMA])
            Schedule.objects.create(
                kelas=gg_late, day='THURSDAY',
                start_time=time(17, 0), end_time=time(18, 30),
            )
        # Anchor a finished batch: window = 4 weeks, anchor 6 weeks ago so the
        # final session is 1 week in the past. The dashboard sweep will then
        # auto-complete enrollments and the kelas reopens on next browse.
        anchor_first_late = date.today() - timedelta(days=7 * 5)
        existing_late = Session.objects.filter(kelas=gg_late).count()
        if existing_late < 4:
            max_num_late = (
                Session.objects.filter(kelas=gg_late)
                .aggregate(m=models.Max('session_number'))['m'] or 0
            )
            for i in range(4 - existing_late):
                d = anchor_first_late + timedelta(days=7 * (existing_late + i))
                sess_num = max_num_late + i + 1
                Session.objects.get_or_create(
                    kelas=gg_late, session_number=sess_num,
                    defaults={
                        'date': d,
                        'start_time': time(17, 0), 'end_time': time(18, 30),
                        'session_type': SessionType.REGULAR,
                        'status': SessionStatus.COMPLETED,
                        'capacity': gg_late.capacity,
                    },
                )
        # Enroll yohanes (kursi ganjil); book him on weeks 1, 3 of the window.
        yohanes = User.objects.filter(username='yohanes').first()
        if yohanes:
            enr, _ = Enrollment.objects.get_or_create(
                student_profile=yohanes.student_profile, kelas=gg_late,
                defaults={
                    'status': EnrollmentStatus.ACTIVE,
                    'price_at_enrollment': gg_late.price,
                },
            )
            if enr.status != EnrollmentStatus.ACTIVE:
                enr.status = EnrollmentStatus.ACTIVE
                enr.save(update_fields=['status', 'updated_at'])
            sessions_late = list(
                Session.objects.filter(
                    kelas=gg_late, session_type=SessionType.REGULAR,
                ).order_by('date')
            )
            # Ganjil = sessions on weeks 1, 3, ... (offset day // 7 even)
            first_date = sessions_late[0].date if sessions_late else None
            if first_date:
                for s in sessions_late:
                    week_index = (s.date - first_date).days // 7
                    if week_index % 2 == 0:  # ganjil
                        SessionBooking.objects.get_or_create(
                            enrollment=enr, session=s,
                            defaults={
                                'status': BookingStatus.BOOKED,
                                'kind': BookingKind.AUTO,
                            },
                        )
        results['ganjil_genap_late'] = {
            'kelas': gg_late.name,
            'state': 'batch just-completed (next browse will sweep + reopen)',
        }

        return results

    # ─── Email refresh for rafael + trista ───────────────────────────────────

    def _update_named_emails(self):
        """Update only the email field for rafael + trista. Password untouched."""
        targets = [
            ('rafaeladhikabagasalfathan', 'rafaeladhikabagasalfathan@gmail.com'),
            ('candrarinitristaharidewati', 'candrarinitristaharidewati@gmail.com'),
        ]
        for username, new_email in targets:
            u = User.objects.filter(username=username).first()
            if u and u.email != new_email:
                u.email = new_email
                u.save(update_fields=['email', 'updated_at'])
                self.stdout.write(f'  [UPD] {username} email -> {new_email}')

    # ─── Shared setup helpers ───────────────────────────────────────────────

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

    def _ensure_category(self, name, desc):
        cat, _ = Category.objects.get_or_create(
            name=name,
            defaults={'description': desc, 'is_active': True},
        )
        return cat

    def _ensure_subject(self, name, desc, category):
        subj, _ = Subject.objects.get_or_create(
            name=name,
            defaults={'category': category, 'description': desc, 'is_active': True},
        )
        return subj

    # ─── Extra Trista classes (2nd SD + 2nd SMP) ────────────────────────────

    def _ensure_extra_trista_classes(self, teacher, period, category):
        """Return a dict {level: [kelas, ...]} for the extra SD + SMP classes."""
        out = {'SD': [], 'SMP': []}
        today = date.today()
        start = today - timedelta(days=30)
        end = today + timedelta(days=60)

        # Make sure Trista has the jenjang for each level
        for lvl in (Level.SD, Level.SMP):
            TeacherJenjang.objects.get_or_create(teacher_profile=teacher, level=lvl)

        for kname, sname, sdesc, level, price, total in EXTRA_TRISTA_CLASSES:
            subj = self._ensure_subject(sname, sdesc, category)
            kelas = Kelas.objects.filter(
                name=kname, level=level, academic_period=period, is_deleted=False,
            ).first()
            if not kelas:
                kelas = Kelas.objects.create(
                    name=kname,
                    subject=subj,
                    teacher_profile=teacher,
                    academic_period=period,
                    level=level,
                    capacity=18,
                    total_sessions=total,
                    start_date=start,
                    end_date=end,
                    status=KelasStatus.OPEN,
                    price=Decimal(str(price)),
                    description=f'Kelas {kname} oleh Bu Trista.',
                )
                # One mid-week schedule slot
                day = random.choice(['MONDAY', 'WEDNESDAY', 'FRIDAY'])
                sh = random.choice([15, 16, 17])
                Schedule.objects.create(
                    kelas=kelas,
                    day=day,
                    start_time=time(sh, 0),
                    end_time=time(sh + 2, 0),
                )
                self.stdout.write(f'  + class created: {kelas.name}')
            else:
                # Keep open-status invariant in case auto-close has touched it
                changed = []
                if kelas.end_date < today + timedelta(days=14):
                    kelas.end_date = end
                    changed.append('end_date')
                if kelas.status != KelasStatus.OPEN:
                    kelas.status = KelasStatus.OPEN
                    changed.append('status')
                if changed:
                    kelas.save(update_fields=changed + ['updated_at'])
            out[level].append(kelas)
        return out

    # ─── TK teacher + classes ───────────────────────────────────────────────

    def _ensure_tk_teacher(self):
        """Create or fetch a dedicated TK teacher: 'Guru TK Demo'."""
        username = 'gurutkdemo'
        user = User.objects.filter(username=username).first()
        if not user:
            user = User.objects.create_user(
                username=username,
                email='gurutkdemo@glowmathclass.com',
                first_name='Sri',
                last_name='Wahyuni',
                role=Role.TEACHER,
                approval_status=ApprovalStatus.APPROVED,
                is_active=True,
                phone='0811' + '12345678',
            )
            user.set_password(PASSWORD)
            user.save()
            self.stdout.write(f'  + TK teacher created: {username}')
        # Profile + jenjang
        profile, _ = TeacherProfile.objects.get_or_create(user=user)
        changed = False
        if not profile.specialization:
            profile.specialization = 'TK & Calistung'
            changed = True
        if not profile.education:
            profile.education = Education.S1
            changed = True
        if not profile.bio:
            profile.bio = 'Guru TK berpengalaman, fokus pada Calistung & motorik halus.'
            changed = True
        if profile.experience_years in (None, 0):
            profile.experience_years = 8
            changed = True
        if changed:
            profile.save()
        TeacherJenjang.objects.get_or_create(teacher_profile=profile, level=Level.TK)
        return profile

    def _ensure_tk_classes(self, teacher, period, category):
        today = date.today()
        start = today - timedelta(days=30)
        end = today + timedelta(days=60)
        out = []
        for kname, sname, sdesc, price, total in TK_CLASSES:
            subj = self._ensure_subject(sname, sdesc, category)
            kelas = Kelas.objects.filter(
                name=kname, level=Level.TK, academic_period=period, is_deleted=False,
            ).first()
            if not kelas:
                kelas = Kelas.objects.create(
                    name=kname,
                    subject=subj,
                    teacher_profile=teacher,
                    academic_period=period,
                    level=Level.TK,
                    capacity=12,
                    total_sessions=total,
                    start_date=start,
                    end_date=end,
                    status=KelasStatus.OPEN,
                    price=Decimal(str(price)),
                    description=f'Kelas {kname} untuk siswa TK.',
                )
                day = random.choice(['TUESDAY', 'THURSDAY', 'SATURDAY'])
                sh = random.choice([8, 9, 10])
                Schedule.objects.create(
                    kelas=kelas,
                    day=day,
                    start_time=time(sh, 0),
                    end_time=time(sh + 1, 30),
                )
                self.stdout.write(f'  + TK class created: {kelas.name}')
            else:
                changed = []
                if kelas.end_date < today + timedelta(days=14):
                    kelas.end_date = end
                    changed.append('end_date')
                if kelas.status != KelasStatus.OPEN:
                    kelas.status = KelasStatus.OPEN
                    changed.append('status')
                if changed:
                    kelas.save(update_fields=changed + ['updated_at'])
            out.append(kelas)
        return out

    # ─── Student upsert ─────────────────────────────────────────────────────

    def _upsert_student(self, spec):
        u = User.objects.filter(username=spec['username']).first()
        if not u:
            u = User.objects.create_user(
                username=spec['username'],
                email=spec['email'],
                first_name=spec['first'],
                last_name=spec['last'],
                role=Role.STUDENT,
                approval_status=ApprovalStatus.APPROVED,
                is_active=True,
                phone=spec['phone'],
            )
            u.set_password(PASSWORD)
            u.save()
            self.stdout.write(f'  + student created: {spec["username"]}')
        else:
            # Email / phone may have changed; refresh non-credential fields only
            dirty = []
            if u.email != spec['email']:
                u.email = spec['email']
                dirty.append('email')
            if u.phone != spec['phone']:
                u.phone = spec['phone']
                dirty.append('phone')
            if u.approval_status != ApprovalStatus.APPROVED:
                u.approval_status = ApprovalStatus.APPROVED
                dirty.append('approval_status')
            if not u.is_active:
                u.is_active = True
                dirty.append('is_active')
            if dirty:
                u.save(update_fields=dirty + ['updated_at'])

        # Profile (signal creates an empty one when role=STUDENT)
        profile, _ = StudentProfile.objects.get_or_create(user=u)
        profile.level = spec['level']
        profile.school_name = spec['school']
        profile.school_grade = spec['grade']
        profile.gender = spec['gender']
        profile.parent_name = spec['parent_name']
        profile.parent_phone = spec['parent_phone']
        profile.address = (
            spec['address'] + ('  ' + spec['note'] if spec.get('note') else '')
        )
        # Date of birth — derive from level + grade so the age looks right
        today = date.today()
        base_age = AGE_BY_LEVEL[spec['level']]
        if spec['level'] == Level.SD:
            age = base_age + (spec['grade'] - 1)        # grade 1 ≈ 7yo
        elif spec['level'] == Level.SMP:
            age = base_age + (spec['grade'] - 7)        # grade 7 ≈ 12yo
        elif spec['level'] == Level.SMA:
            age = base_age + (spec['grade'] - 10)       # grade 10 ≈ 15yo
        else:
            age = base_age
        profile.date_of_birth = today.replace(year=today.year - age)
        profile.save()

    # ─── Kelas picker per jenjang ───────────────────────────────────────────

    def _pick_kelases_for(self, level, trista, extra_trista, tk_kelases):
        """Return at least 2 kelases the student can enroll in (same level)."""
        if level == Level.SMA:
            return list(
                Kelas.objects.filter(
                    teacher_profile=trista, level=Level.SMA, is_deleted=False,
                ).order_by('name')[:2]
            )
        if level == Level.SMP:
            # 1 from populate_trista (Aljabar SMP - Pemantapan) + 1 from extras
            base = list(
                Kelas.objects.filter(
                    teacher_profile=trista, level=Level.SMP, is_deleted=False,
                ).order_by('name')
            )
            return base[:2]
        if level == Level.SD:
            base = list(
                Kelas.objects.filter(
                    teacher_profile=trista, level=Level.SD, is_deleted=False,
                ).order_by('name')
            )
            return base[:2]
        if level == Level.TK:
            return tk_kelases[:2]
        # UMUM (not used here — rafael handled by populate_rafael)
        return []

    # ─── Full per-student populate (sessions / attendance / grades / etc.) ──

    def _populate_student(self, user, kelases):
        """Create 2 enrollments (1 COMPLETED + 1 ACTIVE), back-fill data."""
        profile = user.student_profile

        # First, ensure each kelas has its weekly sessions generated. We
        # delegate to the generator (one source of truth) rather than looping
        # per-week inline. Idempotent so re-running this command is safe.
        sess_n = 0
        for k in kelases:
            sess_n += generate_sessions_for_kelas(k)

        # Now enroll: first kelas COMPLETED, second ACTIVE.
        enr_completed = self._upsert_enrollment(profile, kelases[0], EnrollmentStatus.COMPLETED)
        enr_active = self._upsert_enrollment(profile, kelases[1], EnrollmentStatus.ACTIVE)

        # Mark attendance on PAST sessions for each enrollment.
        att_n = 0
        for enr in (enr_completed, enr_active):
            att_n += self._mark_attendance(enr)

        grades_n = sum(self._create_grades_for(enr) for enr in (enr_completed, enr_active))

        journals_n = sum(self._create_journal_for(enr) for enr in (enr_completed, enr_active))

        ratings = self._create_ratings_for(enr_completed)

        notif_n = self._create_notifications(user)

        return {
            'enrollments': 2,
            'completed': 1,
            'active': 1,
            'sessions_added': sess_n,
            'attendance_added': att_n,
            'grades_added': grades_n,
            'journals_added': journals_n,
            'rating_added': sum(ratings.values()),
        }

    def _upsert_enrollment(self, profile, kelas, status):
        enr, created = Enrollment.objects.get_or_create(
            student_profile=profile,
            kelas=kelas,
            defaults={'status': status, 'price_at_enrollment': kelas.price},
        )
        if not created and enr.status != status:
            enr.status = status
            enr.save(update_fields=['status', 'updated_at'])
        return enr

    def _mark_attendance(self, enr):
        """Back-fill Attendance for past COMPLETED sessions of this enrollment.

        Sessions themselves come from generate_sessions_for_kelas(), called
        once per kelas in _populate_student. This method only marks Attendance
        rows for sessions that are already COMPLETED (date < today).
        """
        if enr.status == EnrollmentStatus.DROPPED:
            return 0
        att_added = 0
        completed_sessions = Session.objects.filter(
            kelas=enr.kelas,
            status=SessionStatus.COMPLETED,
            session_type=SessionType.REGULAR,
        )
        for session in completed_sessions:
            att_status = random.choices(
                [
                    AttendanceStatus.PRESENT,
                    AttendanceStatus.PERMITTED,
                    AttendanceStatus.ABSENT,
                ],
                weights=[75, 15, 10],
            )[0]
            _, att_created = Attendance.objects.get_or_create(
                enrollment=enr, session=session,
                defaults={
                    'status': att_status,
                    'marked_by': enr.kelas.teacher_profile.user,
                },
            )
            if att_created:
                att_added += 1
        return att_added

    def _create_grades_for(self, enr):
        if enr.status == EnrollmentStatus.DROPPED:
            return 0
        target = 5  # 1 MIDTERM, 1 FINAL, 2 QUIZ, 1 ASSIGNMENT
        existing = Grade.objects.filter(enrollment=enr).count()
        if existing >= target:
            return 0
        completed_sessions = list(
            Session.objects.filter(kelas=enr.kelas, status=SessionStatus.COMPLETED)
        )
        recipe = [
            (GradeType.MIDTERM, None),
            (GradeType.FINAL, None),
            (GradeType.QUIZ, 'session'),
            (GradeType.QUIZ, 'session'),
            (GradeType.ASSIGNMENT, 'session'),
        ]
        added = 0
        for gtype, needs_sess in recipe[existing:]:
            session = None
            if needs_sess:
                if not completed_sessions:
                    # No completed sessions yet — fall back to MIDTERM (no FK required)
                    gtype = GradeType.MIDTERM
                else:
                    session = random.choice(completed_sessions)
            score = round(random.choices(
                [random.randint(60, 75), random.randint(76, 90), random.randint(91, 100)],
                weights=[20, 60, 20],
            )[0])
            Grade.objects.create(
                enrollment=enr,
                session=session,
                grade_type=gtype,
                score=Decimal(score),
                notes=f'{gtype.label} demo populate',
                graded_by_teacher=enr.kelas.teacher_profile,
            )
            added += 1
        return added

    def _create_journal_for(self, enr):
        if enr.status == EnrollmentStatus.DROPPED:
            return 0
        # Use last month so we don't collide with populate_rafael (which also uses last month)
        first_of_month = date.today().replace(day=1)
        last_month_end = first_of_month - timedelta(days=1)
        m, y = last_month_end.month, last_month_end.year
        subject = enr.kelas.subject.name
        student_first = enr.student_profile.user.first_name or 'Siswa'
        _, created = MonthlyJournal.objects.get_or_create(
            enrollment=enr, month=m, year=y,
            defaults={
                'written_by_teacher': enr.kelas.teacher_profile,
                'summary': (
                    f'{student_first} menunjukkan progress yang baik pada {subject}. '
                    f'Aktif bertanya dan rajin mengerjakan latihan. '
                    f'Perlu dorongan kecil untuk topik aplikasi yang lebih kompleks.'
                ),
                'topics_covered': f'Bab 1-3 {subject}, latihan soal terstruktur, diskusi grup.',
                'strengths': 'Aktif, rasa ingin tahu tinggi, kemampuan dasar baik.',
                'areas_for_improvement': (
                    'Manajemen waktu saat mengerjakan soal panjang, '
                    'memperhatikan ketelitian langkah-langkah perhitungan.'
                ),
                'published_at': timezone.now(),
            },
        )
        return 1 if created else 0

    def _create_ratings_for(self, enr):
        """Only valid on COMPLETED enrollments per rating rules."""
        if enr.status != EnrollmentStatus.COMPLETED:
            return {'teacher': 0, 'class': 0}
        _, t_created = TeacherRating.objects.get_or_create(
            enrollment=enr,
            defaults={
                'teacher_profile': enr.kelas.teacher_profile,
                'score': random.choices([4, 5], weights=[30, 70])[0],
                'comment': 'Cara mengajarnya jelas, sabar, dan menyenangkan. Recommended!',
            },
        )
        _, c_created = ClassRating.objects.get_or_create(
            enrollment=enr,
            defaults={
                'kelas': enr.kelas,
                'score': random.choices([4, 5], weights=[30, 70])[0],
                'comment': 'Materinya runut, latihannya pas, banyak ilmu baru.',
            },
        )
        return {'teacher': int(t_created), 'class': int(c_created)}

    def _create_notifications(self, user):
        rows = [
            (NotificationType.ENROLLMENT,   'Pendaftaran berhasil',
             'Akun demo kamu sudah aktif dan terdaftar ke kelas pertama.', True),
            (NotificationType.SESSION,      'Jadwal sesi minggu ini',
             'Ada sesi terjadwal minggu ini, jangan lupa hadir tepat waktu.', False),
            (NotificationType.GRADE,        'Nilai baru tersedia',
             'Quiz terbaru kamu sudah dinilai — cek di menu Nilai.', False),
            (NotificationType.ANNOUNCEMENT, 'Pengumuman dari Bimbel',
             'Selamat datang di GlowMath Course! Cek pengumuman terbaru.', True),
        ]
        added = 0
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
                added += 1
        return added

    # ─── Rafael verification (already populated by populate_rafael) ─────────

    def _rafael_check(self, user):
        enrs = Enrollment.objects.filter(student_profile__user=user)
        return {
            'enrollments': enrs.count(),
            'has_grades': Grade.objects.filter(enrollment__in=enrs).exists(),
            'has_journal': MonthlyJournal.objects.filter(enrollment__in=enrs).exists(),
            'has_rating': (
                TeacherRating.objects.filter(enrollment__in=enrs).exists()
                or ClassRating.objects.filter(enrollment__in=enrs).exists()
            ),
        }

    # ─── Summary ────────────────────────────────────────────────────────────

    def _print_summary(self, results, rafael_summary, feature_demo=None):
        self.stdout.write(self.style.SUCCESS('\n=== DEMO POPULATE SUMMARY ==='))
        for spec in DEMO_STUDENTS:
            u = spec['username']
            r = results.get(u, {})
            self.stdout.write(
                f'  {u:14s} ({spec["level"]:4s}) -> '
                f'enr={r.get("enrollments", 0)} (1 COMPLETED + 1 ACTIVE), '
                f'+sessions={r.get("sessions_added", 0)}, '
                f'+att={r.get("attendance_added", 0)}, '
                f'+grades={r.get("grades_added", 0)}, '
                f'+journals={r.get("journals_added", 0)}, '
                f'+ratings={r.get("rating_added", 0)}'
            )
        if rafael_summary:
            self.stdout.write('')
            self.stdout.write(
                f'  rafaeladhikabagasalfathan (UMUM) -> enrollments={rafael_summary["enrollments"]}, '
                f'has_grades={rafael_summary["has_grades"]}, '
                f'has_journal={rafael_summary["has_journal"]}, '
                f'has_rating={rafael_summary["has_rating"]}'
            )
        if feature_demo:
            self.stdout.write(self.style.SUCCESS('\n=== FEATURE DEMOS ==='))
            mj = feature_demo.get('multi_jenjang')
            if mj:
                self.stdout.write(
                    f'  Multi-jenjang: "{mj["kelas"]}" jenjang={mj["jenjang"]}, '
                    f'siswa: {", ".join(mj["students"])}'
                )
            gg = feature_demo.get('ganjil_genap')
            if gg:
                self.stdout.write(f'  Paket Ganjil-Genap: "{gg["kelas"]}" (kapasitas 2)')
                for s in gg['seats']:
                    self.stdout.write(f'    - {s["student"]:14s} -> kursi {s["seat"]}')
        self.stdout.write(self.style.SUCCESS('\nDemo logins (password: ikanbuvivid):'))
        self.stdout.write('  Siswa:')
        self.stdout.write('    rafaeladhikabagasalfathan@gmail.com  (UMUM)')
        self.stdout.write('    bimdarmawa@gmail.com                  (SMA)')
        self.stdout.write('    yohanes@gmail.com                     (SMK / level SMA)')
        self.stdout.write('    dianfera@gmail.com                    (SMP)')
        self.stdout.write('    gracia@gmail.com                      (SD)')
        self.stdout.write('    azriel@gmail.com                      (TK)')
        self.stdout.write('  Guru:')
        self.stdout.write('    candrarinitristaharidewati@gmail.com')
        self.stdout.write('\nServer: python manage.py runserver 8765')
