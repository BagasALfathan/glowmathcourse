# Bimbel GlowMathCourse — Database Schema (ERD v7 FINAL)

> 14 tables | All English column names | SD/SMP/SMA kept as Indonesian acronyms
> Locked on March 28, 2026 — no further changes without separate discussion

---

## Tables Overview

| # | Table | Purpose | Key Relationships |
|---|-------|---------|-------------------|
| 1 | User | Login, auth, role | Base for all roles |
| 2 | StudentProfile | Level, school, parent info | One-to-one with User (STUDENT) |
| 3 | TeacherProfile | Education, bio, experience | One-to-one with User (TEACHER) |
| 4 | AdminProfile | Phone | One-to-one with User (ADMIN) |
| 5 | AcademicPeriod | Year + quarter grouping | One period has many kelas |
| 6 | Category | Subject grouping (IPA, IPS, etc.) | One category has many subjects |
| 7 | Subject | Mata pelajaran | Belongs to category |
| 8 | Kelas | Class with capacity & duration | Belongs to teacher + subject + period |
| 9 | Schedule | Day + time slots (multi-day) | Belongs to kelas |
| 10 | Session | Individual meeting/pertemuan | Belongs to kelas |
| 11 | Enrollment | Student joins a kelas | Links student to kelas (unique pair) |
| 12 | Grade | Quiz, Midterm, Final scores | Belongs to enrollment, optionally linked to session |
| 13 | Attendance | Present/Permitted/Absent per session | Links enrollment to session (unique pair) |
| 14 | Rating | Student rates teacher 1-5 | One per enrollment (unique) |
| 15 | ActivityLog | Who did what, when | Links to user |

---

## Table Definitions

### USER
```
id              int PK
first_name      string
last_name       string
email           string          unique, indexed
username        string          unique
password        string          hashed
role            enum            STUDENT | TEACHER | ADMIN    indexed
is_active       boolean         default: true
is_deleted      boolean         default: false
deleted_at      datetime        nullable
created_at      datetime
updated_at      datetime
```

### STUDENT_PROFILE
```
id              int PK
user_id         int FK          unique, one-to-one → User
level           enum            SD | SMP | SMA
school_name     string
school_grade    int             1-12
phone           string
parent_name     string
parent_phone    string
address         string
updated_at      datetime
```

### TEACHER_PROFILE
```
id              int PK
user_id         int FK          unique, one-to-one → User
education       enum            S1 | S2 | S3
specialization  string
bio             string
experience_years int
phone           string
address         string
updated_at      datetime
```

### ADMIN_PROFILE
```
id              int PK
user_id         int FK          unique, one-to-one → User
phone           string
updated_at      datetime
```

### ACADEMIC_PERIOD
```
id              int PK
year            string          "2026-2027"
quarter         enum            Q1 | Q2 | Q3 | Q4
name            string          "Q1 2026-2027"
start_date      date
end_date        date
is_active       boolean         default: false
created_at      datetime
updated_at      datetime
```

### CATEGORY
```
id              int PK
name            string          "Science", "Language", "General"
description     string          nullable
is_active       boolean         default: true
```

### SUBJECT
```
id              int PK
category_id     int FK          indexed → Category
name            string          "Mathematics", "Physics", etc.
description     string
is_active       boolean         default: true
```

### KELAS
```
id              int PK
teacher_id      int FK          indexed → User
subject_id      int FK          indexed → Subject
academic_period_id int FK       indexed → AcademicPeriod
name            string          "Mathematics Class A"
level           enum            SD | SMP | SMA
start_date      date
end_date        date
capacity        int
total_sessions  int             e.g. 4, 8, 12
status          enum            OPEN | FULL | CLOSED       indexed
is_deleted      boolean         default: false
deleted_at      datetime        nullable
created_at      datetime
updated_at      datetime
```

### SCHEDULE
```
id              int PK
kelas_id        int FK          indexed → Kelas
day             enum            MONDAY | TUESDAY | WEDNESDAY | THURSDAY | FRIDAY | SATURDAY
start_time      time
end_time        time
room            string          nullable, e.g. "Room A"
```

