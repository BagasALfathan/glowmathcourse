# Project Structure — GlowMath Course

> **Last scanned:** 2026-05-28. Django 6.0.3 monorepo. Single project, no microservices.

---

## Top-Level Layout

```
glowmathcourse/
├── config/                   # Django project settings + root URL conf
│   ├── settings/
│   │   ├── base.py           # Shared settings, INSTALLED_APPS, TEMPLATES, MIDDLEWARE
│   │   ├── dev.py            # DEBUG=True, SQLite, console email
│   │   └── production.py     # DEBUG=False, Postgres via DATABASE_URL
│   ├── urls.py               # Root urlconf — mounts every app's URLs
│   ├── wsgi.py / asgi.py
│   └── __init__.py
│
├── accounts/                 # User + 3 profile models + auth views
├── academics/                # Kelas, Subject, Schedule, Period, public teacher catalog
├── enrollments/              # Enrollment + EnrollmentWaitlist
├── sessions_app/             # Session + Attendance + SessionBooking (INSTALLED)
├── sessions/                 # ⚠ Legacy app — URLs only, NOT in INSTALLED_APPS. Hosts student my_attendance views
├── grades/                   # Grade model + teacher/student grade pages
├── journals/                 # MonthlyJournal + SessionNote
├── ratings/                  # TeacherRating + ClassRating (split from old single Rating)
├── announcements/            # Announcement model + list/detail/create
├── notifications/            # Notification model (Phase 3D — backend ready, no UI yet)
├── course_materials/         # CourseMaterial model (Phase 3D — backend ready, no UI yet)
├── billing/                  # Invoice/Payment/Refund — feature-flagged OFF
├── dashboard/                # Role-routed dashboards + help page + context_processors + templatetags
├── student/                  # Student "see-all" pages (shadows /my-classes/ + /my-attendance/)
├── admin_panel/              # Custom admin pages (Phase 3C — separate from Django built-in admin)
├── activity_logs/            # ActivityLog audit-trail model + utils.log_activity()
│
├── templates/                # Global templates (base.html, base_auth.html, partials, components)
├── static/                   # Project-level static files (css/animations.css, css/sidebar.css, images/)
├── staticfiles/              # collectstatic output (gitignored in prod)
├── media/                    # User uploads (teacher photos, course materials)
├── theme/                    # django-tailwind app (Tailwind asset pipeline — currently unused; we ship via CDN)
│
├── backups/                  # Local DB snapshots from `backup_database` mgmt command
├── logs/                     # Local logs (gitignored)
├── db.sqlite3                # Dev database
├── backup_pre_deploy.json    # Latest pre-deployment data dump
├── manage.py
├── requirements.txt
├── Procfile                  # gunicorn entry for Hostinger deploy
├── .env                      # SECRET_KEY, DATABASE_URL (NOT committed)
│
└── *.md                      # Documentation at root — see "Documentation" section
```

---

## App Responsibilities

### `config/`
Project-level configuration. Multi-env settings:
- `base.py` — shared (INSTALLED_APPS, TEMPLATES with both context processors, AUTH_USER_MODEL='accounts.User', `ENABLE_PAYMENT_FEATURE = False`)
- `dev.py` — DEBUG=True, SQLite
- `production.py` — DEBUG=False, Postgres via `DATABASE_URL`, whitenoise

The root `urls.py` mounts every app — be careful of mount **order**, it affects URL shadowing (see [PITFALLS.md](PITFALLS.md)).

### `accounts/`
- **Models:** `User` (extends `AbstractUser`, has `role` + `approval_status` + `phone`), `StudentProfile`, `TeacherProfile`, `AdminProfile`, `TeacherJenjang`. Phone lives on `User`; profiles have `@property` shims.
- **Views:** 3 login portals (student/teacher/admin), 2 registration wizards (3-step Khan V3 + 3-step Notion V1), forgot-password (WhatsApp deeplinks), waiting page, profile + profile_settings + profile_edit + change_password
- **Signals:** auto-create role profile on User save
- **Context processor:** `pending_users_count` (for admin pending-approval badge)
- **Decorators:** `@role_required('STUDENT' / 'TEACHER' / 'ADMIN')`

