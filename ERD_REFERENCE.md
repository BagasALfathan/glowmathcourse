# Database Schema — ERD v4 (FINAL — 26 Tables)

> **Migration status (2026-05-18):** Phase 1 ERD v4 (26 tables) + TK / UMUM level additions are COMPLETE.
> Database wiped + fresh dummy data populated. `populate_rafael` and `populate_trista` management commands seed
> the named test users with realistic data.

## Identity (4 tables)

### User
- id (PK)
- username (unique), email (unique)
- password (hash), phone (NEW: moved from profiles)
- role: STUDENT | TEACHER | ADMIN
- approval_status: PENDING | APPROVED | REJECTED
- is_active, is_deleted, deleted_at
- date_joined, created_at, updated_at

### StudentProfile (1-to-1 → User)
- user (FK unique)
- level: **TK | SD | SMP | SMA | UMUM** (5 jenjang)
- school_name, school_grade
- address
- parent_name, parent_phone
- date_of_birth (NEW), gender (NEW)
- created_at, updated_at

### TeacherProfile (1-to-1 → User)
- user (FK unique)
- education: S1 | S2 | S3
- specialization, bio
- experience_years, address
- photo (ImageField)
- hourly_rate (NEW), bank_account (NEW, encrypted)
- created_at, updated_at

### AdminProfile (1-to-1 → User)
- user (FK unique)
- department (NEW), permissions JSON (NEW)
- created_at, updated_at

## Multi-level Teaching (1 table)

### TeacherJenjang
- teacher_profile (FK)
- level: **TK | SD | SMP | SMA | UMUM** (5 jenjang) — one row per (teacher, level) the teacher can teach
- unique (teacher, level)

## Academic Structure (5 tables)

### Category
- name, description, is_active, created_at, updated_at

### Subject (FK Category)
- name, is_active, created_at, updated_at

### AcademicPeriod (NEW: supports both quarter and semester)
- name, year
- period_type: QUARTER | SEMESTER
- quarter: Q1 | Q2 | Q3 | Q4 (if QUARTER)
- semester: GANJIL | GENAP (if SEMESTER)
- start_date, end_date, is_active
- clean() validation

### Kelas (UPDATED)
- name, subject (FK), academic_period (FK)
- teacher_profile (FK → TeacherProfile, was User; @property teacher kept for compat)
- level: **TK | SD | SMP | SMA | UMUM** (5 jenjang)
- capacity, total_sessions
- start_date, end_date
- status: OPEN | FULL | CLOSED
- price (NEW): Decimal Rp per student
- description (NEW)
- is_deleted, deleted_at (soft delete)
- created_at, updated_at

### Schedule
- kelas (FK), day: MONDAY-SATURDAY
- start_time, end_time, room
- unique (kelas, day, start_time)
- = operating hours

## Sessions (1 table)

### Session (UPDATED)
- kelas (FK)
- session_number, date, start_time, end_time
- capacity, topic
- status: SCHEDULED | COMPLETED | CANCELLED
- session_type (NEW): REGULAR | MAKEUP | OPTIONAL
- meeting_url (NEW): URLField for online sessions

## Participation (2 tables)

### Enrollment (UPDATED)
- student_profile (FK → StudentProfile, was User; @property student kept for compat)
- kelas (FK)
- status: ACTIVE | COMPLETED | DROPPED
- enrolled_at
- price_at_enrollment (NEW): snapshot
- unique (student, kelas)

### SessionBooking
- enrollment (FK), session (FK)
- status: BOOKED | CANCELLED
- unique constraint
- Note: only for sessions with session_type=MAKEUP or OPTIONAL

## Records (3 tables)

### Attendance (UPDATED)
- enrollment (FK), session (FK)
- status: PRESENT | PERMITTED | ABSENT (Hadir | Izin | Alpha)
- marked_by (NEW, FK User)
- marked_at
- unique (enrollment, session)

