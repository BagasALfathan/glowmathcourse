# Changelog — GlowMath Course

> All notable changes per phase. Append-only — newest at top.

Format: `## [Phase X] — Title — date`. Each phase has Added / Changed / Fixed / Decisions sections as relevant.

---

## [Phase 3A] — Khan Playful UI Redesign — 2026-05-28

The big student-facing visual pass. Every Khan Playful page uses the wrapper pattern `bg-gradient-to-b from-{color}-50 to-gray-50 -m-6 p-4 md:p-6 min-h-screen`, rounded-3xl heroes with rotated emoji tiles, and `.card-hover-lift` interactions.

### Added — pages redesigned
- **Browse Classes** (`/classes/`) — filter chips + 3-col card grid + level filter
- **Class Detail** (`/classes/<id>/`) — mega hero + 6 colorful sections + sticky bottom CTA bar
- **My Class Detail** (`/my-classes/<id>/`) — progress KPI cards + sessions list + latest journal + amber rate banner when COMPLETED+unrated
- **Teacher Profile (public)** (`/teachers/<id>/`) — rating distribution + active classes carousel
- **Browse Teachers** (`/teachers/`) — student-facing catalog with hero pill search
- **My Schedule** (`/my-schedule/classes|sessions/`) — weekly calendar grid with TODAY highlight
- **Rate Teacher + Class** (`/rate/<enrollment_id>/`) — single form, interactive 5-star + suggestion chips
- **Profile (V3)** (`/profile/`) — cyan compact hero + simple edit form (replaces older multi-card prototype)
- **Pengumuman** (`/announcements/`) — orange hero + filter chips + pinned section + card grid
- **Bantuan** (`/help/`) — emerald hero + 6 FAQ cards + WhatsApp contact CTA
- **Student Sidebar** — Khan Playful theme scoped via `:has(.student-nav-marker)` (teacher/admin untouched)
- **Logout confirmation modal** — Alpine.js modal with POST form to `/logout/`

### Added — infrastructure
- **`{% star_rating value %}` template tag** — accurate CSS-overlay star rendering (replaces text `★★★★★` rounding artifacts)
- **`populate_full_demo` management command** — idempotent + deterministic (`--seed=42` default, `--reset`, `--quick` flags)
- **Contextual Rate prompts** — pulse badge on `/my-classes/` COMPLETED-unrated cards + amber banner on `/my-classes/<id>/`
- **Sidebar context processor** (`sidebar_data`) — cached pending-rating count
- **Cache invalidation signals** — `TeacherRating` save/delete + `Enrollment` save/delete clear sidebar count cache
- **Tier 1 docs** — `URL_ROUTES.md`, `PITFALLS.md`, `TEST_USERS.md`, `PHASE_ROADMAP.md`
- **Tier 2 docs** — `PROJECT_STRUCTURE.md`, `SETUP_GUIDE.md`, `CHANGELOG.md`, `DEMO_DATA.md`

### Changed
- **Class Detail layout** — removed sticky right sidebar (caused sync-scroll jank on long descriptions); both columns now scroll together with a sticky bottom CTA bar for "Daftar".
- **Browse Teachers search** — redesigned to Hero Pill style (Variant A).
- **Star ratings everywhere** — retrofit to accurate CSS overlay via `{% star_rating %}`. Affected: teacher profile, class detail, rate teacher confirmation, dashboard top-teachers widget.
- **Student sidebar** — removed "Pengaturan" link (overkill); user-block at bottom is now clickable `<a href="/profile/">` with hover lift + ✏️ icon scale-up.
- **`accounts:profile_settings`** — kept the URL but now redirects (302) to `accounts:profile` to consolidate.

### Fixed
- **Multi-line `{# ... #}` comment leaked as visible text** in `_nav_student.html`. Switched to `{% comment %} ... {% endcomment %}`.
- **Race condition in enrollment capacity check** — wrapped in `transaction.atomic()` with `Kelas.objects.select_for_update()` + IntegrityError catch.
- **Sidebar horizontal scrollbar overflow** — added `overflow-x: hidden` on the student-scoped aside.
- **Logout flow** — Django 5+ requires POST. Replaced direct `<a href="/logout/">` with a button that opens an Alpine modal containing a POST form.
- **`/my-classes/` view shadowing** — discovered + documented that `student.views.my_classes` shadows `enrollments.views.my_classes` because `student/urls.py` is mounted first. Earlier `needs_rating` annotation that went into the wrong view was moved.

