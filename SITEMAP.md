# GlowMathCourse — Sitemap & Page List Per Role

> ~40 unique pages across 3 roles + public pages
> Locked on March 28, 2026

---

## Page Count Summary

| Role | Pages | Color in diagrams |
|------|-------|-------------------|
| Public (no login) | 3 | Gray |
| Student | 10 | Teal |
| Teacher | 13 | Coral |
| Admin | 14 | Purple |
| **Total unique** | **~40** | |

---

## Public Pages (no login required)

| # | Page | URL | Description |
|---|------|-----|-------------|
| 1 | Landing page | `/` | Welcome page, redirect to login if not authenticated |
| 2 | Login | `/login/` | Email + password login form |
| 3 | Register | `/register/` | Role selection → student or teacher registration form |

---

## Student Pages (role = STUDENT)

| # | Page | URL | Description |
|---|------|-----|-------------|
| 1 | Dashboard | `/dashboard/student/` | Overview: enrolled classes, upcoming sessions, quick stats |
| 2 | Browse classes | `/classes/` | List of available classes, auto-filtered by student level (SD/SMP/SMA) |
| 3 | Class detail | `/classes/{id}/` | Full class info: teacher, schedule, rating, enroll button |
| 4 | Enroll | `/enroll/{kelas_id}/` | POST action — enroll in a class (level match + capacity check) |
| 5 | My enrolled classes | `/my-classes/` | List of classes student is enrolled in |
| 6 | My grades | `/my-grades/` | All grades across all classes |
| 7 | Grades per class | `/my-grades/{kelas_id}/` | Detailed grades for a specific class |
| 8 | My attendance | `/my-attendance/` | Attendance summary across all classes |
| 9 | Attendance per class | `/my-attendance/{kelas_id}/` | Detailed attendance for a specific class |
| 10 | Rate teacher | `/rate/{enrollment_id}/` | Rating form (1-5 stars + comment), only after class COMPLETED |

### Shared pages (accessible by all roles)
- Profile view: `/profile/`
- Profile edit: `/profile/edit/`

---

## Teacher Pages (role = TEACHER)

| # | Page | URL | Description |
|---|------|-----|-------------|
| 1 | Dashboard | `/dashboard/teacher/` | Overview: my classes, recent attendance, upcoming sessions |
| 2 | My classes | `/teacher/classes/` | List of classes I teach |
| 3 | Create class | `/teacher/classes/create/` | Form to create new class + multi-day schedule |
| 4 | Edit class | `/teacher/classes/{id}/edit/` | Edit class details and schedule |
| 5 | Class detail | `/teacher/classes/{id}/students/` | View enrolled students for a class |
| 6 | Sessions list | `/teacher/classes/{id}/sessions/` | All sessions/meetings for a class |
| 7 | Create session | `/teacher/sessions/create/{kelas_id}/` | Form to create a new session/meeting |
| 8 | Mark attendance | `/teacher/sessions/{id}/attendance/` | Mark PRESENT/PERMITTED/ABSENT for each student |
| 9 | Grade management | `/teacher/classes/{id}/grades/` | Add, edit, delete grades for all students in a class |
| 10 | My ratings | `/teacher/ratings/` | View ratings received from students |

### Shared pages (accessible by all roles)
- Profile view: `/profile/`
- Profile edit: `/profile/edit/`

---

## Admin Pages (role = ADMIN)

| # | Page | URL | Description |
|---|------|-----|-------------|
| 1 | Dashboard | `/dashboard/admin/` | Stats overview: total students, active classes, enrollment counts |
| 2 | Manage users | `/admin/users/` | List all users with search/filter by name, role, level, school |
| 3 | User detail | `/admin/users/{id}/` | View user profile + enrollment history |
| 4 | Edit user | `/admin/users/{id}/edit/` | Edit user info and profile |
| 5 | Manage classes | `/admin/classes/` | List all classes with filter by subject, level, teacher, status |
| 6 | Manage subjects | `/admin/subjects/` | CRUD for subjects (Matematika, Fisika, etc.) |
| 7 | Manage categories | `/admin/categories/` | CRUD for categories (Science, Language, General) |
| 8 | Manage periods | `/admin/periods/` | CRUD for academic periods (Q1 2026-2027, etc.) |
| 9 | Manage enrollments | `/admin/enrollments/` | List all enrollments with filter by student, class, status |
| 10 | Manage grades | `/admin/grades/` | View and manage all grades |
| 11 | Manage ratings | `/admin/ratings/` | View all ratings |
| 12 | Activity logs | `/admin/logs/` | Audit trail: who did what, when, filter by user/action/date |

### Shared pages (accessible by all roles)
- Profile view: `/profile/`
- Profile edit: `/profile/edit/`

---

## Navigation Structure

### Student sidebar
- Beranda (Dashboard)
- Cari Kelas (Browse Classes)
- Kelas Saya (My Classes)
- Nilai Saya (My Grades)
- Kehadiran Saya (My Attendance)
- Profil (Profile)

### Teacher sidebar
- Beranda (Dashboard)
- Kelas Saya (My Classes)
- Buat Kelas (Create Class)
- Penilaian Saya (My Ratings)
- Profil (Profile)

### Admin sidebar
- Beranda (Dashboard)
- Pengguna (Users)
- Kelas (Classes)
- Mata Pelajaran (Subjects)
- Kategori (Categories)
- Periode Akademik (Academic Periods)
- Pendaftaran (Enrollments)
- Nilai (Grades)
- Rating (Ratings)
- Log Aktivitas (Activity Logs)
- Profil (Profile)

---

## Page Access Rules

- All student pages require `@role_required('STUDENT')`
- All teacher pages require `@role_required('TEACHER')`
- All admin pages require `@role_required('ADMIN')`
- Profile pages are accessible by all authenticated users
- Public pages (login, register) redirect to dashboard if already logged in
- Unauthenticated users are redirected to `/login/`