### Grade (UPDATED)
- enrollment (FK), session (FK, nullable)
- grade_type: QUIZ | MIDTERM | FINAL | ASSIGNMENT
- score (0-100), notes
- graded_by_teacher (NEW, FK TeacherProfile)
- clean(): if grade_type IN (QUIZ, ASSIGNMENT), session_id required

### ratings/TeacherRating (NEW — split from old Rating)
- enrollment (FK unique)
- teacher_profile (FK)
- score (1-5), comment
- is_anonymous, axes (JSON for future axes)
- created_at, updated_at

### ratings/ClassRating (NEW — split from old Rating)
- enrollment (FK unique)
- kelas (FK)
- score (1-5), comment
- is_anonymous
- created_at, updated_at

## Communication (2 tables)

### Announcement (UPDATED)
- author (FK User), title, content
- target_role: ALL | STUDENT | TEACHER
- level: ALL | SD | SMP | SMA
- is_pinned, is_active
- scheduled_at (NEW), expires_at (NEW)
- created_at, updated_at

### notifications/Notification (NEW)
- user (FK)
- type: GRADE | SESSION | PAYMENT | ANNOUNCEMENT | ENROLLMENT | RATING | OTHER
- title, message, link_url
- is_read, read_at
- created_at, updated_at

## Course Materials (1 table)

### course_materials/CourseMaterial (NEW)
- session (FK, nullable), kelas (FK)
- uploaded_by (FK User)
- title, description
- file (FileField), file_type (auto), file_size (auto)
- is_visible
- created_at, updated_at

## Progress Reporting (2 tables)

### journals/MonthlyJournal (NEW)
- enrollment (FK)
- month (1-12), year
- written_by_teacher (FK TeacherProfile)
- summary, topics_covered, strengths, areas_for_improvement
- viewed_by_parent, viewed_at, parent_response
- published_at, created_at, updated_at
- unique (enrollment, month, year)

### journals/SessionNote (NEW)
- session (FK), enrollment (FK)
- written_by_teacher (FK TeacherProfile)
- note_type: BEHAVIOR | UNDERSTANDING | PARTICIPATION | GENERAL
- content, visibility: TEACHER_ONLY | VISIBLE_TO_PARENT
- created_at, updated_at

## Payment (3 tables) — Feature flag ENABLE_PAYMENT_FEATURE = False

### billing/Invoice (NEW)
- invoice_number (auto INV-YYYY-NNNNN)
- enrollment (FK)
- amount, currency (default IDR), tax_amount, discount_amount, total_amount (computed)
- status: UNPAID | PAID | OVERDUE | REFUNDED
- due_date, paid_at
- created_at, updated_at

### billing/Payment (NEW)
- invoice (FK), amount
- method: BANK_TRANSFER | EWALLET | CARD | CASH
- gateway: MIDTRANS | XENDIT | MANUAL
- transaction_id (unique), status: PENDING | SUCCESS | FAILED
- paid_at, notes
- created_at, updated_at

### billing/Refund (NEW)
- payment (FK), invoice (FK)
- amount (validate ≤ payment.amount), reason
- status: REQUESTED | APPROVED | REJECTED | PROCESSED
- requested_by (FK User), approved_by (FK User)
- approved_at, processed_at, rejection_reason
- gateway_refund_id (unique), notes
- created_at, updated_at

## Audit (1 table)

### activity_logs/ActivityLog (UPDATED)
- user (FK), action, target_type, target_id
- ip_address (NEW), user_agent (NEW)
- created_at

## Key Constraints & Rules

- Soft delete: User, Kelas, Enrollment
- @property compatibility: Kelas.teacher → teacher_profile.user, Enrollment.student → student_profile.user
- Time-aware: auto-close expired Kelas, auto-complete Enrollments when class end_date passes
- Overlap validation: schedule per teacher, session per kelas (back-to-back OK, true overlap rejected)
- Rating: 1 TeacherRating + 1 ClassRating per Enrollment max
- MonthlyJournal: 1 per (enrollment, month, year)
- Invoice: 1 per Enrollment

## Migration Status
Phase 1 (ERD v4) COMPLETE: All 26 tables migrated. Database wiped + fresh dummy data populated.
