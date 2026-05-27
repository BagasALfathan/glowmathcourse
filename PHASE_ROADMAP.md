# Phase Roadmap — GlowMath Course

> **Last updated:** 2026-05-23. Tracking project progress phase by phase.

---

## Status Overview

| Phase | Scope | Status |
|---|---|---|
| 0 | Database + Auth foundation | ✅ Done |
| 1 | Initial UI + role-aware dashboard | ✅ Done |
| 2 | Race-safe enrollment + see-all pages | ✅ Done |
| **3A** | Khan Playful redesign (student-facing pages) | ✅ **Done** |
| 3B | Teacher CRUD redesign | 🟡 In progress |
| 3C | Admin management redesign (V4 Data Pro) | ⏳ Not started |
| 3D | Notifications + course materials | ⏳ Not started |
| 4 | Deployment to Hostinger VPS | ⏳ Not started |

---

## ✅ Phase 0 — Foundation (complete)

- Django 6.0+ project bootstrap, app split
- Custom User model with `role` (STUDENT / TEACHER / ADMIN) + `approval_status`
- 26-table ERD v4 — see [ERD_REFERENCE.md](ERD_REFERENCE.md)
- 3-portal auth (`/`, `/guru/login/`, `/admin/login/`) with redirect rules
- Soft delete on User / Kelas / Enrollment

## ✅ Phase 1 — Initial UI

- Tailwind via CDN + HTMX + Alpine.js
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

## ✅ Phase 3A — Khan Playful redesign (complete)

The big student-facing visual pass. All page wrappers use `bg-gradient-to-b from-{color}-50 to-gray-50 -m-6 p-4 md:p-6 min-h-screen`. Heroes use rounded-3xl with rotated emoji tiles. Cards use rounded-2xl with `.card-hover-lift`.

| # | Page | URL | Accent | Status |
|---|---|---|---|---|
| 1 | Student Dashboard | `/dashboard/student/` | emerald | ✅ |
| 2 | Teacher Dashboard | `/dashboard/teacher/` | emerald (Notion clean) | ✅ |
| 3 | Browse Classes | `/classes/` | emerald | ✅ |
| 4 | Class Detail | `/classes/<pk>/` | emerald | ✅ |
| 5 | Browse Teachers | `/teachers/` | emerald | ✅ |
| 6 | Teacher Profile (public) | `/teachers/<pk>/` | emerald | ✅ |
| 7 | My Classes list | `/my-classes/` | emerald + amber rate-prompt | ✅ |
| 8 | My Class Detail | `/my-classes/<id>/` | emerald + amber rate banner | ✅ |
| 9 | My Schedule (operating hours) | `/my-schedule/classes/` | emerald | ✅ |
| 10 | My Schedule (sessions) | `/my-schedule/sessions/` | emerald | ✅ |
| 11 | Rate Teacher + Class | `/rate/<enrollment_id>/` | amber + emerald | ✅ |
| 12 | Student Sidebar | (partial) | teal | ✅ |
| 13 | Profile (cyan settings) | `/profile/` | **cyan** | ✅ |
| 14 | Pengumuman | `/announcements/` | **orange** | ✅ |
| 15 | Bantuan (Help) | `/help/` | emerald | ✅ |
| 16 | Logout confirmation modal | (in sidebar) | red gradient | ✅ |

**Bonus shipped in Phase 3A:**
- ✅ Accurate star ratings retrofit — CSS overlay technique via `{% star_rating value %}` template tag in `dashboard/templatetags/dashboard_filters.py`
- ✅ `populate_full_demo` management command — idempotent + deterministic mega-seeder
- ✅ Contextual Rate prompts — pulse badge on `/my-classes/` cards + amber banner on detail
- ✅ Sidebar context processor (`sidebar_data`) with cached pending-rating count
- ✅ Cache invalidation signals on TeacherRating + Enrollment save/delete
- ✅ Khan Playful sidebar scoped via `:has(.student-nav-marker)` — teacher/admin untouched
- ✅ 4 utility nav entries (Pengumuman, Jurnal Bulanan, Bantuan, Logout) with clickable user-block → `/profile/`

**Documentation deliverables (this turn):**
- [URL_ROUTES.md](URL_ROUTES.md) — canonical URL-name reference
- [PITFALLS.md](PITFALLS.md) — every bug we've hit, with the fix
- [TEST_USERS.md](TEST_USERS.md) — accounts + scenarios
- [PHASE_ROADMAP.md](PHASE_ROADMAP.md) — this file

---

## 🟡 Phase 3B — Teacher CRUD (in progress)

