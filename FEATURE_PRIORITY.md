# GlowMathCourse — Feature Priority Matrix

> MVP = must ship in weeks 1-3 | Phase 2 = after client delivery
> Locked on March 28, 2026

---

## MVP — Build First (Weeks 1-3)

### Week 1 — Foundation (~6 days)

| Feature | Effort | Days |
|---------|--------|------|
| Django project setup + settings + Tailwind config | Low | 0.5 |
| User model with role field (STUDENT, TEACHER, ADMIN) | Low | 0.5 |
| StudentProfile, TeacherProfile, AdminProfile models | Med | 0.5 |
| Login page (email + password) | Low | 0.5 |
| Student registration (form + auto-create profile) | Med | 1 |
| Teacher registration (form + auto-create profile) | Med | 0.5 |
| Role-based redirect after login (dashboard router) | Low | 0.5 |
| Base template + navbar + sidebar (responsive) | Med | 1 |
| Category, Subject, AcademicPeriod models | Low | 0.5 |
| Admin: seed data (categories, subjects, periods) | Low | 0.5 |

### Week 2 — Core Features (~6.5 days)

| Feature | Effort | Days |
|---------|--------|------|
| Kelas model + Schedule model | Med | 0.5 |
| Teacher: create class + multi-day schedule | High | 1.5 |
| Teacher: edit/delete class | Med | 0.5 |
| Student: browse classes (filtered by level) | Med | 1 |
| Student: class detail page | Low | 0.5 |
| Enrollment model + enroll logic (level match + capacity) | High | 1 |
| Student: my enrolled classes page | Low | 0.5 |
| Student: drop class | Low | 0.5 |
| Teacher: view enrolled students per class | Low | 0.5 |

### Week 3 — Sessions, Attendance, Grades (~6 days)

| Feature | Effort | Days |
|---------|--------|------|
| Session model + teacher creates sessions | Med | 0.5 |
| Attendance model + teacher marks attendance | High | 1.5 |
| Student: view own attendance | Low | 0.5 |
| Grade model + teacher inputs grades | Med | 1 |
| Student: view own grades | Low | 0.5 |
| Student + teacher dashboards (basic stats) | Med | 1 |
| Profile view + edit page | Low | 0.5 |
| Logout | Low | 0.5 hr |

**MVP Total: ~18.5 working days**

---

## Phase 2 — After MVP Ships (Week 4+)

### Enhancement Features

| Feature | Effort | Days |
|---------|--------|------|
| Rating system (student rates teacher 1-5) | Med | 1 |
| Teacher: view own ratings | Low | 0.5 |
| HTMX class filtering (by subject, day, teacher) | Med | 1 |
| HTMX inline grade editing | Med | 0.5 |
| HTMX inline attendance save | Med | 0.5 |
| Teacher/room schedule conflict detection | High | 1 |
| Admin dashboard with full stats | High | 1.5 |
| Admin: manage users (CRUD + search/filter) | Med | 1 |
| Admin: manage classes, subjects, categories | Med | 1 |
| Admin: manage academic periods | Low | 0.5 |
| Admin: manage enrollments | Med | 0.5 |
| Admin: manage grades + ratings | Low | 0.5 |
| Activity log (record who did what) | Med | 1 |
| Soft delete implementation (all 3 tables) | Med | 0.5 |
| Admin: view activity logs + filter | Med | 0.5 |

**Phase 2 Total: ~11 working days**

---

## Future / Out of Scope

| Feature | Effort | Estimate |
|---------|--------|----------|
| Payment & billing system | High | 2 weeks |
| Discount / promo codes | High | 1 week |
| Email notifications | Med | 2 days |
| SMS / WhatsApp notifications | High | 3 days |
| File uploads (report cards, certificates) | Med | 2 days |
| Multi-branch support | High | 2 weeks |

---

## Key Decisions

1. **Admin features are Phase 2** — use Django's built-in admin panel (`/admin/`) during MVP
2. **Ratings are Phase 2** — nice to have, not required to operate the bimbel
3. **HTMX enhancements are Phase 2** — MVP uses full page reloads, Phase 2 adds dynamic partial updates
4. **Activity logging is Phase 2** — the model exists but logging logic comes later
5. **Soft delete is Phase 2** — MVP uses Django's built-in admin for deletions
6. **Conflict detection is Phase 2** — teachers manage their own schedules manually in MVP
