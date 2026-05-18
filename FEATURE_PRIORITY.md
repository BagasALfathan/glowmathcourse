# Feature Priority Matrix

> **Last reviewed:** 2026-05-18 — Phase 3 UI redesign in progress.

## ✅ COMPLETED

### Phase 1 — Database (ERD v4)
- 26-table database, all migrations applied
- 11 new tables in 4 new apps (notifications, course_materials, journals, billing) + split ratings
- **TK + UMUM** added to all level fields (StudentProfile, TeacherJenjang, Kelas)
- Backward-compat `@property` shims (`Kelas.teacher`, `Enrollment.student`)
- Dummy data generator (`generate_dummy_data`) covers all 26 tables
- Named test users via `create_test_users` / `populate_rafael` / `populate_trista`
- Activity logs with IP + user-agent tracking

### Phase 2 — Authentication & onboarding
- 3 separate login portals (siswa / guru / admin) with distinct visual styles
- 2 register wizards (siswa Khan V3 + guru Notion V1) with 5-level jenjang
- 2 forgot-password pages (WhatsApp deeplink + pre-filled message)
- Waiting / pending-approval page (animated pulse + 3-step timeline)
- Role-strict authentication (wrong portal → friendly error message)
- Admin login writes `ActivityLog(ip, user_agent)`

### Phase 3 — UI Redesign (in progress)
- **Animations.css** shared utility classes (fade-in, fade-up, slide, shake, pulse-glow, spinner, success-pop, card-hover-lift/border)
- **Student Dashboard** (Khan V3 — discovery-focused, real data)
- **Teacher Dashboard** (Notion V2 — work-focused, to-do widget)
- **Sidebar** collapse desktop (manual toggle + localStorage) + mobile drawer (<768px)
- **3 teacher See-All pages**: `/teacher/students/`, `/teacher/sessions/`, plus existing `/teacher/classes/`
- **Cached top-teachers query** (1h) on the student dashboard
- **Responsive design** on both dashboards (sm / md / lg / xl breakpoints)

## 🟡 IN PROGRESS / NEXT

### Phase 3 (continuing)
1. **Admin Dashboard** (V4 Data Pro) — NEXT
2. Student-facing pages redesign: browse classes, class detail, my-classes, monthly-score, attendance
3. Teacher CRUD redesign: create/edit class, edit session, input grades, write monthly journal, session notes
4. Admin management redesign: approve users, manage classes/enrollments/ratings/logs, announcement editor
5. New-feature pages (models exist, no UI yet): notifications inbox, course material upload/download, monthly journal write/view, split ratings UI

## ⏳ TODO

### Phase 4 — Deployment
- VPS Hostinger KVM 1 (already provisioned)
- Code clone, nginx, gunicorn, PostgreSQL setup
- SSL with Let's Encrypt
- Custom domain `glowmathclass.com`
- Production-ready settings (`DEBUG=False`, real `ALLOWED_HOSTS`)

### Phase 5 — Polish
- Real-user acceptance testing
- Performance optimization (query budgets, N+1 audits)
- Mobile responsive verification across all pages
- Print layouts for reports

## 🔮 FUTURE (post-launch)
- Payment feature (Invoice, Payment, Refund) — models migrated, gated behind `ENABLE_PAYMENT_FEATURE = False`. Integration with Midtrans or Xendit
- Email notifications (alongside WhatsApp)
- AI features (optional — homework feedback, study suggestions)

## ❌ EXPLICITLY OUT OF SCOPE
- Multi-branch support
- SMS notifications (use WhatsApp instead)
- Student file upload (no certificate upload, etc.) — exceptions: teacher profile photo, teacher course materials
- Public-facing landing/marketing page (separate site if needed)
- REST API / DRF / SPA
