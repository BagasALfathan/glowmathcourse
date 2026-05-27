# URL Routes Reference — GlowMath Course

> **Last regenerated:** 2026-05-23. Every URL is scanned from `<app>/urls.py` files. Re-generate after adding new routes.

This is the canonical lookup for every `{% url %}` reference and `reverse()` call. **If you're unsure of a URL name, check here before guessing.**

---

## Quick Lookup — most-used routes

| Namespace + name | Path | View |
|---|---|---|
| `dashboard:student` | `/dashboard/student/` | `dashboard_views.student_dashboard` |
| `academics:class_browse` | `/classes/` | `academics.views.class_browse` |
| `academics:class_detail` | `/classes/<pk>/` | `academics.views.class_detail` |
| `academics:teacher_list` | `/teachers/` | `academics.views.teacher_list` |
| `academics:teacher_profile` | `/teachers/<pk>/` | `academics.views.teacher_profile` |
| `academics:student_schedule` | `/my-schedule/` | `academics.views.student_schedule_redirect` |
| `student:my_classes` | `/my-classes/` | `student.views.my_classes` |
| `student:my_attendance` | `/my-attendance/` | `student.views.my_attendance` |
| `student:my_monthly_score` | `/my-monthly-score/` | `student.views.my_monthly_score` |
| `enrollments:my_class_detail` | `/my-classes/<enrollment_id>/` | `enrollments.views.my_class_detail` |
| `ratings:rate_teacher` | `/rate/<enrollment_id>/` | `ratings.views.rate_teacher` |
| `announcements:list` | `/announcements/` | `announcements.views.announcements_list` |
| `journals:my_journals` | `/journals/` | `journals.views.my_journals` |
| `accounts:profile` | `/profile/` | `accounts.views.profile_view` |
| `accounts:logout` | `/logout/` | `accounts.views.logout_view` (POST only) |
| `help` (no namespace) | `/help/` | `dashboard.views.help_view` |

---

## Per-App Routes

### `accounts:` (auth, profile, password — `accounts/urls.py`)

| Name | Path | View | Notes |
|---|---|---|---|
| `login` | `/` | `login_student_view` | Student portal landing |
| `register` | `/register/` | `register_student_view` | 3-step Khan V3 wizard |
| `forgot_password` | `/forgot-password/` | `forgot_password_student_view` | WhatsApp deeplink |
| `login_teacher` | `/guru/login/` | `login_teacher_view` | Notion clean white |
| `register_teacher` | `/guru/register/` | `register_teacher_view` | |
| `forgot_password_teacher` | `/guru/forgot-password/` | `forgot_password_teacher_view` | |
| `login_admin` | `/admin/login/` | `login_admin_view` | Dark theme `#111827` |
| `logout` | `/logout/` | `logout_view` | **POST only** (Django 5+) |
| `waiting` | `/waiting/` | `waiting_view` | Pending-approval landing |
| `waiting_legacy` | `/register/waiting/` | `waiting_view` | Legacy alias |
| `register_student` | `/register/student/` | `register_student_view` | Legacy alias |
| `profile` | `/profile/` | `profile_view` | **Canonical profile edit** (cyan Khan Playful, GET/POST) |
| `profile_settings` | `/profile/settings/` | `profile_settings_view` | **302 → `accounts:profile`** (legacy redirect) |
| `profile_edit` | `/profile/edit/` | `profile_edit_view` | Full crispy-form edit |
| `change_password` | `/profile/change-password/` | `change_password_view` | |

### `academics:` (classes, schedules, teacher directory — `academics/urls.py`)

