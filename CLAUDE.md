# CLAUDE.md — GlowMathCourse Bimbel Registration System

> This file is read by Claude Code at the start of every session.
> It defines the project context, tech stack, conventions, and rules.
> Last updated: 2026-05-18

---

## Project Status

**Phase 3 — UI Redesign (in progress)**

✅ Database ERD v4 (26 tables, all migrated, supports TK + UMUM levels)
✅ 3 separate login portals (siswa / guru / admin) at `/`, `/guru/login/`, `/admin/login/`
✅ 2 register wizards (siswa + guru) with 5-level jenjang pills (TK / SD / SMP / SMA / UMUM)
✅ 2 forgot-password pages (WhatsApp deeplink with pre-filled username)
✅ Waiting / pending-approval page (animated pulse + timeline)
✅ **Student Dashboard** (Khan V3 — discovery-focused: announcement hero, best teacher of the month, popular + new classes, today's sessions, latest journal)
✅ **Teacher Dashboard** (Notion V2 — clean: today's sessions priority, to-do list, kelas table, students perlu perhatian)
✅ Sidebar collapse (desktop, localStorage-persisted) + mobile drawer (<768px)
✅ 3 teacher "See All" pages: `/teacher/students/`, `/teacher/classes/`, `/teacher/sessions/` (paginated + filterable)
✅ Animations on auth pages: page fade-in, step slide/fade, error shake, loading spinner, success pop, card-hover lift/border
✅ Responsive design on both dashboards (mobile/tablet/desktop)

✅ **Admin Dashboard** (V4 Data Pro) — built. ~30 admin_panel templates (lists, forms, partials) plus dashboard, all under the `.dp-*` CSS convention.
✅ Student / teacher / admin redesign effectively complete. 0 templates still use legacy `emerald-NNN` or stray Tailwind `teal-NNN` tokens; remaining feature pages use the `primary-NNN` palette, Data Pro `.dp-*` classes, or inline teal hex codes per DESIGN_SYSTEM.md.
🟡 Deployment paused (Hostinger VPS ready; deploy artifacts staged under `deploy/` — see DEPLOYMENT.md)

**Theme:** Teal anchored on `#7fcacd` (rebrand 2026-05-29, replacing the previous emerald `#10b981` primary). Tabler icons loaded in [base.html](templates/base.html) and [base_auth.html](templates/base_auth.html). See [DESIGN_SYSTEM.md](DESIGN_SYSTEM.md) for the full palette and per-role styling rules.

**Dev server runs on port 8765** (not 8000 — port 8000 was held by a stale PHP process). Use `python manage.py runserver 8765`.

---

## Project Overview

**Name:** GlowMathCourse — Tutoring Class Registration System
**Type:** Multi-role web application (Student, Teacher, Admin)
**Purpose:** Streamline class registration, scheduling, attendance, and grade management for a single tutoring center (bimbel) in Indonesia
**Target users:** TK / SD / SMP / SMA / UMUM (universitas + adult) students, teachers, and admin staff
**UI language:** Bahasa Indonesia (all user-facing text)
**Code language:** English (all variable names, column names, enum values, comments)

---

## Tech Stack (LOCKED — do not change)

| Layer | Technology | Version |
|-------|-----------|---------|
| Language | Python | 3.12+ |
| Framework | Django | 6.0+ |
| Frontend | Django Templates + Tailwind CSS | - |
| Interactivity | HTMX + Alpine.js (via CDN) | - |
| Forms | django-crispy-forms + crispy-tailwind | - |
| Database (dev) | SQLite | built-in |
| Database (prod) | PostgreSQL | via Railway |
| Auth | django.contrib.auth (built-in) | - |
| Static files | whitenoise | 6.12+ |
| Environment | python-dotenv | - |
| HTMX integration | django-htmx | - |
| CSS framework | django-tailwind | - |

### Frontend libraries (CDN — no npm install)
```html
<script src="https://unpkg.com/htmx.org@1.9"></script>
<script src="https://unpkg.com/alpinejs@3"></script>
```

---

## Architecture

- **Monolith** — single Django project, no microservices, no separate API
- **Server-rendered** — Django templates, NOT a SPA
- **HTMX** for dynamic interactions (filtering, inline editing, partial page updates)
- **Alpine.js** for client-side UI (dropdowns, modals, toggles)
- **No REST API** — all logic in Django views, no DRF
- **No React, no Vue, no Next.js**

---

## Database Schema

**Reference file:** [ERD_REFERENCE.md](ERD_REFERENCE.md) — read this for complete table definitions.

**26 tables (ERD v4 — LOCKED).** Existing 15 from v1 (`Rating` removed) plus 11 new in 4 new apps:
- **notifications/** Notification
- **course_materials/** CourseMaterial
- **journals/** MonthlyJournal, SessionNote
- **ratings/** TeacherRating + ClassRating (replaced old `Rating`)
- **billing/** Invoice, Payment, Refund (feature-flagged off via `ENABLE_PAYMENT_FEATURE = False`)

### Key rules:
- `Kelas` (not `Class`) — because `Class` is a Python reserved word
- Single `User` model with `role` field (STUDENT, TEACHER, ADMIN)
- One-to-one profile tables per role (StudentProfile, TeacherProfile, AdminProfile)
- Profile auto-created via Django signal on User creation
- `enrolled_count` is NOT stored — derive from `Enrollment.objects.filter(kelas=kelas, status='ACTIVE').count()`
- Soft delete on User, Kelas, Enrollment (is_deleted + deleted_at)
- All queries must include `.filter(is_deleted=False)` by default
- Attendance and Rating link to Enrollment (not directly to User + Kelas)
- **Backward-compat `@property` shims:** `Kelas.teacher` → `teacher_profile.user`, `Enrollment.student` → `student_profile.user`. Attribute access still works; ORM lookups must use the real path (e.g. `kelas__teacher_profile__user=user`)

### Enum values (all English in code):
```python
# User roles
class Role(models.TextChoices):
    STUDENT = 'STUDENT', 'Siswa'
    TEACHER = 'TEACHER', 'Guru'
    ADMIN = 'ADMIN', 'Admin'

# Education levels (5 jenjang — Indonesian acronyms preserved)
class Level(models.TextChoices):
    TK = 'TK', 'TK'
    SD = 'SD', 'SD'
    SMP = 'SMP', 'SMP'
    SMA = 'SMA', 'SMA'
    UMUM = 'UMUM', 'Umum'   # universitas + dewasa (UTBK, TOEFL, IELTS, business English…)

# Days (full English)
class Day(models.TextChoices):
    MONDAY = 'MONDAY', 'Senin'
    TUESDAY = 'TUESDAY', 'Selasa'
    WEDNESDAY = 'WEDNESDAY', 'Rabu'
    THURSDAY = 'THURSDAY', 'Kamis'
    FRIDAY = 'FRIDAY', 'Jumat'
    SATURDAY = 'SATURDAY', 'Sabtu'

# Grade types
class GradeType(models.TextChoices):
    QUIZ = 'QUIZ', 'Kuis'
    MIDTERM = 'MIDTERM', 'UTS'
    FINAL = 'FINAL', 'UAS'
    ASSIGNMENT = 'ASSIGNMENT', 'Tugas'

# Attendance status
class AttendanceStatus(models.TextChoices):
    PRESENT = 'PRESENT', 'Hadir'
    PERMITTED = 'PERMITTED', 'Izin'
    ABSENT = 'ABSENT', 'Alpha'

# Enrollment status
class EnrollmentStatus(models.TextChoices):
    ACTIVE = 'ACTIVE', 'Aktif'
    COMPLETED = 'COMPLETED', 'Selesai'
    DROPPED = 'DROPPED', 'Keluar'

# Kelas status
class KelasStatus(models.TextChoices):
    OPEN = 'OPEN', 'Buka'
    FULL = 'FULL', 'Penuh'
    CLOSED = 'CLOSED', 'Tutup'

# Session status
class SessionStatus(models.TextChoices):
    SCHEDULED = 'SCHEDULED', 'Terjadwal'
    COMPLETED = 'COMPLETED', 'Selesai'
    CANCELLED = 'CANCELLED', 'Dibatalkan'

# Academic quarter
class Quarter(models.TextChoices):
    Q1 = 'Q1', 'Kuartal 1'
    Q2 = 'Q2', 'Kuartal 2'
    Q3 = 'Q3', 'Kuartal 3'
    Q4 = 'Q4', 'Kuartal 4'
```

---

## Business Rules (enforce in views)

1. **Level matching:** student_profile.level must match kelas.level on enrollment
2. **Capacity check:** active enrollment count < kelas.capacity before enrolling
3. **Rating guard:** enrollment.status must be COMPLETED before student can rate
4. **Grade ownership:** only kelas.teacher can input grades for that kelas
5. **Teacher schedule conflict:** same teacher cannot have overlapping times on same day
6. **Room conflict:** same room cannot be double-booked on same day/time
7. **Session limit:** session_number cannot exceed kelas.total_sessions
8. **Duplicate enrollment:** prevented by unique_together (student_id, kelas_id)
9. **Duplicate attendance:** prevented by unique_together (enrollment_id, session_id)
10. **One rating per enrollment:** enforced by unique constraint on enrollment_id

---

## Roles & Access Control

### Student (role = STUDENT)
- Browse classes filtered by their level (SD/SMP/SMA)
- View class details (teacher, schedule, rating)
- Enroll in classes (with level matching + capacity check)
- View enrolled classes and schedules
- View grades per class
- View attendance records
- Rate teachers (only after class is COMPLETED)

### Teacher (role = TEACHER)
- Create and manage classes (kelas)
- Set schedule (multi-day support)
- View enrolled students per class
- Create sessions (pertemuan)
- Mark attendance per session
- Input and update student grades
- View own ratings from students

### Admin (role = ADMIN)
- Full CRUD on all data (users, classes, subjects, categories, etc.)
- Dashboard with stats (total students, active classes, etc.)
- Manage academic periods
- Search & filter students by name, level, school
- Search & filter classes by subject, level, day, teacher
- View activity logs

---

## Coding Conventions

### Python / Django
- Use **class-based views** (ListView, DetailView, CreateView, UpdateView, DeleteView) where possible
- Use **function-based views** for complex logic (enrollment, attendance marking)
- All model names: **PascalCase** (StudentProfile, AcademicPeriod)
- All field names: **snake_case** (school_name, start_time)
- All enum values: **UPPER_SNAKE_CASE** (STUDENT, MONDAY, QUIZ)
- Use Django's `TextChoices` for all enums
- Use `get_FOO_display()` for showing Indonesian labels in templates
- Always use `select_related()` and `prefetch_related()` to avoid N+1 queries
- Put business logic in views, NOT in models (keep models thin)

### Templates
- Use Django template inheritance: `base.html` → role layouts → pages
- All user-facing text in **Bahasa Indonesia**
- Use Tailwind CSS utility classes for styling
- Use HTMX attributes for dynamic behavior (`hx-get`, `hx-post`, `hx-target`, `hx-swap`)
- Use Alpine.js for client-side state (`x-data`, `x-show`, `x-on:click`)
- Mobile-first responsive design
- Use crispy forms for all form rendering

### File naming
- Templates: `app_name/template_name.html` (e.g., `students/dashboard.html`)
- Static files: `static/css/`, `static/js/`, `static/images/`
- No separate CSS files — use Tailwind classes in templates

### Git
- Commit messages: `feat:`, `fix:`, `refactor:`, `docs:`, `style:`
- Branch naming: `feature/enrollment`, `fix/attendance-bug`
- Never commit `.env`, `db.sqlite3`, `__pycache__/`, `node_modules/`

---

## Scope Boundaries — DO NOT BUILD

These features are explicitly OUT OF SCOPE:
- ❌ Multi-branch support
- ❌ SMS notifications (use WhatsApp instead)
- ❌ File upload by students (no certificate upload, etc.) — **EXCEPTIONS:** teacher profile photo (ImageField on TeacherProfile, ≤ 2 MB, jpg/png/webp) and `CourseMaterial.file` uploaded by teachers (under `/media/course_materials/YYYY/MM/`)
- ❌ REST API / DRF
- ❌ React / Vue / any JS framework
- ❌ Microservices architecture
- ❌ Real-time chat or messaging
- ❌ Public-facing marketing landing page (separate site if needed)

### Deferred (Phase 3, models exist, no UI)
- 💤 **Payment / Invoice / Refund** — billing app + models are migrated, but UI is gated behind `ENABLE_PAYMENT_FEATURE = False` in [config/settings/base.py](config/settings/base.py). Don't build UI for these until the flag flips.
- 💤 **Email notifications** — WhatsApp is the only channel today.

Any feature not listed in the Roles & Access Control section above requires separate discussion before building.

---

## Project Structure

```
glowmathcourse/
├── manage.py
├── .env                          # SECRET_KEY, DATABASE_URL
├── .gitignore
├── requirements.txt
├── CLAUDE.md                     # This file
├── ERD_REFERENCE.md              # Database schema reference
│
├── config/                       # Django project settings
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
│
├── accounts/                     # Auth + user management
│   ├── models.py                 # User, StudentProfile, TeacherProfile, AdminProfile
│   ├── views.py                  # Login, register, profile
│   ├── forms.py                  # Registration forms per role
│   ├── signals.py                # Auto-create profile on user creation
│   ├── decorators.py             # @role_required('STUDENT'), etc.
│   ├── urls.py
│   ├── admin.py
│   └── templates/accounts/
│
├── academics/                    # Core academic models
│   ├── models.py                 # AcademicPeriod, Category, Subject, Kelas, Schedule
│   ├── views.py
│   ├── forms.py
│   ├── urls.py
│   ├── admin.py
│   └── templates/academics/
│
├── enrollments/                  # Enrollment management
│   ├── models.py                 # Enrollment
│   ├── views.py                  # Enroll, drop, list
│   ├── urls.py
│   ├── admin.py
│   └── templates/enrollments/
│
├── sessions/                     # Sessions + attendance
│   ├── models.py                 # Session, Attendance
│   ├── views.py
│   ├── urls.py
│   ├── admin.py
│   └── templates/sessions/
│
├── grades/                       # Grade management
│   ├── models.py                 # Grade
│   ├── views.py
│   ├── urls.py
│   ├── admin.py
│   └── templates/grades/
│
├── ratings/                      # Teacher ratings
│   ├── models.py                 # Rating
│   ├── views.py
│   ├── urls.py
│   ├── admin.py
│   └── templates/ratings/
│
├── dashboard/                    # Role-based dashboards
│   ├── views.py                  # student_dashboard, teacher_dashboard, admin_dashboard
│   ├── urls.py
│   └── templates/dashboard/
│
├── activity_logs/                # Activity logging
│   ├── models.py                 # ActivityLog
│   ├── utils.py                  # log_activity() helper
│   ├── admin.py
│   └── templates/activity_logs/
│
├── templates/                    # Global templates
│   ├── base.html                 # Root layout (Tailwind + HTMX + Alpine)
│   ├── navbar.html
│   ├── sidebar.html
│   └── components/               # Reusable template components
│       ├── _class_card.html
│       ├── _grade_table.html
│       ├── _rating_stars.html
│       ├── _schedule_grid.html
│       ├── _pagination.html
│       └── _modal.html
│
├── static/
│   └── css/
│       └── output.css            # Tailwind compiled CSS
│
└── theme/                        # django-tailwind app
    └── ...
```

---

## Development Workflow

1. Always activate venv first: `venv\Scripts\activate` (Windows)
2. After model changes: `python manage.py makemigrations` → `python manage.py migrate`
3. Run dev server: `python manage.py runserver`
4. Tailwind watch mode: `python manage.py tailwind start`
5. Create superuser: `python manage.py createsuperuser`

---

## Deployment Target

- **Platform:** Hostinger VPS KVM 1 (provisioned, deployment paused pending UI redesign)
- **Domain:** glowmathclass.com (planned)
- **Database:** PostgreSQL
- **Static files:** whitenoise
- **WSGI server:** gunicorn
- **TLS:** Let's Encrypt
- **Budget:** Rp 5–12 juta (client project)

---

## Conventions (confirmed)

- **All code in English** — variables, functions, columns, enum values, comments
- **All UI text in Bahasa Indonesia** — labels, buttons, messages, validation errors
- **TK / SD / SMP / SMA / UMUM stay as Indonesian acronyms** — both in code and UI (UMUM display label = "Umum")
- **Class → `Kelas`** — `class` is a Python reserved word; always `Kelas` in model/code
- **Soft delete on User, Kelas, Enrollment** — `is_deleted` + `deleted_at`; default queries must include `.filter(is_deleted=False)`

---

## Test Users

All test passwords are simple by design — these are dev credentials only.

### Admin Portal (`/admin/login/`)
- `admin` / `admin1234` — legacy superuser
- `glowmathcourse` / `ikanbuvivid` — new named admin (superuser + staff, department: "Management")

### Student Portal (`/`)
- **APPROVED** — `student001` … `student180` / `murid123`
  - `student009` has dense real data (recommended for testing dashboard at scale)
  - **`rafaeladhikabagasalfathan`** / `ikanbuvivid` — UMUM level, fully populated by `populate_rafael` (6 UMUM enrollments, sessions, grades, journals, ratings)
- **PENDING** (redirects to `/waiting/` on login) — `student181` … `student195` / `murid123`
- **REJECTED** (login fails with error) — `student196` … `student200` / `murid123`

### Teacher Portal (`/guru/login/`)
- **APPROVED** — `teacher001` … `teacher045` / `teacher123`
  - **`candrarinitristaharidewati`** / `ikanbuvivid` — populated by `populate_trista` (5 classes across SD/SMP/SMA/UMUM, ~34 active students, sessions today, partial attendance/journals to fill the "to-do" widget)
- **PENDING** — `teacher046` … `teacher048` / `teacher123`
- **REJECTED** — `teacher049` … `teacher050` / `teacher123`

---

## Management Commands

### Data generation
- `python manage.py generate_dummy_data` — wipe + regenerate the full dummy dataset (200 students + 50 teachers + classes + sessions + grades + ratings + journals + notifications)
- `python manage.py create_test_users` — idempotently create the 3 named test users (Rafael, Trista, GlowMath). Supports `--reset-passwords` to force-rewrite passwords/flags on existing rows
- `python manage.py populate_rafael` — enroll Rafael into UMUM classes + create sessions/grades/journals/ratings. Idempotent.
- `python manage.py populate_trista` — create Trista's 5 classes (SD/SMP/SMA/UMUM mix) + enroll students + sessions/grades/journals/ratings. Idempotent.

### Server
- **Dev port: 8765** (not 8000 — port 8000 was held by a stale PHP process)
- `python manage.py runserver 8765`

### Verification
- `python manage.py check` — must return "0 silenced" before deploy
- `python manage.py makemigrations --check --dry-run` — confirm no pending model changes
- `python manage.py migrate` — apply pending migrations
