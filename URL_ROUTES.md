# URL Routes — GlowMath Course

> **Last reviewed:** 2026-05-18. Auth + teacher see-all routes are implemented with the new emerald theme.

## Public (no login required) — ✅ all implemented with emerald redesign

- `/` — Student login (mint gradient + bubbles, animate-fade-in + auto-shake on error)
- `/register/` — Student register (3-step Khan V3 wizard, 5-level jenjang pills)
- `/forgot-password/` — Student forgot password (WhatsApp deeplink with pre-filled username)
- `/guru/login/` — Teacher login (Notion clean white card)
- `/guru/register/` — Teacher register (3-step Notion V1 wizard, minimal animations)
- `/guru/forgot-password/` — Teacher forgot password (numbered steps + WhatsApp deeplink)
- `/admin/login/` — Admin login (dark theme `#111827`; successful login writes `ActivityLog(action='ADMIN_LOGIN', ip_address=…)`)

## Authentication
- `/logout/` — POST only; clears session + flash message + redirect to `/`
- `/waiting/` — Pending approval status (animate-fade-up card + animated pulse-ring on the clock icon + 3-step timeline)
- `/django-admin/` — Django built-in admin (developer use only — moved from `/admin/` to free that prefix for the custom admin portal)

## Dashboards (login required)
- `/dashboard/router/` — Auto-redirect based on role
- `/dashboard/student/` — Student dashboard ✅ (Khan V3 — discovery-focused: hero announcement, KPI stats, active class mini cards, best teacher of the month, popular + new classes, today + journal)
- `/dashboard/teacher/` — Teacher dashboard ✅ (Notion V2 — work-focused: greeting + CTA, 4 KPIs, "Sesi Hari Ini" priority, to-do list, kelas table, siswa perlu perhatian)
- `/dashboard/admin/` — Admin dashboard 🔴 (TBD — not yet redesigned)

## Student
- `/classes/` — Browse classes (filtered by student level)
- `/classes/<id>/` — Class detail
- `/my-classes/` — My enrolled classes
- `/my-classes/<id>/sessions/` — Session booking per class
- `/my-grades/` — My grades (HIDDEN — shows monthly score instead)
- `/my-monthly-score/` — Monthly aggregated score (NEW UI)
- `/my-attendance/` — My attendance per class
- `/my-schedule/classes/` — Weekly schedule (operating hours)
- `/my-schedule/sessions/` — Weekly schedule (actual sessions)
- `/my-progress/<id>/` — Progress report per class
- `/teachers/` — Browse teachers
- `/teachers/<id>/` — Teacher public profile
- `/rate/<enrollment_id>/` — Rate teacher + class after completion
- `/notifications/` — NEW: notification inbox
- `/journals/` — NEW: monthly journal view (from teacher)
- `/materials/` — NEW: course materials list

## Teacher

### See-All pages (NEW — paginated + filterable, all ✅)
- `/teacher/students/` — All students enrolled in teacher's classes (paginated 25/page; search by name/username/school; filter by status / level / class)
- `/teacher/classes/` — All teacher's classes
- `/teacher/sessions/` — All teacher's sessions (paginated 25/page; filter by class / status / date range)

### Class & session management
- `/teacher/classes/create/` — Create new class
- `/teacher/classes/<id>/edit/` — Edit class
- `/teacher/classes/<id>/students/` — Students enrolled
- `/teacher/classes/<id>/sessions/` — Sessions list
- `/teacher/sessions/create/<id>/` — Create session
- `/teacher/sessions/<id>/edit/` — Edit session
- `/teacher/sessions/<id>/attendance/` — Mark attendance
- `/teacher/classes/<id>/grades/` — Grade management
- `/teacher/grades/create/` — Add/edit grade
- `/teacher/ratings/` — My ratings (split: teacher + class)
- `/teacher/schedule/classes/` — My class schedule
- `/teacher/schedule/sessions/` — My sessions schedule
- `/teacher/notifications/` — NEW
- `/teacher/journals/<enrollment_id>/` — NEW: write monthly journal
- `/teacher/notes/<session_id>/` — NEW: session notes
- `/teacher/materials/upload/` — NEW: upload course material

## Admin
- `/admin-panel/pending-users/` — Approve/reject users
- `/admin-panel/users/` — Manage users (CRUD)
- `/admin-panel/classes/` — Manage all classes
- `/admin-panel/subjects/` — Subjects CRUD
- `/admin-panel/categories/` — Categories CRUD
- `/admin-panel/periods/` — Academic periods (quarter or semester)
- `/admin-panel/enrollments/` — Manage enrollments
- `/admin-panel/grades/` — All grades
- `/admin-panel/ratings/` — All ratings (teacher + class)
- `/admin-panel/logs/` — Activity logs (with IP)
- `/admin-panel/schedule/classes/` — Master schedule (all teachers)
- `/admin-panel/schedule/sessions/` — Master sessions
- `/admin-panel/announcements/` — Manage announcements
- `/admin-panel/notifications/` — NEW: manage notifications
- `/admin-panel/billing/invoices/` — NEW: invoices (when payment enabled)
- `/admin-panel/billing/payments/` — NEW: payments
- `/admin-panel/billing/refunds/` — NEW: refunds

## Shared (authenticated)
- `/profile/` — View profile
- `/profile/edit/` — Edit profile
- `/profile/change-password/` — Change password

## Error pages
- 404, 500, 403 custom templates