| Name | Path | View |
|---|---|---|
| `class_browse` | `/classes/` | `class_browse` |
| `class_detail` | `/classes/<pk>/` | `class_detail` |
| `teacher_list` | `/teachers/` | `teacher_list` |
| `teacher_list_partial` | `/teachers/partial/` | `teacher_list_partial` (HTMX) |
| `teacher_profile` | `/teachers/<pk>/` | `teacher_profile` |
| `student_schedule` | `/my-schedule/` | `student_schedule_redirect` |
| `student_schedule_classes` | `/my-schedule/classes/` | `student_schedule_classes` |
| `student_schedule_sessions` | `/my-schedule/sessions/` | `student_schedule_sessions` |
| `student_schedule_print` | `/my-schedule/print/` | `student_schedule_print` |
| `teacher_schedule` | `/teacher/schedule/` | `teacher_schedule_redirect` |
| `teacher_schedule_classes` | `/teacher/schedule/classes/` | `teacher_schedule_classes` |
| `teacher_schedule_sessions` | `/teacher/schedule/sessions/` | `teacher_schedule_sessions` |
| `teacher_schedule_print` | `/teacher/schedule/print/` | `teacher_schedule_print` |
| `teacher_all_students` | `/teacher/students/` | `teacher_all_students` |
| `teacher_all_sessions` | `/teacher/sessions/` | `teacher_all_sessions` |
| `teacher_classes` | `/teacher/classes/` | `teacher_classes_list` |
| `teacher_class_create` | `/teacher/classes/create/` | `teacher_class_create` |
| `teacher_class_edit` | `/teacher/classes/<pk>/edit/` | `teacher_class_edit` |
| `teacher_class_delete` | `/teacher/classes/<pk>/delete/` | `teacher_class_delete` |
| `teacher_class_students` | `/teacher/classes/<pk>/students/` | `teacher_class_students` |
| `teacher_class_complete` | `/teacher/classes/<pk>/complete/` | `teacher_complete_class` |

### `student:` (student "see all" pages — `student/urls.py`)

⚠ Mounted BEFORE `enrollments` and `sessions` in `config/urls.py`, so the URL names `enrollments:my_classes` and `sessions:my_attendance` also reverse to these paths — but the views that ACTUALLY serve them live in `student/views.py`.

| Name | Path | View |
|---|---|---|
| `my_classes` | `/my-classes/` | `my_classes` |
| `my_attendance` | `/my-attendance/` | `my_attendance` |
| `my_monthly_score` | `/my-monthly-score/` | `my_monthly_score` |

### `enrollments:` (`enrollments/urls.py`)

| Name | Path | View | Method |
|---|---|---|---|
| `enroll` | `/enroll/<kelas_id>/` | `enroll` | POST |
| `join_waitlist` | `/classes/<kelas_id>/waitlist/` | `join_waitlist` | POST |
| `my_classes` | `/my-classes/` | shadowed by `student:my_classes` | |
| `my_class_detail` | `/my-classes/<enrollment_id>/` | `my_class_detail` | |
| `drop_class` | `/my-classes/<pk>/drop/` | `drop_class` | POST |
| `teacher_update_enrollment` | `/teacher/enrollments/<pk>/update-status/` | `teacher_update_enrollment` | POST |

### `sessions:` (student attendance — `sessions/urls.py`, mounted before `sessions_app`)

| Name | Path | View |
|---|---|---|
| `my_attendance` | `/my-attendance/` | shadowed by `student:my_attendance` |
| `my_attendance_detail` | `/my-attendance/<kelas_id>/` | `my_attendance_detail` |
| `print_my_attendance` | `/my-attendance/print/` | `print_my_attendance` |

### `sessions_app:` (sessions + attendance + bookings — `sessions_app/urls.py`)

| Name | Path |
|---|---|
| `teacher_attendance_overview` | `/teacher/attendance/` |
| `teacher_sessions` | `/teacher/classes/<pk>/sessions/` |
| `teacher_session_create` | `/teacher/sessions/create/<kelas_id>/` |
| `teacher_session_edit` | `/teacher/sessions/<pk>/edit/` |
| `teacher_session_update_status` | `/teacher/sessions/<pk>/update-status/` |
| `teacher_attendance` | `/teacher/sessions/<pk>/attendance/` |
| `export_attendance_excel` | `/teacher/classes/<pk>/export/attendance/excel/` |
| `export_attendance_pdf` | `/teacher/classes/<pk>/export/attendance/pdf/` |
| `session_detail` | `/sessions/<pk>/` |
| `student_session_list` | `/my-classes/<enrollment_id>/sessions/` |
| `student_book_session` | `/my-classes/<enrollment_id>/sessions/<session_id>/book/` |
| `student_cancel_booking` | `/my-classes/<enrollment_id>/sessions/<session_id>/cancel/` |

### `grades:` (`grades/urls.py`)

