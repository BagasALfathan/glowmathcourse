# Demo Data Reference — GlowMath Course

> **Last updated:** 2026-05-28. How dummy data is populated, what scenarios are guaranteed, and how to reset to a known state.

---

## Quick commands

```bash
# Idempotent populate — safe to re-run; tops up missing data
python manage.py populate_full_demo

# Smaller dataset (faster — useful for quick smoke testing)
python manage.py populate_full_demo --quick

# Wipe all non-superuser content + repopulate (destructive)
python manage.py populate_full_demo --reset

# Custom seed for different deterministic output
python manage.py populate_full_demo --seed=123
```

All flags can be combined: `--reset --quick --seed=99`.

---

## What gets populated (per run on a fresh DB)

The command runs **13 sections** in sequence, inside a single `transaction.atomic()`. Each section is idempotent — re-running won't duplicate rows.

| Section | Default | Quick (`--quick`) | Notes |
|---|---|---|---|
| Categories + Subjects | 1 category + 10 subjects with emoji icons | same | `get_or_create` by name |
| Teachers enriched | 40 | 10 | Sets bio, specialization, education, experience_years, jenjang (1–3 per teacher) |
| AcademicPeriod | `Q2 <year>` ensured | same | `get_or_create` by year + period_type + quarter |
| **Classes (Kelas) NEW** | **18** | **6** | Templates spread across TK/SD/SMP/SMA/UMUM. Re-runs don't add more if templates already exist. |
| Schedules | 2–3 days per new class | same | Time slots picked from a fixed pool |
| **Sessions per class** | **16** | **8** | Past + present + future. Status auto-set: COMPLETED (past), SCHEDULED (future), or COMPLETED-if-already-started today |
| Enrollments | 35–85% of capacity per OPEN class; 100% for FULL classes | same | Distribution: 72% ACTIVE, 20% COMPLETED, 8% DROPPED |
| Rafael ensured COMPLETED + unrated | 1 enrollment guaranteed | same | Promotes an ACTIVE → COMPLETED if no existing unrated COMPLETED |
| Attendances | All completed sessions × all enrolled | same | Distribution: 80% PRESENT, 12% PERMITTED, 8% ABSENT |
| Grades | 2 per enrollment (MIDTERM + FINAL only) | same | QUIZ + ASSIGNMENT skipped because `Grade.clean()` requires a session FK; bell-curve score ~80 ±9 |
| Ratings | 70% of COMPLETED enrollments get both TeacherRating + ClassRating | same | Skewed score distribution (50/30/15/5 — see below) |
| Monthly Journals | Last **3** months per ACTIVE/COMPLETED enrollment | **2** months | `get_or_create` by (enrollment, year, month) |
| Announcements | 4 admin-authored items | same | Mix of `target_role` (ALL, STUDENT) |
| Activity Logs | 50 historic entries | same | Only added if existing count < 50 (avoids bloat) |

---

## Distribution targets

### Enrollment status (per OPEN class)

| Status | % |
|---|---|
| ACTIVE | 72 |
| COMPLETED | 20 |
| DROPPED | 8 |

FULL classes are forced to 100% ACTIVE up to capacity (used for UI testing of the locked-CTA / waitlist flow).

### Attendance status

| Status | % |
|---|---|
| PRESENT | 80 |
| PERMITTED | 12 |
| ABSENT | 8 |

### Rating score (TeacherRating + ClassRating, independent)

| Score | % |
|---|---|
| 5 ★ | 50 (teacher) / 45 (class) |
| 4 ★ | 30 (teacher) / 35 (class) |
| 3 ★ | 15 |
| 1–2 ★ | 5 |

Only 70% of COMPLETED enrollments get rated → leaves some empty for realism.

### Grade score

Python `random.gauss(80, 9)` clamped to [40, 100]. Most grades land in the 70–90 band.

---

## Class templates (built into the command)

Templates ensure spread across jenjang + subjects. First N from this list are used based on `--quick`:

| # | Jenjang | Subject | Name | Cap | Price (Rp) | Status |
|---|---|---|---|---|---|---|
| 1 | TK | Calistung | Calistung Ceria TK A | 8 | 200k | OPEN |
| 2 | SD | Matematika Dasar | Matematika SD Kelas 1-3 Asyik | 15 | 300k | OPEN |
| 3 | SD | Bahasa Inggris | English for Kids SD | 10 | 400k | OPEN |
| 4 | SMP | Matematika | Matematika SMP Komprehensif | 18 | 450k | OPEN |
| 5 | SMP | Fisika | Fisika SMP Dasar | 15 | 450k | OPEN |
| 6 | SMP | IPA Terpadu | IPA Terpadu SMP | 20 | 400k | OPEN |
| 7 | SMA | Matematika | Matematika UTBK Intensif | 15 | 500k | OPEN |
| 8 | SMA | Matematika | Matematika Peminatan IPA Kelas 12 | 12 | 550k | OPEN |
| 9 | SMA | Fisika | Fisika UTBK Saintek | 15 | 550k | OPEN |
| 10 | SMA | Kimia | Kimia UTBK Reguler | 15 | 550k | OPEN |
| 11 | SMA | Biologi | Biologi UTBK Saintek | 15 | 550k | OPEN |
| 12 | SMA | Bahasa Inggris | Bahasa Inggris UTBK | 15 | 480k | OPEN |
| 13 | UMUM | Matematika | Statistika & Probabilitas | 15 | 550k | OPEN |
| 14 | UMUM | Bahasa Inggris | TOEFL Preparation iBT | 15 | 750k | OPEN |
| 15 | UMUM | Bahasa Inggris | IELTS Academic Reguler | 12 | 800k | OPEN |
| 16 | UMUM | Bahasa Inggris | Business English Conversation | 10 | 700k | OPEN |
| 17 | SMA | Matematika | Matematika UTBK Premium (FULL) | 6 | 800k | **FULL** |
| 18 | UMUM | Bahasa Inggris | TOEFL Express Bootcamp (FULL) | 5 | 1m | **FULL** |

