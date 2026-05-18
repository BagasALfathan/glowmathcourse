"""Stress test enrollment race-condition safety.

Spawns N concurrent threads that all try to enroll into the same Kelas.
Verifies that no more enrollments than `kelas.capacity` succeed.

Usage:
    python manage.py stress_test_enroll
    python manage.py stress_test_enroll --threads 30 --capacity 3
"""
import threading
import time
import traceback

from django.core.management.base import BaseCommand
from django.db import OperationalError, connections
from django.utils import timezone

from academics.models import AcademicPeriod, Category, Kelas, KelasStatus, PeriodType, Schedule, Subject
from accounts.models import ApprovalStatus, Level, Role, StudentProfile, TeacherProfile, User
from enrollments.models import Enrollment, EnrollmentStatus
from enrollments.views import _try_enroll


class Command(BaseCommand):
    help = "Stress test enrollment race condition (capacity overflow safety)."

    def add_arguments(self, parser):
        parser.add_argument('--threads', type=int, default=20,
                            help='Number of concurrent enroll attempts (default: 20)')
        parser.add_argument('--capacity', type=int, default=3,
                            help='Kelas capacity for the test (default: 3)')
        parser.add_argument('--level', type=str, default='SD',
                            help='Level for kelas + students (default: SD)')

    def handle(self, *args, **opts):
        n_threads = opts['threads']
        capacity = opts['capacity']
        level = opts['level']

        if level not in Level.values:
            self.stderr.write(self.style.ERROR(f'Invalid level: {level}'))
            return

        self.stdout.write(f'\n=== Enrollment stress test ===')
        self.stdout.write(f'Threads: {n_threads}, capacity: {capacity}, level: {level}')

        kelas = self._get_or_create_test_kelas(capacity=capacity, level=level)
        students = self._get_or_create_test_students(n=n_threads, level=level)

        if len(students) < n_threads:
            self.stderr.write(self.style.ERROR(
                f'Only {len(students)} approved {level} students exist, '
                f'need {n_threads}. Run `create_test_users` or `generate_dummy_data` first.'
            ))
            return

        # Reset kelas to clean state for this run
        Enrollment.objects.filter(kelas=kelas).delete()
        kelas.status = KelasStatus.OPEN
        kelas.save(update_fields=['status', 'updated_at'])

        self.stdout.write(f'\nKelas: "{kelas.name}" (id={kelas.pk}, capacity={kelas.capacity})')
        self.stdout.write(f'Students staged: {len(students)}')

        # Run concurrent enrollment attempts
        results = []
        results_lock = threading.Lock()

        def worker(student_profile):
            # SQLite serializes writes via a process-wide writer lock; threads that
            # collide get "database is locked". Retry with small backoff so the
            # stress test exercises the logical guard, not the SQLite quirk.
            # (Postgres in prod uses real row-level locks via select_for_update.)
            attempts = 0
            try:
                while True:
                    attempts += 1
                    try:
                        outcome, _payload = _try_enroll(student_profile, kelas)
                        with results_lock:
                            results.append((outcome, student_profile.pk))
                        return
                    except OperationalError as e:
                        if 'locked' in str(e).lower() and attempts < 20:
                            time.sleep(0.01 * attempts)
                            continue
                        with results_lock:
                            results.append(('err', f'{student_profile.pk}: {e}'))
                        return
                    except Exception as e:
                        with results_lock:
                            results.append(('err', f'{student_profile.pk}: {e}'))
                        traceback.print_exc()
                        return
            finally:
                connections.close_all()

        threads = [threading.Thread(target=worker, args=(s,)) for s in students[:n_threads]]
        t0 = time.perf_counter()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = time.perf_counter() - t0

        # Tally
        ok_count = sum(1 for r in results if r[0] == 'ok')
        full_count = sum(1 for r in results if r[0] == 'full')
        already_count = sum(1 for r in results if r[0] == 'already')
        completed_count = sum(1 for r in results if r[0] == 'completed')
        closed_count = sum(1 for r in results if r[0] == 'closed')
        err_count = sum(1 for r in results if r[0] == 'err')

        # Fresh DB count to verify
        active_db = Enrollment.objects.filter(
            kelas=kelas, status=EnrollmentStatus.ACTIVE, is_deleted=False
        ).count()

        self.stdout.write(f'\n--- Results ({elapsed*1000:.0f} ms) ---')
        self.stdout.write(f'  ok:        {ok_count}')
        self.stdout.write(f'  full:      {full_count}')
        self.stdout.write(f'  already:   {already_count}')
        self.stdout.write(f'  completed: {completed_count}')
        self.stdout.write(f'  closed:    {closed_count}')
        self.stdout.write(f'  err:       {err_count}')
        self.stdout.write(f'  DB active enrollments: {active_db}')
        kelas.refresh_from_db()
        self.stdout.write(f'  Kelas status after:    {kelas.status}')

        # Pass conditions:
        #   1. No overflow:        active_db <= capacity
        #   2. Tally matches DB:   ok_count == active_db
        #   3. Refusals account for the rest
        refused = full_count + already_count + completed_count + closed_count
        if active_db <= capacity and ok_count == active_db and (ok_count + refused + err_count) == n_threads and err_count == 0:
            self.stdout.write(self.style.SUCCESS(
                f'\n[OK] PASS - {active_db} enrolled, {refused} refused, no overflow ({active_db} <= {capacity})'
            ))
        else:
            self.stdout.write(self.style.ERROR(
                f'\n[FAIL] FAIL - active={active_db}, ok={ok_count}, capacity={capacity}, '
                f'refused={refused}, err={err_count}, threads={n_threads}'
            ))

    # ── Fixtures ───────────────────────────────────────────────────────────────

    def _get_or_create_test_kelas(self, capacity, level):
        """Idempotent: return the stress-test kelas, creating prerequisites as needed."""
        teacher_profile = (
            TeacherProfile.objects
            .filter(user__role=Role.TEACHER, user__approval_status=ApprovalStatus.APPROVED, user__is_deleted=False)
            .first()
        )
        if not teacher_profile:
            raise RuntimeError('No approved teacher found. Run `create_test_users` first.')

        category, _ = Category.objects.get_or_create(name='Stress Test')
        subject, _ = Subject.objects.get_or_create(
            name='Stress Test Subject',
            defaults={'category': category},
        )
        today = timezone.localdate()
        period, _ = AcademicPeriod.objects.get_or_create(
            name='Stress Test Period',
            defaults={
                'year': str(today.year),
                'period_type': PeriodType.QUARTER,
                'quarter': 'Q1',
                'start_date': today,
                'end_date': today.replace(year=today.year + 1),
                'is_active': True,
            },
        )

        kelas, created = Kelas.objects.get_or_create(
            name=f'Stress Test Kelas ({level})',
            defaults={
                'teacher_profile': teacher_profile,
                'subject': subject,
                'academic_period': period,
                'level': level,
                'start_date': today.replace(year=today.year + 1),  # future-dated so enroll isn't blocked by start_date
                'end_date': today.replace(year=today.year + 2),
                'capacity': capacity,
                'total_sessions': 12,
                'price': 0,
                'status': KelasStatus.OPEN,
            },
        )
        # Force-correct capacity + dates + status if reused
        kelas.capacity = capacity
        kelas.level = level
        kelas.start_date = today.replace(year=today.year + 1)
        kelas.end_date = today.replace(year=today.year + 2)
        kelas.status = KelasStatus.OPEN
        kelas.is_deleted = False
        kelas.deleted_at = None
        kelas.save()

        # Ensure a schedule exists (so the kelas appears on the schedule grid and
        # the schedule-conflict path is exercised)
        if not kelas.schedules.exists():
            from datetime import time as _time
            Schedule.objects.create(
                kelas=kelas, day='MONDAY',
                start_time=_time(7, 0), end_time=_time(8, 0), room='STRESS-1',
            )
        return kelas

    def _get_or_create_test_students(self, n, level):
        """Return up to `n` approved StudentProfile rows matching the level."""
        qs = (
            StudentProfile.objects
            .filter(
                user__role=Role.STUDENT,
                user__approval_status=ApprovalStatus.APPROVED,
                user__is_deleted=False,
                level=level,
            )
            .select_related('user')
            .order_by('user_id')
        )
        return list(qs[:n])