| Name | Path |
|---|---|
| `teacher_grades_overview` | `/teacher/grades/` |
| `teacher_grades` | `/teacher/classes/<pk>/grades/` |
| `teacher_grade_create` | `/teacher/grades/create/` |
| `teacher_grade_edit` | `/teacher/grades/<pk>/edit/` |
| `teacher_grade_delete` | `/teacher/grades/<pk>/delete/` |
| `teacher_grade_inline_edit` | `/teacher/grades/<pk>/inline-edit/` (HTMX) |
| `teacher_grade_inline_save` | `/teacher/grades/<pk>/inline-save/` (HTMX) |
| `export_grades_excel` | `/teacher/classes/<pk>/export/grades/excel/` |
| `export_grades_pdf` | `/teacher/classes/<pk>/export/grades/pdf/` |
| `my_grades` | `/my-grades/` |
| `my_grades_detail` | `/my-grades/<kelas_id>/` |
| `print_my_grades` | `/my-grades/print/` |
| `teacher_student_progress` | `/teacher/classes/<pk>/students/<enrollment_id>/progress/` |
| `teacher_student_progress_print` | `/teacher/classes/<pk>/students/<enrollment_id>/progress/print/` |
| `teacher_student_progress_pdf` | `/teacher/classes/<pk>/students/<enrollment_id>/progress/pdf/` |
| `student_progress` | `/my-progress/<kelas_id>/` |
| `student_progress_print` | `/my-progress/<kelas_id>/print/` |

### `ratings:` (`ratings/urls.py`)

| Name | Path | View |
|---|---|---|
| `rate_teacher` | `/rate/<enrollment_id>/` | Both TeacherRating + ClassRating, single form |
| `teacher_ratings` | `/teacher/ratings/` | Teacher's incoming ratings dashboard |

### `journals:` (student-facing only — `journals/urls.py`)

| Name | Path |
|---|---|
| `my_journals` | `/journals/` |
| `journal_detail` | `/journals/<pk>/` |

### `announcements:` (`announcements/urls.py`)

| Name | Path |
|---|---|
| `list` | `/announcements/` |
| `create` | `/announcements/create/` (teacher/admin) |
| `detail` | `/announcements/<pk>/` |

### `dashboard:` (`dashboard/urls.py`)

| Name | Path |
|---|---|
| `router` | `/dashboard/` (auto-redirect by role) |
| `student` | `/dashboard/student/` |
| `teacher` | `/dashboard/teacher/` |
| `admin` | `/dashboard/admin/` |

### Root-mounted (no namespace — `config/urls.py`)

| Name | Path | Notes |
|---|---|---|
| `help` | `/help/` | Bantuan page (Khan Playful, all roles) |

### `admin_panel:` (Phase 3C — admin CRUD — `admin_panel/urls.py`)

