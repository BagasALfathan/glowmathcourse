from django.db import models


class AttendanceStatus(models.TextChoices):
    PRESENT = 'PRESENT', 'Hadir'
    PERMITTED = 'PERMITTED', 'Izin'
    ABSENT = 'ABSENT', 'Alpha'


class SessionStatus(models.TextChoices):
    SCHEDULED = 'SCHEDULED', 'Terjadwal'
    COMPLETED = 'COMPLETED', 'Selesai'
    CANCELLED = 'CANCELLED', 'Dibatalkan'


class Session(models.Model):
    kelas = models.ForeignKey(
        'academics.Kelas',
        on_delete=models.CASCADE,
        related_name='sessions',
    )
    session_number = models.PositiveSmallIntegerField()
    date = models.DateField(db_index=True)
    topic = models.CharField(max_length=300, blank=True)
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
    marked_at = models.DateTimeField(auto_now_add=True)
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
