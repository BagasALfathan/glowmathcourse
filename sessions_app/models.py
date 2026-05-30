from django.conf import settings
from django.db import models
from django.utils import timezone


class AttendanceStatus(models.TextChoices):
    PRESENT = 'PRESENT', 'Hadir'
    PERMITTED = 'PERMITTED', 'Izin'
    ABSENT = 'ABSENT', 'Alpha'


class SessionStatus(models.TextChoices):
    SCHEDULED = 'SCHEDULED', 'Terjadwal'
    COMPLETED = 'COMPLETED', 'Selesai'
    CANCELLED = 'CANCELLED', 'Dibatalkan'


class SessionType(models.TextChoices):
    REGULAR = 'REGULAR', 'Reguler'
    MAKEUP = 'MAKEUP', 'Pengganti'
    OPTIONAL = 'OPTIONAL', 'Opsional'


class BookingStatus(models.TextChoices):
    BOOKED = 'BOOKED', 'Terdaftar'
    CANCELLED = 'CANCELLED', 'Dibatalkan'


class BookingKind(models.TextChoices):
    """Provenance of the booking — orthogonal to BookingStatus.
    AUTO  = auto-created from class enrollment (REGULAR sessions seeded for every
            ACTIVE Enrollment in the kelas).
    PICKED = student deliberately picked this session (session-first enrollment flow).
    MAKEUP = legacy makeup/optional booking (historical rows + future MAKEUP/OPTIONAL flow).
    """
    AUTO = 'AUTO', 'Otomatis'
    PICKED = 'PICKED', 'Dipilih'
    MAKEUP = 'MAKEUP', 'Susulan'


class Session(models.Model):
    kelas = models.ForeignKey(
        'academics.Kelas',
        on_delete=models.CASCADE,
        related_name='sessions',
    )
    session_number = models.PositiveSmallIntegerField()
    date = models.DateField(db_index=True)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    topic = models.CharField(max_length=300, blank=True)
    capacity = models.PositiveSmallIntegerField(default=0)
    session_type = models.CharField(
        max_length=10,
        choices=SessionType.choices,
        default=SessionType.REGULAR,
    )
    meeting_url = models.URLField(blank=True)
    status = models.CharField(
        max_length=15,
        choices=SessionStatus.choices,
        default=SessionStatus.SCHEDULED,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Sesi'
        verbose_name_plural = 'Sesi'
        ordering = ['kelas', 'session_number']
        unique_together = [('kelas', 'session_number')]
        indexes = [
            models.Index(fields=['kelas']),
            models.Index(fields=['date']),
        ]

    @property
    def is_today(self):
        return self.date == timezone.localdate()

    @property
    def is_past(self):
        return self.date < timezone.localdate()

    @property
    def is_upcoming(self):
        return self.date > timezone.localdate()

    @property
    def booked_count(self):
        return self.bookings.filter(status=BookingStatus.BOOKED).count()

    @property
    def is_full(self):
        return self.capacity > 0 and self.booked_count >= self.capacity

    def __str__(self):
        return f'{self.kelas.name} — Pertemuan {self.session_number}'


class Attendance(models.Model):
    enrollment = models.ForeignKey(
        'enrollments.Enrollment',
        on_delete=models.CASCADE,
        related_name='attendances',
        db_index=True,
    )
    session = models.ForeignKey(
        Session,
        on_delete=models.CASCADE,
        related_name='attendances',
        db_index=True,
    )
    status = models.CharField(
        max_length=10,
        choices=AttendanceStatus.choices,
        default=AttendanceStatus.PRESENT,
    )
    marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='marked_attendances',
    )
    marked_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Kehadiran'
        verbose_name_plural = 'Kehadiran'
        unique_together = [('enrollment', 'session')]
        indexes = [
            models.Index(fields=['enrollment']),
            models.Index(fields=['session']),
        ]

    def __str__(self):
        return (
            f'{self.enrollment.student.get_full_name()} — '
            f'Pertemuan {self.session.session_number} — '
            f'{self.get_status_display()}'
        )


class SessionBooking(models.Model):
    """Universal session-level enrollment record (Phase 3R schema unlock).

    One row = "this student (via their class Enrollment) is booked into this
    specific Session". Works for ALL session types — REGULAR, MAKEUP, OPTIONAL —
    distinguished by the `kind` field.

    Two enrollment levels in the system:
      * Enrollment      = class-level   (anchors aggregate Grade / MonthlyJournal /
                                         TeacherRating / ClassRating)
      * SessionBooking  = session-level (this model — which sessions a student is in)

    Provenance via `kind`:
      * AUTO   — seeded automatically for every REGULAR session in the kelas
                 the student's Enrollment belongs to.
      * PICKED — student deliberately picked this session (session-first flow).
      * MAKEUP — legacy makeup/optional flow (historical rows).

    `status` (BOOKED / CANCELLED) is orthogonal to `kind` — `status` tracks the
    active/cancelled state of the booking; `kind` tracks how the booking arose.
    """
    enrollment = models.ForeignKey(
        'enrollments.Enrollment',
        on_delete=models.CASCADE,
        related_name='session_bookings',
        db_index=True,
    )
    session = models.ForeignKey(
        Session,
        on_delete=models.CASCADE,
        related_name='bookings',
        db_index=True,
    )
    status = models.CharField(
        max_length=10,
        choices=BookingStatus.choices,
        default=BookingStatus.BOOKED,
    )
    kind = models.CharField(
        max_length=10,
        choices=BookingKind.choices,
        default=BookingKind.PICKED,
        db_index=True,
    )
    booked_at = models.DateTimeField(auto_now_add=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Booking Pertemuan'
        verbose_name_plural = 'Booking Pertemuan'
        unique_together = [('enrollment', 'session')]
        indexes = [
            models.Index(fields=['enrollment']),
            models.Index(fields=['session']),
            models.Index(fields=['kind']),
        ]

    def __str__(self):
        return (
            f'{self.enrollment.student.get_full_name()} — '
            f'Pertemuan {self.session.session_number} — '
            f'{self.get_status_display()}'
        )

    # Read-only convenience shims so templates can do {{ booking.student }}
    # without traversing through enrollment. NEVER use these in ORM filters —
    # always filter via enrollment__student_profile__... (see PITFALLS.md).
    @property
    def student_profile(self):
        return self.enrollment.student_profile

    @property
    def student(self):
        return self.enrollment.student_profile.user

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=['is_deleted', 'deleted_at', 'updated_at'])