| Name | Path |
|---|---|
| `pending_users` | `/admin-panel/pending-users/` |
| `users_table_partial` | `/admin-panel/pending-users/partial/` (HTMX) |
| `change_status` | `/admin-panel/pending-users/<user_id>/change-status/` |
| `users_list` | `/admin-panel/users/` |
| `users_list_partial` | `/admin-panel/users/partial/` (HTMX) |
| `user_detail` | `/admin-panel/users/<user_id>/` |
| `user_edit` | `/admin-panel/users/<user_id>/edit/` |
| `user_reset_password` | `/admin-panel/users/<user_id>/reset-password/` |
| `user_delete` | `/admin-panel/users/<user_id>/delete/` |
| `user_restore` | `/admin-panel/users/<user_id>/restore/` |
| `categories_list` | `/admin-panel/categories/` |
| `category_create` | `/admin-panel/categories/create/` |
| `category_edit` | `/admin-panel/categories/<category_id>/edit/` |
| `category_delete` | `/admin-panel/categories/<category_id>/delete/` |
| `subjects_list` | `/admin-panel/subjects/` |
| `subject_create` | `/admin-panel/subjects/create/` |
| `subject_edit` | `/admin-panel/subjects/<subject_id>/edit/` |
| `subject_delete` | `/admin-panel/subjects/<subject_id>/delete/` |
| `periods_list` | `/admin-panel/periods/` |
| `period_create` | `/admin-panel/periods/create/` |
| `period_edit` | `/admin-panel/periods/<period_id>/edit/` |
| `period_set_active` | `/admin-panel/periods/<period_id>/set-active/` |
| `period_delete` | `/admin-panel/periods/<period_id>/delete/` |
| `classes_list` | `/admin-panel/classes/` |
| `classes_list_partial` | `/admin-panel/classes/partial/` (HTMX) |
| `class_change_status` | `/admin-panel/classes/<kelas_id>/change-status/` |
| `class_soft_delete` | `/admin-panel/classes/<kelas_id>/delete/` |
| `class_restore` | `/admin-panel/classes/<kelas_id>/restore/` |
| `enrollments_list` | `/admin-panel/enrollments/` |
| `enrollments_list_partial` | `/admin-panel/enrollments/partial/` (HTMX) |
| `enrollment_change_status` | `/admin-panel/enrollments/<enrollment_id>/change-status/` |
| `enrollment_progress` | `/admin-panel/enrollments/<enrollment_id>/progress/` |
| `enrollment_transfer` | `/admin-panel/enrollments/<enrollment_id>/transfer/` |
| `bulk_action` | `/admin-panel/enrollments/bulk-action/` |
| `grades_list` | `/admin-panel/grades/` |
| `grades_list_partial` | `/admin-panel/grades/partial/` (HTMX) |
| `ratings_list` | `/admin-panel/ratings/` |
| `ratings_list_partial` | `/admin-panel/ratings/partial/` (HTMX) |
| `logs_list` | `/admin-panel/logs/` |
| `logs_list_partial` | `/admin-panel/logs/partial/` (HTMX) |
| `admin_schedule` | `/admin-panel/schedule/` |
| `admin_schedule_print` | `/admin-panel/schedule/print/` |
| `export_students_excel` | `/admin-panel/export/students/` |
| `export_classes_excel` | `/admin-panel/export/classes/` |
| `announcements_list` | `/admin-panel/announcements/` |
| `announcement_edit` | `/admin-panel/announcements/<pk>/edit/` |
| `announcement_delete` | `/admin-panel/announcements/<pk>/delete/` |
| `announcement_toggle` | `/admin-panel/announcements/<pk>/toggle/` |

### Django built-in

| Path | Notes |
|---|---|
| `/django-admin/` | Django built-in admin (moved from `/admin/` to free that prefix for the custom admin portal) |
| `/robots.txt` | TemplateView |

---

## Common Pitfalls (URL-name mistakes seen in past sessions)

| ❌ Wrong (commonly assumed) | ✅ Right (actual) |
|---|---|
| `academics:browse_classes` | `academics:class_browse` |
| `accounts:browse_teachers` | `academics:teacher_list` |
| `student:my_schedule` | `academics:student_schedule` (or `_classes` / `_sessions`) |
| `journals:list` | `journals:my_journals` |
| `journals:detail` | `journals:journal_detail` |
| `ratings:rate` | `ratings:rate_teacher` |
| `accounts:profile_settings` (as canonical) | exists but **redirects** to `accounts:profile` |
| `dashboard:help` | `help` (no namespace — mounted at root) |

See [PITFALLS.md](PITFALLS.md) for the deeper rationale on each.

---

## Notes on URL shadowing (important)

The `student/` app's URLs are included BEFORE `enrollments/` and `sessions/` in `config/urls.py`:

```python
path('', include('student.urls')),       # student.views.my_classes serves /my-classes/
path('', include('academics.urls')),
path('', include('enrollments.urls')),   # enrollments.views.my_classes EXISTS but is dead code
path('', include('grades.urls')),
path('', include('sessions.urls')),      # sessions.views.my_attendance — shadowed similarly
path('', include('sessions_app.urls')),
```

This means:
- `{% url 'enrollments:my_classes' %}` → reverses to `/my-classes/` → but the VIEW that runs is `student.views.my_classes` (not `enrollments.views.my_classes`).
- `{% url 'sessions:my_attendance' %}` → reverses to `/my-attendance/` → served by `student.views.my_attendance`.

If you change behavior at `/my-classes/`, edit `student/views.py` (the active code), not `enrollments/views.py` (orphan duplicate).
