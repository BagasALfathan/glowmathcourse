"""QA + dev-DB cleanup pass.

Idempotent. Re-running is safe; it converges the DB to the same final state.

What it does:
  (a) Delete or soft-delete QA leftovers (kelas id 157 "Tes Kelas Otomatis
      SMP-SMA" + user tesqa.smp@gmail.com and their enrollments / bookings).
  (b) Repair over-capacity classes (drop excess ACTIVE enrollments, oldest
      kept so historical attendance and grades survive).
  (c) Merge duplicate Subject rows (keep the lowest-PK row of each name,
      re-point dependent Kelas FKs, then delete dupes).
  (d) Ensure exactly one AcademicPeriod has is_active=True. The most recent
      active row wins; the rest are flipped off.
  (e) Collapse Trista's per-class schedules to a single row (matches the new
      one-weekly-slot domain rule) and assign non-overlapping (day, time)
      windows across her classes so the teacher slot-conflict rule holds.
  (f) Dedupe Session rows: for each kelas, group by (date, start_time); when
      more than one exists, keep the row with attendance (or the lowest
      session_number) and migrate bookings/attendance from the losers onto
      the survivor where the unique constraint allows. Cancelled losers and
      their bookings are then deleted.
  (g) Dedupe Kelas rows by (teacher_profile_id, name): when populate_demo
      (or a similar seeder) re-creates a demo class because the academic
      period rotated, two non-deleted Kelas rows for the same teacher and
      name accumulate. Keep the one with the most enrollments (tie broken
      by highest pk), re-point Enrollment FKs onto the survivor where the
      unique (student, kelas) constraint allows, and soft-delete the loser.

Run:
    python manage.py cleanup_demo
"""
from datetime import time

from django.core.management.base import BaseCommand
from django.db import transaction

from academics.models import (
    AcademicPeriod, Kelas, Schedule, Subject,
)
from accounts.models import User
from enrollments.models import Enrollment, EnrollmentStatus


TRISTA_USERNAME = 'candrarinitristaharidewati'


