# Test Users Reference — GlowMath Course

> **Last updated:** 2026-05-23. Use these accounts for manual QA. All dev-only passwords are shared by convention.

---

## Quick Reference (named accounts)

| Role | Username | Password | Purpose |
|---|---|---|---|
| **Student (rich)** | `rafaeladhikabagasalfathan` | `ikanbuvivid` | UMUM siswa, fully populated by `populate_rafael` |
| **Teacher (rich)** | `candrarinitristaharidewati` | `ikanbuvivid` | 5 classes across SD/SMP/SMA/UMUM, populated by `populate_trista` |
| **Admin (named)** | `glowmathcourse` | `ikanbuvivid` | Superuser + staff, department = "Management" |
| **Admin (legacy)** | `admin` | `admin1234` | Legacy superuser kept for back-compat |

---

## Bulk test users (created by `populate_full_demo` + `create_test_users`)

| Pattern | Password | Count | Approval status |
|---|---|---|---|
| `student001` – `student180` | `murid123` | 180 | **APPROVED** — full access |
| `student181` – `student195` | `murid123` | 15 | **PENDING** — redirects to `/waiting/` on login |
| `student196` – `student200` | `murid123` | 5 | **REJECTED** — login fails with error |
| `teacher001` – `teacher045` | `teacher123` | 45 | **APPROVED** |
| `teacher046` – `teacher048` | `teacher123` | 3 | **PENDING** |
| `teacher049` – `teacher050` | `teacher123` | 2 | **REJECTED** |

`student009` is intentionally dense (heavy enrollment + grade history) — recommended when testing list pagination, charts, or any "at scale" rendering on the student dashboard.

---

## Scenarios per named user

### Rafael (`rafaeladhikabagasalfathan`) — UMUM student

Populated by `python manage.py populate_rafael` (idempotent).

- 6 active UMUM enrollments across math (Kalkulus, Statistika), English (TOEFL, IELTS), and one more
- **≥1 COMPLETED enrollment that is unrated** — drives the contextual Rate Teacher banner + amber card overlay
  - Enrollment #318 is conventionally the unrated one — if it has a rating, run `populate_full_demo` again or wipe via Django shell to reset.
- ~78 session attendance records (mix of PRESENT / PERMITTED / ABSENT)
- 5+ grades per enrollment (mix of QUIZ / MIDTERM / FINAL / ASSIGNMENT)
- Recent monthly journals from teachers

**Test routes:**
- `/dashboard/student/` — Khan V3 dashboard (announcement hero, top teacher, popular classes, journal)
- `/my-classes/` — list with rate-prompt badge on the unrated COMPLETED card
- `/my-classes/318/` — detail page with amber rate banner at top
- `/rate/318/` — rate Teacher + Class form
- `/my-schedule/classes/` — operating-hours weekly grid
- `/my-schedule/sessions/` — actual sessions weekly grid
- `/my-monthly-score/` — aggregated monthly scores
- `/my-attendance/` — attendance records
- `/announcements/` — orange Khan Playful list
- `/journals/` — monthly journals from teachers
- `/help/` — Bantuan FAQ
- `/profile/` — cyan Khan Playful edit form

### Trista (`candrarinitristaharidewati`) — teacher

Populated by `python manage.py populate_trista` (idempotent).

- 5 classes across SD / SMP / SMA / UMUM mix
- ~34 active students enrolled
- Sessions scheduled today (for "Sesi Hari Ini" widget on teacher dashboard)
- Partial attendance recorded — leaves the "to-do" widget non-empty
- Has a few partial journals to test the journal-writing flow

**Test routes:**
- `/dashboard/teacher/` — Notion V2 dashboard (today's sessions priority, to-do list)
- `/teacher/classes/` — see-all classes
- `/teacher/sessions/` — see-all sessions with filter
- `/teacher/students/` — see-all students
- `/teacher/grades/` — gradebook overview
- `/teacher/ratings/` — incoming ratings (TeacherRating + ClassRating split)

### GlowMath (`glowmathcourse`) — admin

Idempotently created by `create_test_users`. `is_superuser=True`, `is_staff=True`, `AdminProfile.department='Management'`.

**Test routes:**
- `/dashboard/admin/` — admin dashboard (legacy — Phase 3A redesign deferred)
- `/admin-panel/pending-users/` — approval queue (PENDING students/teachers)
- `/admin-panel/users/` — full user CRUD
- `/admin-panel/classes/` — class management with soft-delete + restore
- `/admin-panel/enrollments/` — enrollment management with bulk actions
- `/admin-panel/grades/`, `/admin-panel/ratings/`, `/admin-panel/logs/`
- `/admin-panel/schedule/` — master schedule across all teachers
- `/admin-panel/announcements/` — pin/unpin/edit/delete

---

## Setup commands

```bash
# All three named users (Rafael, Trista, GlowMath) — idempotent
python manage.py create_test_users

# Force-rewrite passwords on existing rows (useful after dummy regen)
python manage.py create_test_users --reset-passwords

# Just Rafael — enroll + sessions + grades + journals + ratings (idempotent)
python manage.py populate_rafael

# Just Trista — 5 classes + students + sessions + partial attendance (idempotent)
python manage.py populate_trista

# Mega populate — full demo dataset (200 students + 50 teachers + classes + sessions + grades + ratings + journals + announcements + logs)
python manage.py populate_full_demo

# Reset all dummy data + repopulate (destructive — wipes non-superuser content)
python manage.py populate_full_demo --reset

# Smaller dataset for fast testing
python manage.py populate_full_demo --quick
```

The `populate_full_demo` command is **deterministic** — `--seed=42` (default) always produces the same output, so screenshots and test cases are reproducible across machines.

---

## Reset-to-known-state recipe

When tests have mutated state (e.g. Rafael's #318 got accidentally rated), run:

```bash
python manage.py populate_full_demo --reset    # 30s, wipes all non-superuser content
python manage.py create_test_users             # restores named users + passwords
python manage.py populate_rafael               # restores Rafael's specific scenario
python manage.py populate_trista               # restores Trista's specific scenario
```

After this, all scenarios above hold again.

---

## Dev portal

```bash
python manage.py runserver 8765    # port 8765 (NOT 8000 — see CLAUDE.md)
```

- Student portal:  http://127.0.0.1:8765/
- Teacher portal:  http://127.0.0.1:8765/guru/login/
- Admin portal:    http://127.0.0.1:8765/admin/login/
