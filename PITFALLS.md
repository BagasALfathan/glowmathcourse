# Pitfalls & Gotchas — GlowMath Course

> **Last updated:** 2026-05-23. Bugs we've hit before. Read this BEFORE writing code so we don't repeat them.

Every entry here represents real time lost on a real bug. Append new entries as we find them — the doc only stays useful if it grows.

---

## Django Templates

### ❌ Multi-line `{# ... #}` comments leak as visible text

Django `{# ... #}` is **single-line only**. If the closing `#}` is on a different line, the entire comment renders as text in the output.

```django
{# this is fine #}

{# this WILL leak as visible text
   because the close tag is on
   another line #}

{% comment %}
this is the correct multi-line form —
will not leak.
{% endcomment %}
```

**How we hit it:** added a multi-line `{# Khan Playful student sidebar … #}` block to `_nav_student.html`. The text "Khan Playful student sidebar" was visible at the top of every authenticated page until we noticed.

### ❌ URL name mismatches

Before using `{% url 'foo:bar' %}`, look it up in [URL_ROUTES.md](URL_ROUTES.md). The most common wrong-guess patterns:

| ❌ Wrong | ✅ Right |
|---|---|
| `academics:browse_classes` | `academics:class_browse` |
| `accounts:browse_teachers` | `academics:teacher_list` |
| `student:my_schedule` | `academics:student_schedule` |
| `journals:list` | `journals:my_journals` |
| `journals:detail` | `journals:journal_detail` |
| `dashboard:help` | `help` (no namespace) |

### ❌ URL path shadowing (`/my-classes/`)

`config/urls.py` mounts `student/urls.py` BEFORE `enrollments/urls.py`. Both define `/my-classes/`. The first match wins → `student.views.my_classes` runs. The `enrollments.views.my_classes` function still exists but is unreachable.

**How we hit it:** added `needs_rating` logic to `enrollments.views.my_classes` and the template didn't show the badge. Took 20 minutes to realize the view never ran. Apply the change in `student/views.py` instead.

---

## Django Models

### ❌ Race condition on Enrollment capacity

Concurrent enrollment requests can both pass the `count() < capacity` check and write past the limit. The fix is `select_for_update()` + retry pattern.

**Right pattern** (see `enrollments/views.py::enroll`):

```python
with transaction.atomic():
    kelas = Kelas.objects.select_for_update().get(pk=kelas_id, is_deleted=False)
    active_count = Enrollment.objects.filter(
        kelas=kelas, status=EnrollmentStatus.ACTIVE, is_deleted=False
    ).count()
    if active_count >= kelas.capacity:
        # raise / messages.error / redirect
        ...
    Enrollment.objects.create(...)
```

### ❌ `Class` is a Python reserved word — use `Kelas`

The model is `academics.models.Kelas`. Never write `Class`. Field FK names are `kelas` everywhere.

### ❌ Phone field lives on `User`, NOT `StudentProfile`

ERD v4 moved `phone` to the `User` model. `StudentProfile.phone` and `TeacherProfile.phone` are **`@property` shims** that proxy to `user.phone` — they read+write through.

| ❌ Wrong | ✅ Right |
|---|---|
| `user.student_profile.phone_number` | `user.phone` |
| `StudentProfile.objects.filter(phone='...')` | `User.objects.filter(phone='...')` (then `.student_profile`) |

### ❌ `TeacherJenjang` field is `level`, not `jenjang`

The model uses Indonesian acronyms (TK/SD/SMP/SMA/UMUM) as VALUES, but the FIELD name is `level` (English). Don't write `TeacherJenjang(jenjang='SMA')` — that's a `TypeError`.

```python
# ✅
TeacherJenjang.objects.create(teacher_profile=tp, level='SMA')

# ❌
TeacherJenjang.objects.create(teacher_profile=tp, jenjang='SMA')
```

### ❌ `Subject.get_or_create(name=...)` without `category` raises `IntegrityError`

`Subject` has a **non-nullable** FK to `Category`. You must pass `category=...` in `defaults` when creating.

### ❌ `Grade` requires `grade_type` enum; QUIZ+ASSIGNMENT also require `session`

