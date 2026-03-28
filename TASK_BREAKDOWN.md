# GlowMathCourse — Day-by-Day Build Plan

> 21 working days | MVP complete by Day 15 | Deploy by Day 21
> Locked on March 28, 2026

---

## Overview

| Phase | Days | Goal |
|-------|------|------|
| Week 1 (Days 1-5) | Foundation | Auth, models, layout, profiles |
| Week 2 (Days 6-10) | Core features | Classes, enrollment, scheduling |
| Week 3 (Days 11-15) | Teaching workflow | Sessions, attendance, grades → **MVP DONE** |
| Week 4 (Days 16-21) | Enhancements + deploy | Ratings, admin CRUD, HTMX, deploy |

Buffer days: Day 5, Day 10, parts of Day 20-21

---

## Week 1 — Foundation

### Day 1 — Project setup
- [ ] Create Django project: `django-admin startproject config .`
- [ ] Setup Tailwind: `python manage.py tailwind init`
- [ ] Configure settings.py (dotenv, installed apps, middleware)
- [ ] Create accounts app: `python manage.py startapp accounts`
- [ ] Custom User model with role field (STUDENT, TEACHER, ADMIN)
- [ ] StudentProfile, TeacherProfile, AdminProfile models
- [ ] Django signal: auto-create profile on user save
- [ ] First migration + create superuser
- [ ] Git init + .gitignore + first commit

**Goal:** Project runs, User + 3 profiles in DB, superuser can log into /admin/

### Day 2 — Auth pages
- [ ] Base template (base.html) with Tailwind classes
- [ ] Add HTMX + Alpine.js CDN script tags to base template
- [ ] Login page + view
- [ ] Student registration page + form (with level, school, parent info)
- [ ] Teacher registration page + form (with education, specialization)
- [ ] Logout view

**Goal:** Students and teachers can register, login, and logout

### Day 3 — Layout + role routing
- [ ] Navbar component (responsive, mobile hamburger menu)
- [ ] Sidebar component (different menu items per role, Bahasa Indonesia labels)
- [ ] @role_required decorator (accounts/decorators.py)
- [ ] Dashboard router view (auto-redirect based on role)
- [ ] Student dashboard (placeholder page)
- [ ] Teacher dashboard (placeholder page)
- [ ] Admin dashboard (placeholder page)

**Goal:** After login, each role sees their own dashboard with sidebar

### Day 4 — Academic models + seed data
- [ ] Create academics app: `python manage.py startapp academics`
- [ ] Category model
- [ ] Subject model (FK to Category)
- [ ] AcademicPeriod model
- [ ] Kelas model (with level, capacity, total_sessions, start/end date)
- [ ] Schedule model (kelas_id, day, start_time, end_time, room)
- [ ] Register all models in admin.py
- [ ] Seed script: categories (IPA, IPS, Bahasa, Umum), subjects, 1 academic period
- [ ] Migrate + verify in Django admin

**Goal:** All academic models in DB, seed data loaded, visible in /admin/

### Day 5 — Profile pages + buffer
- [ ] Profile view page (shows role-specific data)
- [ ] Profile edit page + form (edits role-specific profile)
- [ ] Catch up on any Day 1-4 overflow
- [ ] Code review + cleanup + git push

**Goal:** Week 1 complete — auth, profiles, layout, all models ready

---

## Week 2 — Classes + Enrollment

### Day 6 — Teacher creates classes
- [ ] Teacher: my classes list page (/teacher/classes/)
- [ ] Teacher: create class form with multi-day schedule (/teacher/classes/create/)
- [ ] Class card component (templates/components/_class_card.html)

**Goal:** Teachers can create classes with multi-day schedules

### Day 7 — Teacher manages classes
- [ ] Teacher: edit class page (/teacher/classes/{id}/edit/)
- [ ] Teacher: soft delete class (/teacher/classes/{id}/delete/)
- [ ] Teacher: view enrolled students per class (/teacher/classes/{id}/students/)
- [ ] Schedule grid component (templates/components/_schedule_grid.html)

**Goal:** Full teacher class management working

### Day 8 — Student browses + enrolls
- [ ] Student: browse classes page, auto-filtered by level (/classes/)
- [ ] Student: class detail page (/classes/{id}/)
- [ ] Create enrollments app: `python manage.py startapp enrollments`
- [ ] Enrollment model + migration
- [ ] Enroll view with level match + capacity check (/enroll/{kelas_id}/)

**Goal:** Students can browse classes and enroll with validation