`--quick` uses templates #1–6 only.

---

## Guaranteed test scenarios

After `populate_full_demo` on a fresh DB:

- ✅ **Rafael** has 6+ enrollments across UMUM classes
- ✅ **Rafael has ≥1 COMPLETED enrollment WITHOUT a TeacherRating** — drives the contextual rate prompt (badge on `/my-classes/` card + amber banner on `/my-classes/<id>/`)
- ✅ **Trista** has 5 classes spread across SD/SMP/SMA/UMUM
- ✅ **Today's sessions exist** — `/my-schedule/sessions/` has data, teacher dashboard "Sesi Hari Ini" widget is non-empty
- ✅ **Some classes are FULL** — for testing the locked-CTA / waitlist flow
- ✅ **Rating distribution is spread** — some 5-star, some 4, some 3, some 1–2 → the accurate `{% star_rating %}` template tag visibly renders fractional stars
- ✅ **Recent journals exist** — student `/journals/` has content; teacher dashboard widgets populated
- ✅ **3 admin announcements visible to all roles** — at least one student-visible pinned

---

## Determinism

The command sets `random.seed(<seed>)` at start (default 42). Same seed = identical output across machines, **provided** the upstream data hasn't changed (e.g., user list).

Use `--seed=N` for an alternate deterministic snapshot — useful for screenshots or before/after comparisons.

```bash
python manage.py populate_full_demo --seed=99
```

---

## Idempotency mechanism

Every write uses `get_or_create` or an existence check:

| Entity | Uniqueness key |
|---|---|
| Subject | `name` |
| AcademicPeriod | `(year, period_type, quarter)` |
| Kelas | `name` |
| Schedule | `(kelas, day, start_time)` |
| Enrollment | `(student_profile, kelas)` |
| Session | `(kelas, date, start_time)` |
| Attendance | `(session, enrollment)` |
| Grade | `(enrollment, grade_type, session)` — but command only writes MIDTERM + FINAL with `session=None`, so 1 per (enr, grade_type) |
| TeacherRating | `enrollment` (OneToOne) |
| ClassRating | `enrollment` (OneToOne) |
| MonthlyJournal | `(enrollment, year, month)` |
| Announcement | `title` |

Re-running adds only what's missing. To regenerate from scratch, use `--reset` (deletes everything except superusers).

---

## Reset recipes

### Full reset + repopulate (clean slate, ~30s)

```bash
python manage.py populate_full_demo --reset
python manage.py create_test_users          # restores named users
python manage.py populate_rafael            # restores Rafael-specific scenario
python manage.py populate_trista            # restores Trista-specific scenario
```

### Reset Rafael's enrollments only (without --reset full wipe)

```python
# python manage.py shell
from accounts.models import User
from enrollments.models import Enrollment
from django.core.cache import cache

rafael = User.objects.get(username='rafaeladhikabagasalfathan')
Enrollment.objects.filter(student_profile=rafael.student_profile).delete()
cache.delete(f'sidebar_pending_ratings_{rafael.id}')
exit()

# Then in shell:
python manage.py populate_rafael
```

### Force one COMPLETED enrollment for Rate Teacher testing

```python
# python manage.py shell
from enrollments.models import Enrollment, EnrollmentStatus
from ratings.models import TeacherRating, ClassRating
from django.core.cache import cache

enr = (
    Enrollment.objects
    .filter(student_profile__user__username='rafaeladhikabagasalfathan')
    .first()
)
enr.status = EnrollmentStatus.COMPLETED
enr.save()
TeacherRating.objects.filter(enrollment=enr).delete()
ClassRating.objects.filter(enrollment=enr).delete()
cache.delete(f'sidebar_pending_ratings_{enr.student_profile.user_id}')
print(f'/rate/{enr.id}/ ← visit this URL')
```

---

## Caveats

- **Faker is optional.** Without it, the command falls back to a fixed name pool. Install via `pip install Faker` for realistic Indonesian (`locale='id_ID'`) names.
- **QUIZ + ASSIGNMENT grades NOT generated** — `Grade.clean()` requires a `session` FK for these types. The command only writes MIDTERM + FINAL (no session needed) to keep the seed logic simple. Real teacher input is expected to fill in QUIZ/ASSIGNMENT entries.
- **ActivityLog only adds 50 if count < 50** — re-running doesn't bloat the log table.
- **Teacher photos NOT generated.** Avatars render initials in colored backgrounds.
- **No course materials, no notifications, no invoices.** These belong to Phase 3D / billing features and are not part of the demo seed.
- **`--reset` does NOT touch users.** It wipes academic + participation + records content but leaves the User table intact. Run `create_test_users` after `--reset` if user data is also stale.

---

## When to re-run

- After pulling a migration that adds a new field with a non-null default → re-run to seed the new field
- Before a demo / screencast → run `--reset --quick` for a clean, fast snapshot
- After running stress tests → run `--reset` to clear race-test artifacts
- After a manual ad-hoc shell session that mutated state → run plain `populate_full_demo` to top up
