# Phase Roadmap — GlowMath Course

> **Last updated:** 2026-05-29. Tracking project progress phase by phase + client revision backlog.

---

## Status Overview

| Phase | Scope | Status |
|---|---|---|
| 0 | Database + Auth foundation | ✅ Done |
| 1 | Initial UI + role-aware dashboard | ✅ Done |
| 2 | Race-safe enrollment + see-all pages | ✅ Done |
| **3A** | Khan Playful student-facing redesign (16 pages + infra) | ✅ **Done** |
| **3B** | Teacher CRUD (Create/Edit/Sessions/Gradebook/Students/Attendance) | ✅ **Done** (6 pages) |
| **3B-extra** | Schedule print, overlap validation, color rebrand `#7fcacd` | 🟡 In progress |
| **3B-remaining** | Write Journal, My Ratings dashboard | ⏳ Not started |
| **3R** | **CLIENT REVISIONS** (6 items across 3 groups) | 🔴 **New — priority** |
| 3C | Admin panel (~12 pages CRUD + V4 Data Pro dashboard) | ⏳ Not started |
| 3D | Notifications + Course Materials UI | ⏳ Not started |
| 4 | Deployment to Hostinger VPS | ⏳ Not started |

---

## ✅ Phase 0 — Foundation (complete)

- Django 6.0+ project bootstrap, app split
- Custom User model with `role` (STUDENT / TEACHER / ADMIN) + `approval_status`
- 26-table ERD v4 — see [ERD_REFERENCE.md](ERD_REFERENCE.md)
- 3-portal auth (`/`, `/guru/login/`, `/admin/login/`) with redirect rules
- Soft delete on User / Kelas / Enrollment

## ✅ Phase 1 — Initial UI

- Tailwind via CDN + HTMX + Alpine.js (no build step)
- Role-routed dashboards (`/dashboard/{student,teacher,admin}/`)
- Basic CRUD scaffolding for academic structure (Category, Subject, Period, Kelas, Schedule)
- Crispy-tailwind forms

## ✅ Phase 2 — Race-safe enrollment + see-all

- `select_for_update()` + capacity guard on `enroll`
- Enrollment waitlist with auto-positioning
- Student "see all" pages (`/my-classes/`, `/my-attendance/`, `/my-monthly-score/`)
- Teacher "see all" pages (`/teacher/classes/`, `/teacher/students/`, `/teacher/sessions/`)
- Activity logging with IP capture
- Stress test command (`stress_test_enroll`)

---

## ✅ Phase 3A — Khan Playful student redesign (complete)

The big student-facing visual pass. Page wrappers use `bg-gradient-to-b from-{color}-50 to-gray-50 -m-6 p-4 md:p-6 min-h-screen`. Heroes use rounded-3xl with rotated emoji tiles. Cards use rounded-2xl with `.card-hover-lift`.

| # | Page | URL | Status |
|---|---|---|---|
| 1 | Student Dashboard | `/dashboard/student/` | ✅ |
| 2 | Teacher Dashboard | `/dashboard/teacher/` | ✅ |
| 3 | Browse Classes | `/classes/` | ✅ |
| 4 | Class Detail | `/classes/<pk>/` | ✅ |
| 5 | Browse Teachers | `/teachers/` | ✅ |
| 6 | Teacher Profile (public) | `/teachers/<pk>/` | ✅ |
| 7 | My Classes list | `/my-classes/` | ✅ |
| 8 | My Class Detail | `/my-classes/<id>/` | ✅ |
| 9 | My Schedule (operating hours) | `/my-schedule/classes/` | ✅ |
| 10 | My Schedule (sessions) | `/my-schedule/sessions/` | ✅ |
| 11 | Rate Teacher + Class | `/rate/<enrollment_id>/` | ✅ |
| 12 | Student Sidebar | (partial) | ✅ |
| 13 | Profile (simple cyan edit) | `/profile/` | ✅ |
| 14 | Pengumuman (orange) | `/announcements/` | ✅ |
| 15 | Bantuan (Help) | `/help/` | ✅ |
| 16 | Logout confirmation modal | (in sidebar) | ✅ |

**Bonus shipped in Phase 3A:**
- ✅ Accurate star ratings retrofit (CSS overlay via `{% star_rating %}`)
- ✅ `populate_full_demo` idempotent + deterministic seeder
- ✅ Contextual rate prompts (pulse badge + amber banner)
- ✅ Sidebar context processor with cached pending-rating count
- ✅ Cache invalidation signals on TeacherRating + Enrollment
- ✅ Sidebar scoped via `:has(.student-nav-marker)` — teacher/admin isolated
- ✅ Logout modal moved to body level (escapes sidebar `transform` containing block)
- ✅ Tier 1/2/3 documentation (12 .md files)

---

## ✅ Phase 3B — Teacher CRUD (6 pages committed)

