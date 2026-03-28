# GlowMathCourse — URL Routes Reference

> ~50 Django URL routes across 8 apps
> Locked on March 28, 2026
> No REST API — all server-rendered pages + HTMX partials

---

## Legend

- **GET** — full page load
- **POST** — form submission
- **HTMX** — partial HTML response (swapped into existing page)

---

## accounts/ — Auth & Profiles

| Method | URL | Description | Role |
|--------|-----|-------------|------|
| GET | `/` | Landing page / redirect to login | PUBLIC |
| GET | `/login/` | Login page | PUBLIC |
| POST | `/login/` | Process login | PUBLIC |
| GET | `/register/` | Role selection page | PUBLIC |
| GET | `/register/student/` | Student registration form | PUBLIC |
| POST | `/register/student/` | Create student + StudentProfile | PUBLIC |
| GET | `/register/teacher/` | Teacher registration form | PUBLIC |
| POST | `/register/teacher/` | Create teacher + TeacherProfile | PUBLIC |
| POST | `/logout/` | Logout and redirect to login | ALL |
| GET | `/profile/` | View own profile | ALL |
| GET | `/profile/edit/` | Edit own profile form | ALL |
| POST | `/profile/edit/` | Save profile changes | ALL |

---

## dashboard/ — Role-Based Dashboards

| Method | URL | Description | Role |
|--------|-----|-------------|------|
| GET | `/dashboard/` | Auto-redirect based on user role | ALL |
| GET | `/dashboard/student/` | Student dashboard (enrolled classes, upcoming sessions) | STUDENT |
| GET | `/dashboard/teacher/` | Teacher dashboard (my classes, recent attendance) | TEACHER |
| GET | `/dashboard/admin/` | Admin dashboard (stats, overview) | ADMIN |

---

## academics/ — Subjects, Categories, Kelas, Schedule

| Method | URL | Description | Role |
|--------|-----|-------------|------|
| GET | `/classes/` | Browse classes (auto-filtered by student level) | STUDENT |
| HTMX | `/classes/filter/` | Filter classes by subject, day, teacher | STUDENT |
| GET | `/classes/{id}/` | Class detail page (schedule, teacher, rating) | ALL |
| GET | `/teacher/classes/` | My classes list | TEACHER |
| GET | `/teacher/classes/create/` | Create new class form | TEACHER |
| POST | `/teacher/classes/create/` | Save new class + schedule slots | TEACHER |
| GET | `/teacher/classes/{id}/edit/` | Edit class form | TEACHER |
| POST | `/teacher/classes/{id}/edit/` | Save class changes | TEACHER |
| POST | `/teacher/classes/{id}/delete/` | Soft delete class | TEACHER |
| GET | `/teacher/classes/{id}/students/` | View enrolled students for a class | TEACHER |
| GET | `/admin/classes/` | Manage all classes | ADMIN |
| GET | `/admin/subjects/` | Manage subjects (CRUD) | ADMIN |
| GET | `/admin/categories/` | Manage categories (CRUD) | ADMIN |
| GET | `/admin/periods/` | Manage academic periods (CRUD) | ADMIN |

---

## enrollments/ — Class Registration

| Method | URL | Description | Role |
|--------|-----|-------------|------|
| POST | `/enroll/{kelas_id}/` | Enroll in a class (with level + capacity check) | STUDENT |
| GET | `/my-classes/` | My enrolled classes list | STUDENT |
| POST | `/my-classes/{id}/drop/` | Drop a class (soft delete enrollment) | STUDENT |
| GET | `/admin/enrollments/` | Manage all enrollments | ADMIN |
| HTMX | `/admin/enrollments/filter/` | Filter enrollments by student, class, status | ADMIN |

---

## sessions/ — Meetings & Attendance

| Method | URL | Description | Role |
|--------|-----|-------------|------|
| GET | `/teacher/classes/{id}/sessions/` | Session list for a class | TEACHER |
| GET | `/teacher/sessions/create/{kelas_id}/` | Create new session form | TEACHER |
| POST | `/teacher/sessions/create/{kelas_id}/` | Save new session | TEACHER |
| GET | `/teacher/sessions/{id}/attendance/` | Mark attendance page (all enrolled students) | TEACHER |
| POST | `/teacher/sessions/{id}/attendance/` | Save attendance for all students | TEACHER |
| HTMX | `/teacher/sessions/{id}/attendance/save/` | Inline save single student attendance | TEACHER |
| GET | `/my-attendance/` | View own attendance summary | STUDENT |
| GET | `/my-attendance/{kelas_id}/` | Attendance detail per class | STUDENT |

---

## grades/ — Grade Management

| Method | URL | Description | Role |
|--------|-----|-------------|------|
| GET | `/teacher/classes/{id}/grades/` | Grade management page (all students) | TEACHER |
| POST | `/teacher/grades/create/` | Add new grade entry | TEACHER |
| HTMX | `/teacher/grades/{id}/edit/` | Inline edit grade | TEACHER |
| POST | `/teacher/grades/{id}/delete/` | Delete grade | TEACHER |
| GET | `/my-grades/` | View all my grades | STUDENT |
| GET | `/my-grades/{kelas_id}/` | Grades per class | STUDENT |
| GET | `/admin/grades/` | Manage all grades | ADMIN |

---

## ratings/ — Teacher Ratings

| Method | URL | Description | Role |
|--------|-----|-------------|------|
| GET | `/rate/{enrollment_id}/` | Rating form (1-5 stars + comment) | STUDENT |
| POST | `/rate/{enrollment_id}/` | Submit rating | STUDENT |
| GET | `/teacher/ratings/` | View my ratings from students | TEACHER |
| GET | `/admin/ratings/` | Manage all ratings | ADMIN |

---

## Admin Management — Users & Logs

| Method | URL | Description | Role |
|--------|-----|-------------|------|
| GET | `/admin/users/` | Manage all users (students, teachers, admins) | ADMIN |
| HTMX | `/admin/users/filter/` | Filter/search users by name, level, school, role | ADMIN |
| GET | `/admin/users/{id}/` | User detail page | ADMIN |
| GET | `/admin/users/{id}/edit/` | Edit user form | ADMIN |
| POST | `/admin/users/{id}/delete/` | Soft delete user | ADMIN |
| GET | `/admin/logs/` | Activity logs list | ADMIN |
| HTMX | `/admin/logs/filter/` | Filter logs by user, action, date | ADMIN |

---

## URL Design Rules

1. **Student-facing:** clean URLs — `/my-classes/`, `/my-grades/`, `/my-attendance/`
2. **Teacher-facing:** prefixed — `/teacher/classes/`, `/teacher/grades/`
3. **Admin-facing:** prefixed — `/admin/users/`, `/admin/classes/`
4. **HTMX endpoints** return partial HTML fragments, not full pages
5. **All deletes use POST** — HTML forms only support GET and POST
6. **No `/api/` prefix** — this is NOT a REST API
7. **Role protection** via `@role_required()` decorator on every view
8. **{id} parameters** use Django's `<int:pk>` converter
