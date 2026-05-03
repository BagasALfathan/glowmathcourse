# CLAUDE.md — GlowMathCourse Bimbel Registration System

> This file is read by Claude Code at the start of every session.
> It defines the project context, tech stack, conventions, and rules.
> Last updated: March 28, 2026

---

## Project Overview

**Name:** GlowMathCourse — Tutoring Class Registration System
**Type:** Multi-role web application (Student, Teacher, Admin)
**Purpose:** Streamline class registration, scheduling, attendance, and grade management for a single tutoring center (bimbel) in Indonesia
**Target users:** SD/SMP/SMA students, teachers, and admin staff
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

**Reference file:** `ERD_REFERENCE.md` in project root — read this for complete table definitions.

**14 tables:** User, StudentProfile, TeacherProfile, AdminProfile, AcademicPeriod, Category, Subject, Kelas, Schedule, Session, Enrollment, Grade, Attendance, Rating, ActivityLog

### Key rules:
- `Kelas` (not `Class`) — because `Class` is a Python reserved word
- Single `User` model with `role` field (STUDENT, TEACHER, ADMIN)
- One-to-one profile tables per role (StudentProfile, TeacherProfile, AdminProfile)
- Profile auto-created via Django signal on User creation
- `enrolled_count` is NOT stored — derive from `Enrollment.objects.filter(kelas=kelas, status='ACTIVE').count()`
- Soft delete on User, Kelas, Enrollment (is_deleted + deleted_at)
- All queries must include `.filter(is_deleted=False)` by default
- Attendance and Rating link to Enrollment (not directly to User + Kelas)

### Enum values (all English in code):
```python
# User roles
class Role(models.TextChoices):
    STUDENT = 'STUDENT', 'Siswa'
    TEACHER = 'TEACHER', 'Guru'
    ADMIN = 'ADMIN', 'Admin'

# Education levels (Indonesian acronyms — keep as-is)
class Level(models.TextChoices):
    SD = 'SD', 'SD'
    SMP = 'SMP', 'SMP'
    SMA = 'SMA', 'SMA'

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

These features are explicitly OUT OF SCOPE for MVP:
- ❌ Payment / transaction / billing integration
- ❌ Discount / promo codes
- ❌ Multi-branch support
- ❌ SMS / WhatsApp notifications
- ❌ File upload (report cards, certificates, photos) — **EXCEPTION: teacher profile photo is allowed** (ImageField on TeacherProfile, max 2 MB, jpg/png/webp only, stored under `/media/teacher_photos/`)
- ❌ REST API / DRF
- ❌ React / Vue / any JS framework
- ❌ Microservices architecture
- ❌ Real-time chat or messaging
- ❌ Email notifications (Phase 2)

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

- **Platform:** Railway (free tier) or Contabo VPS
- **Database:** PostgreSQL (provided by platform)
- **Static files:** whitenoise
- **WSGI server:** gunicorn
- **Budget:** Rp 5-12 juta (client project)