Teacher-facing redesign — Notion Clean (white cards, 0.5px borders, solid teal primary buttons, `.card-hover-border` instead of `.card-hover-lift`). All 6 pages shipped + pushed to `origin/main` (commits `0ba4bab` → `dd01d36`).

| # | Page | URL | Pattern |
|---|---|---|---|
| 1 | Create Class | `/teacher/classes/create/` | 2-group form + jenjang chips + auto-defaults |
| 2 | Edit Class | `/teacher/classes/<pk>/edit/` | Prefilled chips + status field (OPEN/FULL/CLOSED) |
| 3 | Manage Sessions | `/teacher/classes/<pk>/sessions/` | Progress + repeat-form + HTMX `+ Tambah Baris` + cap enforcement |
| 4 | Simple Gradebook | `/teacher/classes/<pk>/grades/` | Tabs per assessment (notes-prefix title) + `{% grade_note %}` strip on student side |
| 5 | Class Students roster | `/teacher/classes/<pk>/students/` | Card grid + WA deeplink + Nilai/Kehadiran action buttons |
| 6 | Per-session Attendance | `/teacher/sessions/<pk>/attendance/` | 3-state toggle (🟢 Hadir / 🟡 Izin / 🔴 Alpha) + soft future-session warning |

**Phase 3B infrastructure additions:**
- ✅ `_session_overlap_conflicts()` helper + integrated cross-class overlap validation in `teacher_sessions` POST
- ✅ `grades/templatetags/grade_filters.py` — `|grade_note` + `|grade_title` for prefix stripping
- ✅ HTMX `teacher_session_row_partial` endpoint with server-side cap enforcement (HX-Trigger toast)
- ✅ `_NOTES_TITLE_RE` regex in `grades/views.py` for `[Judul] :: catatan` parsing

---

## 🟡 Phase 3B-extra — In progress

| Item | Status | Notes |
|---|---|---|
| Teacher Monthly Schedule + Print | ✅ Done (uncommitted) | `/teacher/schedule/classes/` reused — calendar grid with color-coded sessions per kelas |
| Cross-class session overlap validation | ✅ Done (uncommitted) | Strict `<` comparison — back-to-back allowed; intra-batch + DB checks |
| Color rebrand to `#7fcacd` teal primary | 🟡 ~70% done | Tailwind config swapped (all `primary-*` instantly remapped); 53 templates bulk-converted; ~16 templates with inline `<style>` hex still need second pass |

---

## ⏳ Phase 3B-remaining (small, ~2 sesi)

| Item | URL | Status |
|---|---|---|
| Write Monthly Journal | `/teacher/journals/<enrollment_id>/` (new) | ⏳ |
| Teacher Ratings dashboard | `/teacher/ratings/` (exists, needs Notion Clean redesign) | ⏳ |
| Semantic-green restoration | (post-rebrand) | Restore `bg-green-*` for success status badges (Aktif/Hadir/Selesai) after color rebrand made them teal |
| Inline-hex finishing pass | (16 files) | Style-block hex like `#10b981` → `#4a9499` in class_detail, login_*, register_*, etc |

---

## 🔴 Phase 3R — CLIENT REVISIONS (new, priority)

6 revision items from client feedback. Slot AHEAD of Phase 3C — client needs to see these changes before admin panel is built. Architecturally low-impact (no schema change, no role addition).

### Grup A — Hide Fields (low-risk, ~1 sesi)

| # | Item | Where | Note |
|---|---|---|---|
| 1 | **Email login** (replace username field) | All login pages (`/`, `/guru/login/`, `/admin/login/`) | Email becomes the credential. Username remains in DB but auto-generated from email on register; existing users keep current username for backward compat. **No destructive migration.** |
| 2 | **Hide tarif/harga** from UI | Create Class form, Class Detail page, Browse Classes cards, My Class Detail | `Kelas.price` stays in DB (billing models reference it). Just remove display + form field. |
| 3 | **Hide rekening BCA** (`TeacherProfile.bank_account`) | Teacher profile + admin user edit | Field stays in DB for future re-enablement. |

### Grup B — Jenjang Filtering (medium, ~1 sesi)

| # | Item | Where | Note |
|---|---|---|---|
| 4 | **Browse Classes** filtered to `student_profile.level` | `/classes/` for STUDENT role | TK siswa only sees TK classes, etc. |
| 5 | **Browse Teachers** filtered to student's jenjang | `/teachers/` | Show only teachers whose `TeacherJenjang.level` includes the student's level. |

> **Architecture note:** Jenjang stays as `StudentProfile.level` field — **NOT** a new role. The 3-role system (STUDENT/TEACHER/ADMIN) is locked per ERD v4. These items are query-time filters, not schema changes.

### Grup C — Session-First Enrollment + Tentor Schedule (high, ~1–2 sesi)