Most teacher pages exist functionally (Phase 1/2 scaffold) but use legacy styling. The 3B pass brings them to Khan Playful parity, with the teacher accent being Notion-Clean (white cards, 0.5px borders, solid emerald buttons, `.card-hover-border` instead of `.card-hover-lift`).

**Pages to redesign:**

| Page | URL | Priority |
|---|---|---|
| Create Class | `/teacher/classes/create/` | high |
| Edit Class | `/teacher/classes/<pk>/edit/` | high |
| Class Students roster | `/teacher/classes/<pk>/students/` | high |
| Create Session | `/teacher/sessions/create/<kelas_id>/` | high |
| Edit Session | `/teacher/sessions/<pk>/edit/` | high |
| Mark Attendance | `/teacher/sessions/<pk>/attendance/` | high |
| Input Grade | `/teacher/grades/create/` | high |
| Edit Grade | `/teacher/grades/<pk>/edit/` | high |
| Grade Book (per class) | `/teacher/classes/<pk>/grades/` | high |
| Grades overview | `/teacher/grades/` | med |
| Student Progress (teacher view) | `/teacher/classes/<pk>/students/<enrollment_id>/progress/` | med |
| Write Monthly Journal | (new — needs route) | med |
| Teacher Ratings dashboard | `/teacher/ratings/` | med |
| Teacher Schedule (classes view) | `/teacher/schedule/classes/` | low |
| Teacher Schedule (sessions view) | `/teacher/schedule/sessions/` | low |

New routes needed:
- `/teacher/journals/<enrollment_id>/` — write/edit monthly journal
- `/teacher/notes/<session_id>/` — session notes (in journals app)

---

## ⏳ Phase 3C — Admin Management (V4 Data Pro)

The admin dashboard (`/dashboard/admin/`) currently uses legacy styling. Phase 3C delivers the Data Pro variant per [DESIGN_SYSTEM.md](DESIGN_SYSTEM.md): dense metric grids, sortable tables, activity feed sidebar, tab navigation.

**Scope:**

| Area | URL | Notes |
|---|---|---|
| Admin Dashboard V4 | `/dashboard/admin/` | metric tiles, top/worst leaderboards, activity feed |
| Users CRUD | `/admin-panel/users/` | search + filter + bulk actions |
| Approval queue | `/admin-panel/pending-users/` | swipe / batch approve |
| Categories / Subjects / Periods | `/admin-panel/{categories,subjects,periods}/` | full CRUD |
| Classes CRUD | `/admin-panel/classes/` | soft-delete + restore |
| Enrollments | `/admin-panel/enrollments/` | bulk transfer + status changes |
| Grades / Ratings / Logs | `/admin-panel/{grades,ratings,logs}/` | filtered tables |
| Master Schedule | `/admin-panel/schedule/` | all teachers + conflict detection |
| Announcements | `/admin-panel/announcements/` | pin/unpin + target audience |
| Exports | `/admin-panel/export/{students,classes}/` | Excel downloads |

---

## ⏳ Phase 3D — Notifications + Course Materials

Both backends are migrated (ERD v4) but UI is not yet built.

**Notifications:**
- `/notifications/` (student) — inbox list
- `/teacher/notifications/` — inbox list
- `/admin-panel/notifications/` — broadcast + audit
- Badge count in navbar (read/unread)

**Course Materials:**
- `/materials/` (student) — list per class, download links
- `/teacher/materials/upload/` — drag-drop upload (PDF / PPTX / etc.)
- File size + type validation
- Storage path: `/media/course_materials/YYYY/MM/`

---

## ⏳ Phase 4 — Deployment

Target platform: **Hostinger VPS KVM 1** (already provisioned, deployment paused for UI redesign).

| Step | Owner |
|---|---|
| Ubuntu 24.04 base + system updates | dev |
| Nginx reverse proxy + Gunicorn (systemd unit) | dev |
| Migrate dev SQLite → prod PostgreSQL | dev |
| Whitenoise static serve | (already wired) |
| `.env` for prod (`SECRET_KEY`, `DATABASE_URL`, `ALLOWED_HOSTS`, `DEBUG=False`) | dev |
| Let's Encrypt SSL via certbot | dev |
| Custom domain DNS → `glowmathclass.com` | dev |
| Initial data seed (categories, periods, admin user) | dev |
| Smoke test on prod (`smoke_test` command) | dev |
| Backup cron (`backup_database` command nightly) | dev |

Budget anchor: Rp 5–12 juta total project cost. VPS ~Rp 70k/month.

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

This roadmap snapshot is from **2026-05-23**. When a phase completes, update the Status Overview row + add details to that phase's section. When new pitfalls or URL names are discovered, append to `PITFALLS.md` and `URL_ROUTES.md` respectively rather than this file.