### Day 9 — Enrollment management
- [ ] Student: my enrolled classes page (/my-classes/)
- [ ] Student: drop class functionality (/my-classes/{id}/drop/)
- [ ] Auto-update kelas status (OPEN → FULL when at capacity)
- [ ] Test enrollment edge cases (duplicate, full class, wrong level)

**Goal:** Full enrollment lifecycle working (enroll, view, drop)

### Day 10 — Buffer + polish
- [ ] Fix UI issues from week 2
- [ ] Mobile responsiveness testing
- [ ] Code cleanup + git push

**Goal:** Week 2 complete — classes + enrollment fully working

---

## Week 3 — Sessions, Attendance, Grades

### Day 11 — Sessions
- [ ] Create sessions app: `python manage.py startapp sessions`
- [ ] Session model + migration
- [ ] Teacher: session list per class (/teacher/classes/{id}/sessions/)
- [ ] Teacher: create session form (/teacher/sessions/create/{kelas_id}/)
- [ ] Session number validation (cannot exceed kelas.total_sessions)

**Goal:** Teachers can create and manage sessions per class

### Day 12-13 — Attendance (2 days)
- [ ] Attendance model + migration
- [ ] Teacher: mark attendance page — all students in one view (/teacher/sessions/{id}/attendance/)
- [ ] Attendance form logic (bulk save: PRESENT/PERMITTED/ABSENT for each student)
- [ ] Student: view own attendance summary (/my-attendance/)
- [ ] Student: attendance per class detail (/my-attendance/{kelas_id}/)

**Goal:** Full attendance workflow — teacher marks, student views

### Day 14 — Grades
- [ ] Create grades app: `python manage.py startapp grades`
- [ ] Grade model + migration
- [ ] Teacher: grade management page per class (/teacher/classes/{id}/grades/)
- [ ] Teacher: add grade form
- [ ] Teacher: edit + delete grade

**Goal:** Teachers can input, edit, and delete grades

### Day 15 — Student grades + dashboards
- [ ] Student: view all grades page (/my-grades/)
- [ ] Student: grades per class detail (/my-grades/{kelas_id}/)
- [ ] Grade table component (templates/components/_grade_table.html)
- [ ] Student dashboard: real data (enrolled count, attendance %, avg grade)
- [ ] Teacher dashboard: real data (class count, student count, next session)
- [ ] Code cleanup + git push

**Goal: MVP COMPLETE — all core features working!**

---

## Week 4 — Phase 2 Enhancements + Deploy

### Day 16-17 — Ratings + admin dashboard
- [ ] Create ratings app + Rating model
- [ ] Student: rate teacher page (/rate/{enrollment_id}/)
- [ ] Teacher: view my ratings page (/teacher/ratings/)
- [ ] Rating stars component (templates/components/_rating_stars.html)
- [ ] Admin dashboard with real stats (total students, active classes, etc.)
- [ ] Admin: manage users page with search/filter (/admin/users/)

### Day 18-19 — Admin CRUD + HTMX
- [ ] Admin: manage classes page (/admin/classes/)
- [ ] Admin: manage subjects + categories (/admin/subjects/, /admin/categories/)
- [ ] Admin: manage enrollments (/admin/enrollments/)
- [ ] Admin: manage academic periods (/admin/periods/)
- [ ] HTMX: class filtering on student browse page
- [ ] HTMX: user search/filter on admin users page
- [ ] Activity log model + log_activity() helper function
- [ ] Admin: view activity logs (/admin/logs/)

### Day 20-21 — Deploy + final polish
- [ ] Setup Railway (or VPS) + PostgreSQL database
- [ ] Configure production settings (whitenoise, gunicorn, ALLOWED_HOSTS)
- [ ] Create Procfile + requirements.txt
- [ ] Deploy to production + test
- [ ] Mobile responsive final pass (test on real phone)
- [ ] Bug fixes + edge case testing
- [ ] Create admin account for client
- [ ] Client handoff

**Goal: Project deployed, client handoff ready!**

---

## How to use this with Claude Code

Each day, open your terminal and run:
```
cd D:\coding\glowmathcourse
venv\Scripts\activate
claude
```

Then tell Claude Code what to build:
```
Today is Day 1. Read CLAUDE.md and ERD_REFERENCE.md.
Create the Django project setup, custom User model with role field,
and the three profile models (StudentProfile, TeacherProfile, AdminProfile).
Include the Django signal to auto-create profiles on user creation.
```

Work through each day's tasks in order. If you finish early, pull from the next day. If you're behind, use the buffer days to catch up.

---

## Effort Legend

- **lo** = under 30 minutes
- **md** = 1-2 hours
- **hi** = 2-3 hours
- **buffer** = catch-up time, use as needed