### `academics/`
- **Models:** `Category`, `Subject` (FK Category, required), `AcademicPeriod` (quarter or semester), `Kelas` (NOT `Class`), `Schedule`
- **Views:** `class_browse`, `class_detail` (student-facing), `teacher_list` + `teacher_profile` (public catalog), `student_schedule_*` (weekly grids), `teacher_schedule_*`, teacher class CRUD (`teacher_class_create/edit/delete/students/complete`), teacher "see-all" (`teacher_all_students`, `teacher_all_sessions`)
- **HTMX partials:** `_class_browse_grid.html`, `_teacher_list_grid.html`
- **Middleware:** `StatusUpdateMiddleware` (auto-close expired Kelas + auto-complete Enrollments)

### `enrollments/`
- **Models:** `Enrollment` (FK student_profile + kelas, status, price_at_enrollment), `EnrollmentWaitlist`
- **Views:** `enroll` (POST, race-safe with `select_for_update`), `join_waitlist`, `my_class_detail`, `drop_class`, `teacher_update_enrollment`
- **Signals:** invalidate weekly schedule cache + sidebar pending-rating cache on enrollment save/delete

### `sessions_app/`
- **Models:** `Session`, `Attendance`, `SessionBooking`
- **Views:** teacher session CRUD + attendance marking + Excel/PDF exports; student `session_detail` (role-aware), `student_session_list`, book/cancel for MAKEUP/OPTIONAL sessions
- **Signals:** invalidate weekly schedule cache when a Session changes

### `sessions/` ⚠ legacy
- **Status:** Not in `INSTALLED_APPS` — just a `urls.py` + `views.py` mounted in `config/urls.py`. Hosts `/my-attendance/...` views.
- The `student/` app's `my_attendance` view shadows the path; `sessions:my_attendance` URL name reverses correctly but the executing view is `student.views.my_attendance`. See [PITFALLS.md](PITFALLS.md#-url-path-shadowing-my-classes).

### `grades/`
- **Models:** `Grade` (FK enrollment + nullable session; `grade_type` enum required; `clean()` enforces session FK for QUIZ + ASSIGNMENT)
- **Views:** teacher grade CRUD + HTMX inline edit, gradebook overview, Excel/PDF exports, student progress reports

### `journals/`
- **Models:** `MonthlyJournal` (per enrollment per (month,year); requires `written_by_teacher` + 4 required text fields), `SessionNote` (per-session notes)
- **Views:** `my_journals` + `journal_detail` (student-facing; teachers write via Phase 3B routes — not yet built)

### `ratings/`
- **Models:** `TeacherRating` (OneToOne enrollment + FK teacher_profile) + `ClassRating` (OneToOne enrollment + FK kelas). Both 1-5 score with optional comment + `is_anonymous`.
- **Views:** `rate_teacher` (single form submits both), `teacher_ratings` dashboard
- **Signals:** invalidate sidebar pending-rating cache on save/delete

### `announcements/`
- **Models:** `Announcement` (author, title, content, `target_role`, `level`, `is_pinned`, `is_active`, `scheduled_at`, `expires_at`). **No `category` field** — chips on UI are presentational.
- **Views:** `announcements_list`, `announcement_detail`, `announcement_create` (teacher/admin only)

### `dashboard/`
- **Views:** `dashboard_router` (auto-redirect by role), `student_dashboard`, `teacher_dashboard`, `admin_dashboard`, `help_view` (Bantuan page at `/help/`)
- **Template tags:** `dashboard_filters.py` — `star_rating` (CSS overlay accurate rendering), `getitem`, `month_name`, etc.
- **Context processor:** `sidebar_data` (cached pending-rating count for student sidebar)

### `student/`
- **Shadow views** for `/my-classes/`, `/my-attendance/`, `/my-monthly-score/`. This app's `urls.py` is mounted FIRST in `config/urls.py`, so its views win the path battle with `enrollments` and `sessions`. See [PITFALLS.md](PITFALLS.md#-url-path-shadowing-my-classes).

### `admin_panel/` (Phase 3C scope)
- **Models:** none — operates on existing models
- **Views:** pending users approval, users CRUD, classes CRUD with soft-delete + restore, categories/subjects/periods CRUD, enrollments with bulk-actions, grades/ratings/logs lists with HTMX partials, master schedule, announcements admin, Excel exports
- **Templates:** ~25 templates, most with `_*_list_table.html` HTMX partials

### `activity_logs/`
- **Model:** `ActivityLog` (user, action string, target_type string, target_id, ip_address, user_agent, auto created_at)
- **Utils:** `log_activity(user, action, target_type, target_id=None)` helper