| # | Item | Where | Note |
|---|---|---|---|
| 6 | **Teacher schedule on public profile** | `/teachers/<pk>/` | Show upcoming sessions per teacher (across their classes) on the public profile page. |
| 7 | **Session-first enrollment** | New flow from `/teachers/<pk>/` | Student picks a session directly from the teacher's schedule → auto-enrolls into the parent Kelas if not already enrolled. Reduces friction: no "enroll first, then look at sessions" workflow. |

---

## ⏳ Phase 3C — Admin Management (V4 Data Pro)

Admin dashboard (`/dashboard/admin/`) currently uses legacy styling. Phase 3C delivers the Data Pro variant per [DESIGN_SYSTEM.md](DESIGN_SYSTEM.md): dense metric grids, sortable tables, activity feed sidebar, tab navigation.

**~12 pages scope:**

| # | Area | URL |
|---|---|---|
| 1 | Admin Dashboard V4 | `/dashboard/admin/` |
| 2 | Approval queue | `/admin-panel/pending-users/` |
| 3 | Users CRUD | `/admin-panel/users/` |
| 4 | Classes CRUD | `/admin-panel/classes/` |
| 5 | Enrollments | `/admin-panel/enrollments/` |
| 6 | Subjects | `/admin-panel/subjects/` |
| 7 | Categories | `/admin-panel/categories/` |
| 8 | Periods | `/admin-panel/periods/` |
| 9 | Announcements | `/admin-panel/announcements/` |
| 10 | Activity Logs | `/admin-panel/logs/` |
| 11 | Ratings | `/admin-panel/ratings/` |
| 12 | Master Schedule | `/admin-panel/schedule/` |

---

## ⏳ Phase 3D — Notifications + Course Materials

Both backends migrated (ERD v4) but UI not yet built.

**Notifications:**
- `/notifications/` (student inbox)
- `/teacher/notifications/`
- `/admin-panel/notifications/` (broadcast + audit)
- Unread badge in navbar

**Course Materials:**
- `/materials/` (student — list per class, download)
- `/teacher/materials/upload/` (drag-drop PDF/PPTX/etc)
- File size + type validation
- Storage: `/media/course_materials/YYYY/MM/`

---

## ⏳ Phase 4 — Deployment

Target: **Hostinger VPS KVM 1** at `76.13.219.144` → `glowmathclass.com`. Full blueprint in [DEPLOYMENT.md](DEPLOYMENT.md).

| Step | Notes |
|---|---|
| Ubuntu 24.04 base + system updates | |
| PostgreSQL 16 + dev DB migration | dj-database-url already wired |
| Gunicorn (systemd unit) + Nginx reverse proxy | `Procfile` exists for reference |
| Let's Encrypt SSL via certbot | auto-renew via systemd timer |
| DNS A-records → 76.13.219.144 | at registrar |
| `.env` prod (SECRET_KEY, DATABASE_URL, ALLOWED_HOSTS, DEBUG=False) | |
| `python manage.py smoke_test` on prod | |
| Backup cron (`backup_database` command nightly) | |

Budget anchor: Rp 5–12 juta total. VPS ~Rp 70k/month.

---

## 📊 Effort estimate sampai Production

| Bucket | Estimate |
|---|---|
| **Phase 3R — Client revisions** (6 items, 3 grups) | **3–4 sesi** |
| **Phase 3B-extra remaining** (color rebrand finish + semantic-green restore + Write Journal + Teacher Ratings) | 2 sesi |
| **Phase 3C — Admin panel** (~12 pages) | 4–5 sesi |
| **Phase 4 — Deployment** | 1–2 sesi |
| **TOTAL ke production-ready** | **~10–13 sesi** |

**Demo-ready bottom line** (cukup buat tunjukin 6 revisi klien): **~3–4 sesi**. Setelah Phase 3R selesai, klien bisa lihat versi yang udah merefleksikan semua feedback mereka.

---

## Out of scope (explicit non-goals)

- ❌ Multi-branch support
- ❌ SMS notifications (WhatsApp deeplinks only)
- ❌ Student file uploads (except teacher profile photo + teacher-uploaded course materials)
- ❌ REST API / DRF
- ❌ React / Vue / any JS framework
- ❌ Microservices architecture
- ❌ Real-time chat
- ❌ Public marketing landing page (separate site if needed)

## Deferred (models exist, UI gated)

- 💤 **Payment / Invoice / Refund** — `billing/` migrated, UI behind `ENABLE_PAYMENT_FEATURE = False` in `config/settings/base.py`. Do not build UI until the flag flips.
- 💤 **Email notifications** — WhatsApp deeplinks are the only channel today.

---

## Re-generation note

This roadmap snapshot is from **2026-05-29**. When a phase completes, update the Status Overview row + add details to that phase's section. When new pitfalls or URL names are discovered, append to [PITFALLS.md](PITFALLS.md) and [URL_ROUTES.md](URL_ROUTES.md) respectively rather than this file.
