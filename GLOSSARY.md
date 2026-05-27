# Glossary — GlowMath Course

> **Last updated:** 2026-05-28. Domain terms used in code (English) and UI (Bahasa Indonesia). Use this when adding new strings to either side.

The hard rule from [CLAUDE.md](CLAUDE.md): **code in English, UI in Bahasa Indonesia**. This doc maps between them so we stay consistent.

---

## Core domain models

| Code (English) | UI (Indonesia) | Definition |
|---|---|---|
| `User` | Pengguna | Generic user account (student / teacher / admin), extends `AbstractUser` |
| `StudentProfile` | Profil Siswa | Per-user profile for students (level, school, parent contact) |
| `TeacherProfile` | Profil Guru | Per-user profile for teachers (specialization, bio, hourly rate, photo) |
| `AdminProfile` | Profil Admin | Per-user profile for admins (department, permissions) |
| `TeacherJenjang` | Jenjang Guru | One row per `(teacher, level)` — which levels each teacher can teach |
| `Kelas` | Kelas | A class/course offering. **NOT `Class`** (Python reserved word) |
| `Subject` | Mata Pelajaran | Subject area (Matematika, Fisika, etc.) |
| `Category` | Kategori | Subject grouping (e.g., "Akademik Umum") |
| `AcademicPeriod` | Periode Akademik | Semester or quarter (e.g., "Q2 2026") |
| `Schedule` | Jadwal | Recurring weekly schedule (day + time) per Kelas |
| `Session` | Pertemuan / Sesi | Single occurrence of a Kelas at a specific date+time |
| `SessionBooking` | Pendaftaran Sesi | Student booking for a MAKEUP or OPTIONAL session |
| `Enrollment` | Pendaftaran Kelas | Student-to-Kelas relationship (active / completed / dropped) |
| `EnrollmentWaitlist` | Waitlist | Queue for FULL classes |
| `Attendance` | Kehadiran | Student presence at a Session (hadir / izin / alpha) |
| `Grade` | Nilai | Score per assessment (quiz / UTS / UAS / tugas) |
| `MonthlyJournal` | Jurnal Bulanan | Teacher's monthly report per Enrollment |
| `SessionNote` | Catatan Sesi | Per-session note by teacher (behavior / understanding / participation) |
| `TeacherRating` | Rating Guru | Student rating of teacher (1–5 stars) |
| `ClassRating` | Rating Kelas | Student rating of the class itself (1–5 stars, separate from teacher) |
| `Announcement` | Pengumuman | Admin/teacher broadcast to users |
| `Notification` | Notifikasi | Per-user in-app notification (Phase 3D — backend only) |
| `CourseMaterial` | Materi Kelas | Teacher-uploaded file (PDF, slides, etc.) tied to Kelas/Session (Phase 3D — backend only) |
| `Invoice` / `Payment` / `Refund` | Tagihan / Pembayaran / Pengembalian Dana | Billing models — feature-flagged OFF |
| `ActivityLog` | Log Aktivitas | Audit trail of significant user actions |

---

## Jenjang (education levels)

| Code | Bahasa Indonesia | Description |
|---|---|---|
| `TK` | TK (Taman Kanak-Kanak) | Kindergarten (ages 4–6) |
| `SD` | SD (Sekolah Dasar) | Elementary (ages 7–12) |
| `SMP` | SMP (Sekolah Menengah Pertama) | Junior high (ages 13–15) |
| `SMA` | SMA (Sekolah Menengah Atas) | Senior high (ages 16–18) |
| `UMUM` | Umum | University + adult learners (UTBK prep, TOEFL, IELTS, business English) |

**Important:** the values stay as Indonesian acronyms (`'SMA'`, not `'SENIOR_HIGH'`) in BOTH code AND UI. The UI label `'Umum'` is what `Level.UMUM.label` returns; the storage value is `'UMUM'`.

---

## Status enums (canonical values + UI labels)

### `Role` (User)
| Value | UI label |
|---|---|
| `STUDENT` | Siswa |
| `TEACHER` | Guru |
| `ADMIN` | Admin |