### Decisions
- **Rate Teacher access:** contextual (badge + banner), NOT a sidebar item. Avoids cluttering navigation with a transient action.
- **Logout:** confirmation modal, NOT direct submit. Prevents accidental logouts during long study sessions.
- **Sidebar Khan Playful styling:** STUDENT-only. Teacher and admin sidebars stay on legacy styling until Phase 3B/3C explicitly redesigns them.
- **Profile UI:** single simple edit form (NOT 6 modular cards). The modular layout was a transient prototype.
- **`Announcement.category` field:** NOT added. Event/Sistem/Promo filter chips render as presentational placeholders until/unless real categorization is needed.

---

## [Phase 2] — Race-Safe Enrollment + See-All Pages — early 2026

### Added
- **Race-safe `enroll` view** — `select_for_update()` on `Kelas` + capacity guard inside `transaction.atomic()`
- **Enrollment waitlist** — `EnrollmentWaitlist` model with `position` field + `join_waitlist` view
- **Student "see-all" pages** — `/my-classes/`, `/my-attendance/`, `/my-monthly-score/` (paginated + filterable)
- **Teacher "see-all" pages** — `/teacher/classes/`, `/teacher/students/`, `/teacher/sessions/`
- **Activity logs with IP** — `ActivityLog` model + `log_activity()` helper
- **Stress test command** — `stress_test_enroll` (20 threads × cap 3 to validate race safety)

### Decisions
- **Race safety:** `select_for_update()` + capacity recount inside transaction, NOT optimistic concurrency
- **Soft delete:** `is_deleted` + `deleted_at` on `User`, `Kelas`, `Enrollment`. All default querysets filter `is_deleted=False`.
- **URL shadowing for "see-all":** `student/urls.py` mounted before `enrollments/urls.py` + `sessions/urls.py` so student views serve `/my-classes/` and `/my-attendance/`. The shadowed views in `enrollments/` and `sessions/` are effectively dead.

---

## [Phase 1] — Initial UI + Dashboards — early 2026

### Added
- **Student dashboard** (Khan V3) — announcement hero, today's sessions, popular classes, top teacher of the month
- **Teacher dashboard** (Notion V2) — today's sessions priority, to-do list, kelas table, "siswa perlu perhatian"
- **Admin dashboard** (legacy — Data Pro V4 deferred to Phase 3C)
- **3-portal login** — `/`, `/guru/login/`, `/admin/login/` with distinct visual treatments
- **Registration wizards** — 3-step Khan V3 (student, gamified) + 3-step Notion V1 (teacher, minimal)
- **Waiting approval page** — pulse-ring animation + 3-step timeline
- **Forgot password** — WhatsApp deeplink with pre-filled username
- **Profile + profile_edit + change_password**
- **Initial CRUD scaffolding** — Category, Subject, Period, Kelas, Schedule (legacy admin UI)
- **Crispy-tailwind forms** — for complex multi-field forms (registration, profile edit, class create)

---

## [Phase 0] — Foundation — initial commit

### Added
- **Django 6.0.3 project** — `config/` layout with multi-env settings (`base.py` + `dev.py` + `production.py`)
- **Custom `User` model** — extends `AbstractUser` with `role` + `approval_status` + `phone`
- **ERD v4** — 26 tables across 15 apps, all migrated
- **Auth backbone** — login/logout/register/reset views, decorators (`@role_required`), signals (auto-create role profile on User save)
- **Tailwind via CDN** + **HTMX** + **Alpine.js** — no JS framework, no build step
- **Tabler Icons** webfont
- **Initial seed commands** — `create_test_users`, `seed_data`, `generate_dummy_data`

### Decisions
- **Stack locked:** Django 6.0+, Tailwind via CDN, HTMX, Alpine.js. NO DRF, NO React/Vue/Next, NO microservices, NO npm.
- **Single User model with `role` field** — not separate Student/Teacher/Admin User subclasses
- **Reserved-word workaround:** `Kelas` (not `Class`) — Python reserves the word
- **Indonesian acronyms in code AND UI:** TK / SD / SMP / SMA / UMUM stay as-is
- **UI language:** Bahasa Indonesia. **Code language:** English (vars, functions, columns, enum values, comments).
- **Three-portal auth split:** student at `/`, teacher at `/guru/login/`, admin at `/admin/login/`. `/django-admin/` reserved for Django built-in admin.

---

## Conventions for this file

- **Date format:** YYYY-MM-DD
- **Section ordering:** Added → Changed → Fixed → Decisions
- **Append-only:** never edit completed phases. If a Phase 3A entry needs correcting later, add a follow-up Phase 3A.1 entry rather than rewriting.
- **Cross-link:** when a change references another doc, use `[link text](FILENAME.md)` format so it stays clickable in GitHub.