The `Grade` model has no `title` field. The required enum is `grade_type` (QUIZ / MIDTERM / FINAL / ASSIGNMENT). `clean()` enforces that QUIZ and ASSIGNMENT grades have a `session` FK set.

| ❌ Wrong | ✅ Right |
|---|---|
| `Grade(title='Quiz 1', score=85)` | `Grade(grade_type='QUIZ', score=85, session=sess, enrollment=enr, graded_by_teacher=tp)` |
| `Grade(grade_type='QUIZ', session=None)` | requires `session`; for ungraded-by-session use MIDTERM or FINAL |

### ❌ `Announcement` field is `author`, not `created_by`; values are UPPERCASE

```python
# ✅
Announcement.objects.create(
    author=admin_user,
    title=..., content=...,
    target_role='ALL',  # or 'STUDENT' / 'TEACHER'
    level='ALL',        # or 'SD' / 'SMP' / 'SMA'
)

# ❌
Announcement.objects.create(created_by=admin, target_role='all', ...)
```

The model also has NO `category` field. The category filter chips on `/announcements/` (Event / Sistem / Promo) are presentational placeholders only — only `is_pinned` filters by data.

### ❌ `MonthlyJournal` minimum fields

The model has 4 required text fields beyond `summary`:

```python
MonthlyJournal.objects.create(
    enrollment=enr,
    month=5, year=2026,
    written_by_teacher=tp,         # required FK
    summary='...',
    topics_covered='...',           # required
    strengths='...',                # required
    areas_for_improvement='...',    # required
)
```

### ❌ `TeacherRating` filter via `enrollment__*`, not direct

`TeacherRating` has `enrollment` (OneToOne) + `teacher_profile` (FK). It does NOT have direct `kelas` or `student_profile` FKs.

```python
# ❌
TeacherRating.objects.filter(kelas=k, student_profile=s)

# ✅
TeacherRating.objects.filter(
    enrollment__kelas=k,
    enrollment__student_profile=s,
)
```

### ❌ `ActivityLog.created_at` is auto — don't pass it manually

```python
# ❌
ActivityLog.objects.create(user=u, action='LOGIN', created_at=timezone.now())

# ✅
ActivityLog.objects.create(user=u, action='LOGIN')
```

### ❌ Soft delete: always filter `is_deleted=False`

`User`, `Kelas`, and `Enrollment` use soft delete (`is_deleted=True` + `deleted_at`). Always add `is_deleted=False` to default querysets, or you'll see ghost rows in production.

---

## Sidebar Update Pitfalls

### ❌ Touching teacher/admin sidebar without permission

Phase 3A Khan Playful styling is **student-only**. The shared `<aside>` shell in `base.html` includes per-role partials:

- `templates/partials/_nav_student.html` — Khan Playful (touch-eligible)
- `templates/partials/_nav_teacher.html` — **OFF-LIMITS** unless task explicitly names it
- `templates/partials/_nav_admin.html` — **OFF-LIMITS** unless task explicitly names it

The student partial scopes its styling via `:has(.student-nav-marker)` so it can't leak to other roles. Don't break that scoping.

### ❌ Sidebar entries pointing to non-existent pages (404s)

Before adding a sidebar item, hit the URL once. The 4 utility entries (Pengumuman, Jurnal Bulanan, Bantuan, Logout) were each verified to render before going into the sidebar.

### ❌ Django 5+ logout requires POST

A plain `<a href="/logout/">` returns `405 Method Not Allowed`. Use:

```html
<form method="post" action="{% url 'accounts:logout' %}">
  {% csrf_token %}
  <button type="submit">Logout</button>
</form>
```

The student sidebar wraps this in an Alpine modal — the button toggles `showLogoutModal`, and the modal contains the actual POST form.

### ❌ Multi-line Django comment in `_nav_student.html` leaked text

Fixed in turn dated 2026-05-23. See "Django Templates → Multi-line comments" above for the broader pattern.

---

## Phase 3A Specific

### ❌ Sticky sidebar in Class Detail caused sync-scroll jank