### `billing/` ⚠ feature-flagged
- **Models:** `Invoice`, `Payment`, `Refund` — migrated, FK integrity in place
- **UI:** NONE. Gated behind `ENABLE_PAYMENT_FEATURE = False` in `config/settings/base.py`. Don't build UI until the flag flips.

### `notifications/` + `course_materials/` ⚠ backend ready, no UI
- Models migrated. No views/templates. Slated for Phase 3D.

---

## Templates layout (`templates/`)

```
templates/
├── base.html              # Shared shell — sidebar + navbar + body + Alpine collapse state
├── base_auth.html         # Standalone login/register layout (no sidebar)
├── base_print.html        # Print stylesheets
├── 403.html / 404.html / 500.html
├── coming_soon.html
├── robots.txt
│
├── partials/
│   ├── _nav_student.html  # Khan Playful — touch-eligible
│   ├── _nav_teacher.html  # ⛔ OFF-LIMITS unless task explicitly names it
│   └── _nav_admin.html    # ⛔ OFF-LIMITS unless task explicitly names it
│
├── components/
│   ├── _class_card.html       # Reusable Kelas card (used by browse + my-classes via include)
│   ├── _grade_table.html
│   ├── _rating_stars.html     # Use {% star_rating %} template tag instead — more accurate
│   ├── _schedule_grid.html
│   └── _session_grid.html
│
├── sessions/              # Legacy app's templates
├── student/               # Student see-all templates (my_classes, my_attendance, my_monthly_score)
└── teacher/               # Some shared teacher pages
```

Per-app templates live at `<app>/templates/<app>/...` (Django app-template convention).

---

## Frontend stack (locked — no build step)

- **Tailwind CSS** via `cdn.tailwindcss.com` (Play CDN — JIT scans DOM at load)
- **HTMX** via `unpkg.com/htmx.org@1.9`
- **Alpine.js** via `unpkg.com/alpinejs@3`
- **Tabler Icons** webfont via `cdn.jsdelivr.net/npm/@tabler/icons-webfont@3.5.0`
- **django-tailwind** package is installed but unused — `theme/` directory exists as a no-op
- No npm, no webpack, no compile step

---

## Python dependencies (highlights from `requirements.txt`)

- **Django 6.0.3** + **gunicorn 25.3.0** + **whitenoise** (static files) + **dj-database-url** (DATABASE_URL parsing)
- **django-crispy-forms 2.6** + **crispy-tailwind 1.0.3** — for the complex multi-field forms
- **django-htmx 1.27.0** — request.htmx detection
- **psycopg2-binary 2.9.12** — Postgres driver (prod)
- **pillow 12.2.0** — ImageField support (teacher photos)
- **openpyxl 3.1.5** — Excel exports (attendance, grades, students)
- **python-dotenv 1.2.2** — `.env` loading
- **Faker** (optional, locale `id_ID`) — for realistic Indonesian dummy names in `populate_full_demo`

---

## Documentation at project root

| File | Purpose |
|---|---|
| `CLAUDE.md` | Project conventions, tech stack, business rules — read at every session start |
| `DESIGN_SYSTEM.md` | Khan Playful + Notion Clean + Data Pro variants, color palette, components |
| `ERD_REFERENCE.md` | 26-table ERD v4 with field details |
| `URL_ROUTES.md` | Every named URL + path + view across 12 urlconfs |
| `PITFALLS.md` | Real bugs encountered + fixes (append-only) |
| `TEST_USERS.md` | Named test accounts + scenarios + setup recipes |
| `PHASE_ROADMAP.md` | Phase status + future scope |
| `PROJECT_STRUCTURE.md` | (this file) folder tree + app responsibilities |
| `SETUP_GUIDE.md` | Fresh-install instructions for new dev |
| `CHANGELOG.md` | Phase-by-phase change log |
| `DEMO_DATA.md` | `populate_full_demo` reference + scenarios |
| `FEATURE_PRIORITY.md` | Pre-existing — feature backlog priority list |
| `SITEMAP.md` | Pre-existing — URL/page sitemap |
| `TASK_BREAKDOWN.md` | Pre-existing — work breakdown structure |

---

## Where to start (newcomer)

1. Read `CLAUDE.md` — project conventions, what NOT to build, tech stack
2. Read `SETUP_GUIDE.md` — install + run dev server in 10 min
3. Read `DESIGN_SYSTEM.md` + `URL_ROUTES.md` — visual + routing landscape
4. Skim `PHASE_ROADMAP.md` — pick what to work on next
5. Bookmark `PITFALLS.md` — check before debugging
