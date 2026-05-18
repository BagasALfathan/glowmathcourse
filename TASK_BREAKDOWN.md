# Task Breakdown — Current Status

> **Last reviewed:** 2026-05-18.

## ✅ COMPLETED

### Phase 0 — Foundation (Days 1–21)
- Django setup, 15-table ERD v1, 65 functional pages
- HTMX search, charts, exports
- Approval flow with WhatsApp deeplink
- Time-aware logic (schedule overlap, auto-close expired classes)

### Phase 1 — Database Upgrade (ERD v4)
- ERD v1 → v4 migration (26 tables)
- 11 new tables in 4 new apps: notifications, course_materials, journals (×2), ratings (split into Teacher + Class), billing (×3)
- Field additions on existing tables (User.phone, StudentProfile.dob/gender, TeacherProfile.hourly_rate/bank_account, AdminProfile.department, etc.)
- **TK + UMUM** levels added to all level fields (StudentProfile, TeacherJenjang, Kelas)
- Backward-compat `@property` shims (`Kelas.teacher`, `Enrollment.student`)
- 3 named test users via `create_test_users`
- Realistic data seeders: `populate_rafael` (UMUM student) + `populate_trista` (5-class teacher across SD/SMP/SMA/UMUM)

### Phase 2 — Auth Redesign
- 3 login portals (siswa mint / guru clean / admin dark) at `/`, `/guru/login/`, `/admin/login/`
- 2 register wizards with 5-level jenjang pills
- 2 forgot-password pages with WhatsApp deeplink
- Waiting / pending-approval page with animated pulse + timeline
- Role-strict authentication (cross-portal login → friendly redirect message)
- Admin login → `ActivityLog(ip, user_agent)`
- Emerald `#10b981` theme replaced the old teal

### Phase 3 — UI Redesign (in progress — see below for what's done vs remaining)

**Done:**
- [x] Shared `animations.css` utility (fade-in, fade-up, slide, shake, pulse-glow, spinner, success-pop, card-hover-lift/border, step-circle-active)
- [x] Register pages with step transitions + spinner + auto-shake on validation
- [x] **Student Dashboard** (Khan V3 — hero announcement, KPI stats, active classes, best teacher of the month, popular + new, today + journal)
- [x] **Teacher Dashboard** (Notion V2 — greeting + CTA, 4 KPIs, "Sesi Hari Ini" priority, to-do list, kelas table with mobile-card fallback, siswa perlu perhatian)
- [x] Sidebar collapse (desktop, localStorage-persisted) + mobile drawer (<768px)
- [x] 3 teacher see-all pages (`/teacher/students/`, `/teacher/sessions/`, `/teacher/classes/`)
- [x] Animations on all auth pages (login + register + forgot + waiting)
- [x] Responsive design on both dashboards (sm / md / lg)
- [x] `update_expired_classes()` middleware (cached 5min, auto-completes past sessions + auto-closes finished classes)

## 🔄 IN PROGRESS / NEXT

### Phase 3 (continuing)
- [ ] **Admin Dashboard** (V4 Data Pro) — NEXT
- [ ] Student feature pages: browse classes, class detail, my-classes, monthly score, attendance
- [ ] Teacher CRUD: create/edit class, edit session, input grades, write monthly journal, session notes
- [ ] Admin management: approve users, manage classes/enrollments/ratings/logs, announcement editor
- [ ] New-feature pages (models ready, no UI): notifications inbox, course material upload/download, split ratings, monthly journal viewer

## ⏳ TODO

### Phase 4 — Deployment
- VPS Hostinger KVM 1 (provisioned, waiting)
- Code clone, nginx, gunicorn, PostgreSQL setup (~80% done)
- SSL with Let's Encrypt
- Custom domain `glowmathclass.com`
- Production-ready settings

### Phase 5 — Polish
- Test all flows with real users
- Performance optimization (query audits, cache tuning)
- Mobile responsive verification on remaining pages
- Print layouts for reports

## Notes on dev environment

- **Dev server runs on port 8765** (not 8000 — port 8000 is held by an unrelated long-running PHP process)
- `python manage.py check` → must return "0 silenced" before deploy
- `python manage.py makemigrations --check --dry-run` → confirm no pending model changes