Initial Class Detail design had a sticky right sidebar (info card). On long class descriptions, the right column went into ghost-scroll because content height was unequal. Final design: both columns scroll together, plus a sticky bottom CTA bar for the "Daftar" button.

### ❌ Inaccurate star ratings (`★★★★★` plain text)

A plain string `'★' * round(rating)` rounds aggressively (4.3 → 4 full stars, 4.7 → 5). The fix is a CSS overlay technique: a gray underlay of 5 stars + a gold overlay clipped to `width: (rating/5)*100%`.

**Helper:** `{% star_rating value %}` from `dashboard/templatetags/dashboard_filters.py`.

### ❌ Tailwind `text-3xl` on emoji span ineffective inside `<aside>`

When the logout modal's emoji `<span class="text-3xl leading-none">🚪</span>` rendered at browser-default size, the suspected cause was a CSS cascade override from sidebar collapsed-mode rules. Verified rule targets `.nav-item` only, not arbitrary spans — so the cause was likely browser cache (CDN-Tailwind class generation may not see a hidden modal element until first show). Hard refresh resolves; if persistent, force size via inline style: `style="font-size: 2rem; line-height: 1;"`.

---

## Management commands / dev workflow

### ❌ `runserver` on port 8000 vs 8765

CLAUDE.md mandates `python manage.py runserver 8765` because port 8000 was held by a stale PHP process during early dev. If you forget the port, links that hardcode 8765 will look broken.

### ❌ `populate_full_demo` is idempotent — `--reset` is destructive

Re-running without `--reset` will just top up missing data; safe. `--reset` deletes ALL non-superuser data first. Confirm before invoking.

### ❌ Faker is optional

`populate_full_demo` works without Faker installed but falls back to a fixed name pool. Install `faker` if you want realistic Indonesian names.

---

### ❌ Two enrollment levels — don't confuse Enrollment with SessionBooking

After the 2026-05-31 schema unlock, `SessionBooking` is now the universal
session-level enrollment record (for ALL session types, not just MAKEUP/OPTIONAL).
This creates two enrollment levels:

| Model | Level | Anchors |
|---|---|---|
| `enrollments.Enrollment` | class-level | `Grade`, `MonthlyJournal`, `TeacherRating`, `ClassRating` (unchanged — still per-class aggregates) |
| `sessions_app.SessionBooking` | session-level | `Attendance` (per session — already was) |

Rules:
- A **class-level** stat (avg grade, monthly journal) → query `Enrollment.objects.…`
- A **session-level** stat ("which students are in session X") → query `SessionBooking.objects.…`
- A student who's "enrolled in class K" has 1 Enrollment + N SessionBookings (one per REGULAR Session in K)

**ORM filter rules:**
- ❌ `SessionBooking.objects.filter(student=user)` — no `student` field on SessionBooking; that's a @property shim
- ✅ `SessionBooking.objects.filter(enrollment__student_profile__user=user)`
- ❌ `SessionBooking.objects.filter(student_profile=sp)` — same reason
- ✅ `SessionBooking.objects.filter(enrollment__student_profile=sp)`

`booking.student` and `booking.student_profile` work in TEMPLATES (read-only attribute access via the @property shim) — never in ORM lookups.

### ❌ `'sessions.Session'` FK string resolves to Django's cookie table

The project's Session model lives at `sessions_app.Session` (app_label `sessions_app`).
There's also a stale empty `sessions/models.py` whose only registered model is
**`django.contrib.sessions.models.Session`** — the built-in session-cookie storage
(`django_session` table).

| ❌ Wrong | ✅ Right |
|---|---|
| `FK('sessions.Session')` | `FK('sessions_app.Session')` |

This bites when writing FK strings in new models or migrations. Always
`sessions_app.Session`, never `sessions.Session`.

### ❌ Soft-delete on SessionBooking too

Phase 3R schema unlock added `is_deleted` + `deleted_at` + `soft_delete()` to
`SessionBooking` to match the Enrollment convention. Filter `is_deleted=False`
in default querysets — same trap as User/Kelas/Enrollment.

## Append new pitfalls here as they're discovered

<!--
Format: `### ❌ Short title`
followed by 2-4 sentences on context + the fix.
Date the entry if helpful.
-->