### `ApprovalStatus` (User)
| Value | UI label |
|---|---|
| `PENDING` | Menunggu |
| `APPROVED` | Disetujui |
| `REJECTED` | Ditolak |

### `Education` (TeacherProfile)
| Value | UI label |
|---|---|
| `S1` | S1 |
| `S2` | S2 |
| `S3` | S3 |

### `Gender` (StudentProfile)
| Value | UI label |
|---|---|
| `MALE` | Laki-laki |
| `FEMALE` | Perempuan |

### `KelasStatus`
| Value | UI label |
|---|---|
| `OPEN` | Buka |
| `FULL` | Penuh |
| `CLOSED` | Tutup |

### `Day` (Schedule)
| Value | UI label |
|---|---|
| `MONDAY` | Senin |
| `TUESDAY` | Selasa |
| `WEDNESDAY` | Rabu |
| `THURSDAY` | Kamis |
| `FRIDAY` | Jumat |
| `SATURDAY` | Sabtu |

(No `SUNDAY` — operations are closed Sunday.)

### `PeriodType` / `Quarter` / `Semester` (AcademicPeriod)
| Value | UI label |
|---|---|
| `QUARTER` | Kuartal |
| `SEMESTER` | Semester |
| `Q1` / `Q2` / `Q3` / `Q4` | Q1 / Q2 / Q3 / Q4 |
| `GANJIL` | Ganjil |
| `GENAP` | Genap |

### `EnrollmentStatus`
| Value | UI label |
|---|---|
| `ACTIVE` | Aktif |
| `COMPLETED` | Selesai |
| `DROPPED` | Keluar |

### `SessionStatus`
| Value | UI label |
|---|---|
| `SCHEDULED` | Terjadwal |
| `COMPLETED` | Selesai |
| `CANCELLED` | Dibatalkan |

### `SessionType`
| Value | UI label |
|---|---|
| `REGULAR` | Reguler |
| `MAKEUP` | Pengganti |
| `OPTIONAL` | Tambahan |

### `BookingStatus` (SessionBooking)
| Value | UI label |
|---|---|
| `BOOKED` | Terbooking |
| `CANCELLED` | Dibatalkan |

### `AttendanceStatus`
| Value | UI label |
|---|---|
| `PRESENT` | Hadir |
| `PERMITTED` | Izin |
| `ABSENT` | Alpha |

> Note: the model's display label is **`Alpha`** (matches the school usage `α`). Some external sources spell it "Alpa". Use `Alpha` in UI strings to match the canonical model label.

### `GradeType`
| Value | UI label |
|---|---|
| `QUIZ` | Kuis |
| `MIDTERM` | UTS |
| `FINAL` | UAS |
| `ASSIGNMENT` | Tugas |

### `Announcement.TargetRole`
| Value | UI label |
|---|---|
| `ALL` | Semua |
| `STUDENT` | Siswa |
| `TEACHER` | Guru |

### `Announcement.TargetLevel`
| Value | UI label |
|---|---|
| `ALL` | Semua Jenjang |
| `SD` / `SMP` / `SMA` | (literal labels) |

### `NotificationType`
| Value | UI label (implied) |
|---|---|
| `GRADE` | Nilai |
| `SESSION` | Sesi |
| `PAYMENT` | Pembayaran |
| `ANNOUNCEMENT` | Pengumuman |
| `ENROLLMENT` | Pendaftaran |
| `RATING` | Rating |
| `OTHER` | Lainnya |

### `NoteType` / `NoteVisibility` (SessionNote)
| Value | UI label |
|---|---|
| `BEHAVIOR` | Perilaku |
| `UNDERSTANDING` | Pemahaman |
| `PARTICIPATION` | Partisipasi |
| `GENERAL` | Umum |
| `TEACHER_ONLY` | Hanya Guru |
| `VISIBLE_TO_PARENT` | Terlihat oleh Orang Tua |

---

## Design patterns