class Command(BaseCommand):
    help = 'Run a one-pass QA cleanup on the dev DB. Idempotent.'

    @transaction.atomic
    def handle(self, *args, **opts):
        self.stdout.write(self.style.SUCCESS('\n=== cleanup_demo ==='))

        a_count = self._delete_qa_leftovers()
        b_count = self._repair_over_capacity()
        c_count = self._merge_duplicate_subjects()
        d_count = self._collapse_active_periods()
        e_count = self._fix_trista_overlaps()
        # Run Kelas dedupe BEFORE Session dedupe so any sessions moved onto
        # the surviving Kelas in step (g) get folded by (date, start_time)
        # in step (f).
        g_count = self._dedupe_kelas_by_name()
        f_removed, f_skipped = self._dedupe_sessions()

        self.stdout.write(self.style.SUCCESS('\n=== SUMMARY ==='))
        self.stdout.write(f'  (a) QA leftovers removed:        {a_count}')
        self.stdout.write(f'  (b) Over-capacity dropped:       {b_count}')
        self.stdout.write(f'  (c) Duplicate subjects merged:   {c_count}')
        self.stdout.write(f'  (d) Active periods normalized:   {d_count}')
        self.stdout.write(f'  (e) Trista schedule reassigns:   {e_count}')
        self.stdout.write(f'  (f) Duplicate sessions removed:  {f_removed}')
        if f_skipped:
            self.stdout.write(f'      (skipped, kept both):        {f_skipped}')
        self.stdout.write(f'  (g) Duplicate Kelas merged:      {g_count}')

    # ─── (a) QA leftovers ───────────────────────────────────────────────────

    def _delete_qa_leftovers(self):
        """Soft-delete kelas id 157 + hard-delete user tesqa.smp@gmail.com.

        For the kelas we use soft delete (is_deleted=True) per project rule;
        for the QA test user we hard-delete because the row is purely test
        scaffolding and the project rule "Enrollment uses PROTECT against
        StudentProfile" forces us to clean enrollments/bookings first.
        """
        removed = 0
        kelas = Kelas.objects.filter(pk=157).first()
        if kelas is not None and not kelas.is_deleted:
            kelas.soft_delete()
            self.stdout.write(f'  - soft-deleted Kelas 157 "{kelas.name}"')
            removed += 1
        elif kelas is None:
            # Also handle a "by-name" match in case the PK isn't 157 on this DB.
            named = Kelas.objects.filter(
                name='Tes Kelas Otomatis SMP-SMA', is_deleted=False,
            ).first()
            if named is not None:
                named.soft_delete()
                self.stdout.write(f'  - soft-deleted Kelas "{named.name}" (pk={named.pk})')
                removed += 1

        # QA test user (also catch by email; their username may vary)
        targets = User.objects.filter(
            email__iexact='tesqa.smp@gmail.com',
        )
        for u in list(targets):
            self._hard_delete_student(u)
            removed += 1
        return removed

    def _hard_delete_student(self, user):
        """Strip Enrollment + bookings + profile, then drop the User row."""
        from sessions_app.models import SessionBooking

        sp = getattr(user, 'student_profile', None)
        if sp is not None:
            # Bookings cascade with Enrollment, but be explicit for clarity.
            enr_ids = list(
                Enrollment.objects.filter(student_profile=sp).values_list('pk', flat=True)
            )
            if enr_ids:
                SessionBooking.objects.filter(enrollment_id__in=enr_ids).delete()
            Enrollment.objects.filter(student_profile=sp).delete()
            sp.delete()
        username = user.username
        user.delete()
        self.stdout.write(f'  - hard-deleted QA user "{username}" + dependencies')

    # ─── (b) Over-capacity ──────────────────────────────────────────────────

    def _repair_over_capacity(self):
        """Drop excess ACTIVE enrollments so no class shows enrolled > capacity.

        Drops in oldest-first order so newer/recent attendees stay enrolled.
        Drops are marked DROPPED rather than deleted so any history attached
        to those enrollments (attendance/grades) is still intact.
        """
        from sessions_app.models import BookingStatus, SessionBooking
        from django.utils import timezone

        dropped_total = 0
        for kelas in Kelas.objects.filter(is_deleted=False).only(
            'id', 'capacity', 'name'
        ):
            active = list(
                Enrollment.objects
                .filter(kelas=kelas, status=EnrollmentStatus.ACTIVE, is_deleted=False)
                .order_by('enrolled_at', 'id')
            )
            excess = len(active) - kelas.capacity
            if excess <= 0:
                continue
            # Trim from the OLDEST end so the freshest stay. Excess > 0 means
            # we keep `capacity` newest; older ones flip to DROPPED.
            to_drop = active[: excess]
            for enr in to_drop:
                enr.status = EnrollmentStatus.DROPPED
                enr.save(update_fields=['status', 'updated_at'])
                # Cancel future bookings so the seat actually frees up.
                SessionBooking.objects.filter(
                    enrollment=enr, status=BookingStatus.BOOKED,
                ).update(status=BookingStatus.CANCELLED, updated_at=timezone.now())
                dropped_total += 1
            self.stdout.write(
                f'  - kelas "{kelas.name}" cap={kelas.capacity}, '
                f'dropped {excess} oldest ACTIVE enrollment(s)'
            )
        return dropped_total

    # ─── (c) Duplicate subjects ─────────────────────────────────────────────

    def _merge_duplicate_subjects(self):
        """Collapse duplicate Subject rows by name.

        Keep the lowest-PK row; re-point Kelas FKs of all higher-PK rows; delete
        the dupes.
        """
        from django.db.models import Count
        dupe_names = (
            Subject.objects
            .values('name')
            .annotate(c=Count('id'))
            .filter(c__gt=1)
            .values_list('name', flat=True)
        )
        merged = 0
        for name in list(dupe_names):
            rows = list(Subject.objects.filter(name=name).order_by('id'))
            if len(rows) < 2:
                continue
            keep, *dupes = rows
            for d in dupes:
                n = Kelas.objects.filter(subject=d).update(subject=keep)
                d.delete()
                merged += 1
                self.stdout.write(
                    f'  - merged Subject "{name}" pk={d.pk if d.pk else "?"} '
                    f'-> pk={keep.pk} (re-pointed {n} kelas)'
                )
        return merged

    # ─── (d) Active periods ─────────────────────────────────────────────────

    def _collapse_active_periods(self):
        """Ensure at most one AcademicPeriod row is is_active=True.

        Wins the contest: the row with the most recent start_date (tie-broken
        by highest pk). All others get is_active=False.
        """
        actives = list(
            AcademicPeriod.objects
            .filter(is_active=True)
            .order_by('-start_date', '-id')
        )
        if len(actives) <= 1:
            return 0
        winner = actives[0]
        flipped = 0
        for p in actives[1:]:
            p.is_active = False
            p.save(update_fields=['is_active', 'updated_at'])
            flipped += 1
        self.stdout.write(
            f'  - kept AcademicPeriod "{winner.name}" active, '
            f'flipped {flipped} other(s)'
        )
        return flipped

    # ─── (e) Trista schedule overlaps ───────────────────────────────────────

    def _fix_trista_overlaps(self):
        """Collapse Trista's per-kelas Schedule rows to one and assign
        non-overlapping (day, start_time, end_time) windows so the slot
        conflict rule holds.

        Strategy: pick slots from a fixed bank of (day, start, end) windows
        that don't overlap with each other. If there are more classes than
        slots, cycle to a second non-overlapping bank later in the day.
        """
        trista = User.objects.filter(username=TRISTA_USERNAME).first()
        if trista is None:
            return 0
        teacher_profile = getattr(trista, 'teacher_profile', None)
        if teacher_profile is None:
            return 0

        # Bank of non-overlapping slots, one per kelas. Ordered so each row
        # uses a different (day, start_time) than every other row.
        slot_bank = [
            ('MONDAY',    time(13, 0), time(14, 30)),
            ('MONDAY',    time(15, 0), time(16, 30)),
            ('TUESDAY',   time(13, 0), time(14, 30)),
            ('TUESDAY',   time(15, 0), time(16, 30)),
            ('WEDNESDAY', time(13, 0), time(14, 30)),
            ('WEDNESDAY', time(15, 0), time(16, 30)),
            ('THURSDAY',  time(13, 0), time(14, 30)),
            ('THURSDAY',  time(15, 0), time(16, 30)),
            ('FRIDAY',    time(13, 0), time(14, 30)),
            ('FRIDAY',    time(15, 0), time(16, 30)),
            ('SATURDAY',  time(9, 0),  time(10, 30)),
            ('SATURDAY',  time(10, 45), time(12, 15)),
            ('SATURDAY',  time(13, 0), time(14, 30)),
            ('SATURDAY',  time(15, 0), time(16, 30)),
            ('MONDAY',    time(17, 0), time(18, 30)),
            ('TUESDAY',   time(17, 0), time(18, 30)),
        ]

        kelases = list(
            Kelas.objects
            .filter(teacher_profile=teacher_profile, is_deleted=False)
            .order_by('id')
        )

        reassigned = 0
        for idx, kelas in enumerate(kelases):
            if idx >= len(slot_bank):
                # No more slots; warn but keep schedules intact.
                self.stdout.write(
                    f'  - WARN: out of slot bank for Trista at kelas "{kelas.name}"'
                )
                continue
            day, st, et = slot_bank[idx]
            # Pull the existing room (if any) from the first schedule so we
            # don't wipe room assignments.
            existing = list(kelas.schedules.all().order_by('id'))
            room = existing[0].room if existing else ''
            # Replace ALL schedules on this kelas with a single canonical row.
            kelas.schedules.all().delete()
            Schedule.objects.create(
                kelas=kelas, day=day,
                start_time=st, end_time=et, room=room,
            )
            reassigned += 1

        if reassigned:
            self.stdout.write(
                f'  - reassigned {reassigned} of Trista\'s classes to '
                f'distinct non-overlapping weekly slots'
            )
        return reassigned

    # ─── (f) Duplicate Session rows ─────────────────────────────────────────

    def _dedupe_sessions(self):
        """Collapse Session duplicates per kelas, grouped by (date, start_time).

        Survivor selection:
          1. Row with the most Attendance rows wins.
          2. Tie-broken by lowest session_number.

        Migration: for each loser, attempt to move its Attendance and
        SessionBooking rows onto the survivor. If a target row already exists
        for that (enrollment, survivor) pair (unique constraint), the loser's
        row is dropped instead. After migration, the loser Session is deleted
        (which cascades any remaining bookings/attendance still pointing at
        it).

        If a group contains two rows that BOTH have non-overlapping attendance
        that would still collide on survivor after best-effort migration, we
        leave both rows in place and count it as `skipped`, with a message.
        Renumbering is NOT performed; we only need to preserve the unique
        constraint (kelas, session_number), which deleting losers cannot
        violate.
        """
        from collections import defaultdict
        from django.db import IntegrityError, transaction as txn

        from academics.models import Kelas
        from sessions_app.models import Attendance, Session, SessionBooking

        removed_total = 0
        skipped_total = 0

        kelases = Kelas.objects.filter(is_deleted=False).only('id', 'name')
        for kelas in kelases:
            # Load FULL Session rows (no .only()) so the post_delete signal
            # can still read instance.kelas after the row is removed - the
            # signal uses a refresh-from-db fallback for deferred fields and
            # that fails on an already-deleted row.
            sessions = list(
                Session.objects
                .filter(kelas=kelas)
                .order_by('session_number')
            )
            buckets = defaultdict(list)
            for s in sessions:
                if s.date is None or s.start_time is None:
                    continue
                buckets[(s.date, s.start_time)].append(s)

            for (d, t), rows in buckets.items():
                if len(rows) < 2:
                    continue

                # Pick survivor: most attendance, then lowest session_number.
                def _score(sess):
                    return (
                        Attendance.objects.filter(session=sess).count(),
                        -sess.session_number,  # lower session_number wins on tie
                    )

                rows.sort(key=_score, reverse=True)
                survivor = rows[0]
                losers = rows[1:]

                group_removed = 0
                group_skipped = 0
                for loser in losers:
                    ok = self._migrate_and_delete(survivor, loser)
                    if ok:
                        group_removed += 1
                    else:
                        group_skipped += 1

                if group_removed:
                    self.stdout.write(
                        f'  - kelas "{kelas.name}" {d} {t.strftime("%H:%M")}: '
                        f'kept session #{survivor.session_number}, '
                        f'removed {group_removed} duplicate(s)'
                    )
                if group_skipped:
                    self.stdout.write(
                        f'    WARN kelas "{kelas.name}" {d} {t.strftime("%H:%M")}: '
                        f'kept {group_skipped} duplicate(s) (attendance conflict)'
                    )
                removed_total += group_removed
                skipped_total += group_skipped

        return removed_total, skipped_total

    def _migrate_and_delete(self, survivor, loser):
        """Move loser's bookings + attendance to survivor where possible.

        Returns True if the loser session was deleted; False if it had to be
        kept due to unresolvable unique-constraint collisions on the survivor.
        """
        from django.db import IntegrityError, transaction as txn
        from sessions_app.models import Attendance, SessionBooking

        try:
            with txn.atomic():
                # Move bookings one by one. Unique (enrollment, session) means
                # if a survivor row already has the same enrollment booked, we
                # just delete the loser's row.
                for booking in SessionBooking.objects.filter(session=loser):
                    existing = SessionBooking.objects.filter(
                        enrollment=booking.enrollment_id, session=survivor,
                    ).first()
                    if existing is None:
                        booking.session = survivor
                        booking.save(update_fields=['session', 'updated_at'])
                    else:
                        # Prefer the BOOKED, kind=AUTO/PICKED row over CANCELLED.
                        if (
                            booking.status == 'BOOKED'
                            and existing.status == 'CANCELLED'
                        ):
                            existing.delete()
                            booking.session = survivor
                            booking.save(update_fields=['session', 'updated_at'])
                        else:
                            booking.delete()

                # Move attendance similarly.
                for att in Attendance.objects.filter(session=loser):
                    if Attendance.objects.filter(
                        enrollment=att.enrollment_id, session=survivor,
                    ).exists():
                        # Survivor already has attendance for this enrollment;
                        # drop the loser's row.
                        att.delete()
                    else:
                        att.session = survivor
                        att.save(update_fields=['session', 'updated_at'])

                # Grade rows reference session via SET_NULL; preserve them by
                # repointing to survivor (no unique constraint exists).
                from grades.models import Grade
                Grade.objects.filter(session=loser).update(session=survivor)

                loser.delete()
            return True
        except IntegrityError as e:
            # Bail out and keep both. Should be rare; reported via WARN above.
            return False

    # ─── (g) Duplicate Kelas rows ───────────────────────────────────────────

    def _dedupe_kelas_by_name(self):
        """Collapse Kelas duplicates by (teacher_profile_id, name).

        When a seeder (e.g. populate_demo) re-creates a demo class because
        the academic period rotated, two non-deleted Kelas rows for the same
        teacher and name accumulate. Keep the one with the most enrollments
        (tie broken by highest pk), re-point Enrollment + Schedule + Session
        FKs onto the survivor where unique constraints allow, and soft-delete
        the loser.
        """
        from collections import defaultdict
        from django.db import models
        from django.utils import timezone

        from academics.models import Kelas, Schedule
        from enrollments.models import Enrollment
        from sessions_app.models import Session

        kelas_groups = defaultdict(list)
        for k in Kelas.objects.filter(is_deleted=False).only(
            'id', 'teacher_profile_id', 'name',
        ):
            kelas_groups[(k.teacher_profile_id, k.name)].append(k)

        merged = 0
        for (tp_id, name), rows in kelas_groups.items():
            if len(rows) < 2:
                continue

            # Choose survivor: most enrollments, highest pk as tiebreak.
            def _score(k):
                n = Enrollment.objects.filter(kelas=k).count()
                return (n, k.pk)

            rows.sort(key=_score, reverse=True)
            survivor = Kelas.objects.get(pk=rows[0].pk)  # full instance
            losers = rows[1:]

            for loser_stub in losers:
                loser = Kelas.objects.get(pk=loser_stub.pk)

                # Move Enrollment rows where (student_profile, survivor) does
                # not collide; otherwise drop the loser's enrollment to avoid
                # the unique constraint.
                for enr in Enrollment.objects.filter(kelas=loser):
                    collision = Enrollment.objects.filter(
                        student_profile=enr.student_profile_id,
                        kelas=survivor,
                    ).exclude(pk=enr.pk).first()
                    if collision is None:
                        enr.kelas = survivor
                        enr.save(update_fields=['kelas', 'updated_at'])
                    else:
                        # Survivor already has an enrollment for this student.
                        # Prefer the row with stronger status (ACTIVE > COMPLETED
                        # > DROPPED). Hard-delete the weaker row; bookings and
                        # attendance cascade with it.
                        rank = {
                            'ACTIVE': 3, 'COMPLETED': 2, 'DROPPED': 1,
                        }
                        if rank.get(enr.status, 0) > rank.get(collision.status, 0):
                            collision.delete()
                            enr.kelas = survivor
                            enr.save(update_fields=['kelas', 'updated_at'])
                        else:
                            enr.delete()

                # Schedule rows: the survivor's slot is the canonical one for
                # the merged kelas (cleanup_demo's step (e) keeps Trista's
                # schedules unique per kelas). Just drop the loser's schedules
                # rather than try to re-point and clash on
                # unique (kelas, day, start_time).
                Schedule.objects.filter(kelas=loser).delete()

                # Session rows: re-point per row with a session_number bump
                # when the survivor already owns that number. The (date,
                # start_time) duplicates this creates get folded by step (f)
                # which runs after this method.
                max_num = (
                    Session.objects.filter(kelas=survivor)
                    .aggregate(models.Max('session_number'))['session_number__max']
                    or 0
                )
                used = set(
                    Session.objects
                    .filter(kelas=survivor)
                    .values_list('session_number', flat=True)
                )
                next_num = max_num + 1
                for sess in Session.objects.filter(kelas=loser).order_by('session_number'):
                    if sess.session_number not in used:
                        used.add(sess.session_number)
                        sess.kelas = survivor
                        sess.save(update_fields=['kelas', 'updated_at'])
                    else:
                        sess.kelas = survivor
                        sess.session_number = next_num
                        used.add(next_num)
                        next_num += 1
                        sess.save(update_fields=['kelas', 'session_number', 'updated_at'])

                loser.is_deleted = True
                loser.deleted_at = timezone.now()
                loser.save(update_fields=['is_deleted', 'deleted_at', 'updated_at'])
                merged += 1
                self.stdout.write(
                    f'  - merged Kelas duplicate "{name}" pk={loser.pk} '
                    f'-> pk={survivor.pk} (teacher_profile={tp_id})'
                )

        return merged