### SESSION
```
id              int PK
kelas_id        int FK          indexed → Kelas
session_number  int             1, 2, 3, etc.
date            date            indexed
topic           string          nullable
status          enum            SCHEDULED | COMPLETED | CANCELLED
created_at      datetime
updated_at      datetime
```

### ENROLLMENT
```
id              int PK
student_id      int FK          indexed → User
kelas_id        int FK          indexed → Kelas
status          enum            ACTIVE | COMPLETED | DROPPED    indexed
is_deleted      boolean         default: false
deleted_at      datetime        nullable
enrolled_at     datetime
updated_at      datetime

unique_together: (student_id, kelas_id)
```

### GRADE
```
id              int PK
enrollment_id   int FK          indexed → Enrollment
session_id      int FK          nullable, indexed → Session
grade_type      enum            QUIZ | MIDTERM | FINAL | ASSIGNMENT
score           decimal         0-100
notes           string          nullable
graded_at       datetime
updated_at      datetime
```

### ATTENDANCE
```
id              int PK
enrollment_id   int FK          indexed → Enrollment
session_id      int FK          indexed → Session
status          enum            PRESENT | PERMITTED | ABSENT
marked_at       datetime
updated_at      datetime

unique_together: (enrollment_id, session_id)
```

### RATING
```
id              int PK
enrollment_id   int FK          unique, indexed → Enrollment
score           int             1-5
comment         string          nullable
created_at      datetime
updated_at      datetime
```

### ACTIVITY_LOG
```
id              int PK
user_id         int FK          indexed → User
action          string          "created", "updated", "deleted"
target_type     string          "kelas", "enrollment", etc.
target_id       int
created_at      datetime        indexed (for archiving/purging)
```

---

## Constraints Summary

### DB-Level Unique Constraints
- `Enrollment`: unique_together (student_id, kelas_id)
- `Attendance`: unique_together (enrollment_id, session_id)
- `Rating`: unique (enrollment_id)
- `Schedule`: unique_together (kelas_id, day, start_time)

### View-Level Validation Rules
- **Level matching**: student_profile.level must match kelas.level on enrollment
- **Capacity check**: active enrollment count < kelas.capacity
- **Rating guard**: enrollment.status must be COMPLETED to rate
- **Grade ownership**: kelas.teacher_id must match request.user
- **Teacher conflict**: same teacher, same day, no overlapping times
- **Room conflict**: same room, same day, no overlapping times
- **Session limit**: session_number must not exceed kelas.total_sessions

### Indexes
- User: email, role
- Kelas: teacher_id, subject_id, academic_period_id, status
- Enrollment: student_id, kelas_id, status
- Session: kelas_id, date
- Grade: enrollment_id, session_id
- Attendance: enrollment_id, session_id
- Schedule: kelas_id
- ActivityLog: user_id, created_at

---

## Enum Reference (All English)

| Field | Values | Indonesian UI Label |
|-------|--------|-------------------|
| User.role | STUDENT, TEACHER, ADMIN | Siswa, Guru, Admin |
| level | SD, SMP, SMA | SD, SMP, SMA |
| Schedule.day | MONDAY-SATURDAY | Senin-Sabtu |
| Grade.grade_type | QUIZ, MIDTERM, FINAL, ASSIGNMENT | Kuis, UTS, UAS, Tugas |
| Attendance.status | PRESENT, PERMITTED, ABSENT | Hadir, Izin, Alpha |
| Enrollment.status | ACTIVE, COMPLETED, DROPPED | Aktif, Selesai, Keluar |
| Kelas.status | OPEN, FULL, CLOSED | Buka, Penuh, Tutup |
| Session.status | SCHEDULED, COMPLETED, CANCELLED | Terjadwal, Selesai, Dibatalkan |
| AcademicPeriod.quarter | Q1, Q2, Q3, Q4 | Kuartal 1-4 |

---

## Soft Delete Tables
- User (is_deleted, deleted_at)
- Kelas (is_deleted, deleted_at)
- Enrollment (is_deleted, deleted_at)

All queries must include `.filter(is_deleted=False)` by default.