### Khan Playful
Khan Academy–inspired playful design. Used for **student-facing** pages.
- Color-tinted page wrapper: `bg-gradient-to-b from-{color}-50 to-gray-50 -m-6 p-4 md:p-6 min-h-screen`
- Rounded-3xl hero with rotated white emoji tile (`transform: rotate(-4deg)`)
- Confetti decorations (top-right, bottom-left, ~20–25% opacity)
- Cards with `.card-hover-lift` (translate-y on hover)
- Pastel section backgrounds (purple/yellow/blue/pink/teal/orange)
- Emoji headings ("Hai!", "Yuk", "🎒 Kelas saya")
- Friendly Indonesian tone

### Notion Clean
Notion-inspired clean look. Used for **teacher-facing** pages.
- Background: `#f9fafb` (gray-50)
- White cards, 0.5px border, rounded-xl
- Solid emerald buttons (NO gradients)
- `.card-hover-border` (border color change, no lift)
- Whitespace-heavy
- Professional Indonesian tone

### Data Pro
Admin dashboard variant. Planned for Phase 3C.
- Dense metric grids
- Sortable tables
- Activity feed sidebar
- Tab navigation
- Dark theme on admin login portal only

---

## Common acronyms

| Acronym | Full form |
|---|---|
| UTBK | Ujian Tulis Berbasis Komputer (university entrance test) |
| UTS | Ujian Tengah Semester (midterm exam) |
| UAS | Ujian Akhir Semester (final exam) |
| WA | WhatsApp |
| WIB | Waktu Indonesia Barat (Western Indonesia Time, UTC+7) |
| ERD | Entity Relationship Diagram |
| KSN | Kompetisi Sains Nasional (national science olympiad) |
| IPA | Ilmu Pengetahuan Alam (natural sciences) |
| IPS | Ilmu Pengetahuan Sosial (social sciences) |
| TOEFL | Test of English as a Foreign Language |
| IELTS | International English Language Testing System |
| EYD / PUEBI | Indonesian spelling standard |
| SD / SMP / SMA | (see Jenjang table above) |

---

## Project-specific vocabulary

| Term | Meaning |
|---|---|
| **Bimbel** | Bimbingan belajar — tutoring (the business model) |
| **GlowMath** | Brand name; "Glow" + "Math" — the bimbel |
| **3-portal auth** | Separate login pages for student / teacher / admin (at `/`, `/guru/login/`, `/admin/login/`) |
| **Race-safe enroll** | Concurrent enrollment guarded by `select_for_update()` + capacity recount in the same transaction |
| **Soft delete** | `is_deleted=True` + `deleted_at` timestamp instead of row removal. Default querysets filter `is_deleted=False`. |
| **URL shadowing** | `student/urls.py` mounted before `enrollments` + `sessions` so the student views win for `/my-classes/` and `/my-attendance/`. See [PITFALLS.md](PITFALLS.md). |
| **Khan Playful sidebar** | The student-only teal-gradient sidebar with floating active card + clickable user block + Alpine logout modal |
| **Rate prompt** | Contextual UI surfacing for unrated COMPLETED enrollments — pulse badge on `/my-classes/` card + amber banner on `/my-classes/<id>/` |
| **Hero pill** | A pill-shaped search bar inside a colorful gradient hero (used on `/teachers/` and `/classes/`) |
| **Pertemuan** | "Session" in UI — but use `Session` in code; `pertemuan` is the Bahasa label |
| **Jenjang** | Education level — model field is `level` in English, but UI label and value are TK/SD/SMP/SMA/UMUM acronyms |
| **TBD** | To Be Decided (used in this doc and roadmap) |

---

## Bahasa style guide

- **Sentence case** for headings: "Kelas saya", not "KELAS SAYA" or "Kelas Saya"
- **Use "kamu"** (informal you), not "Anda" — Khan Playful tone is friendly, not corporate
- **Emoji-friendly** in student UI; sparing in teacher UI
- **Avoid loanwords** when an Indonesian equivalent exists: "rating" stays as "rating" (loanword OK), but "homework" → "tugas"
- **Don't translate technical terms** that don't have a clean Indonesian equivalent: `password`, `email`, `username`, `logout`, `rating`, `dashboard`
