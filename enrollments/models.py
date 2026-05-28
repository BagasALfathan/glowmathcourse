from django.db import models
from django.utils import timezone

from accounts.models import StudentProfile


class EnrollmentStatus(models.TextChoices):
    ACTIVE = 'ACTIVE', 'Aktif'
    COMPLETED = 'COMPLETED', 'Selesai'
    DROPPED = 'DROPPED', 'Keluar'


class Enrollment(models.Model):
    student_profile = models.ForeignKey(
        StudentProfile,
        on_delete=models.PROTECT,
        related_name='enrollments',
        db_index=True,
    )
    kelas = models.ForeignKey(
        'academics.Kelas',
        on_delete=models.PROTECT,
        related_name='enrollments',
        db_index=True,
    )
    status = models.CharField(
        max_length=10,
        choices=EnrollmentStatus.choices,
        default=EnrollmentStatus.ACTIVE,
        db_index=True,
    )
    price_at_enrollment = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
    )
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    enrolled_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Pendaftaran'
        verbose_name_plural = 'Pendaftaran'
        constraints = [
            models.UniqueConstraint(
                fields=['student_profile', 'kelas'],
                name='uniq_enrollment_student_kelas',
            ),
        ]
        indexes = [
            models.Index(fields=['student_profile']),
            models.Index(fields=['kelas']),
            models.Index(fields=['status']),
        ]

    # Backward-compat: code/templates still use `enrollment.student` to get the User
    @property
    def student(self):
        return self.student_profile.user

    def __str__(self):
        return f'{self.student.get_full_name()} → {self.kelas.name}'

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()


class EnrollmentWaitlist(models.Model):
    """Student daftar tunggu untuk kelas yang penuh."""
    student_profile = models.ForeignKey(
        'accounts.StudentProfile',
        on_delete=models.CASCADE,
        related_name='waitlists',
    )
    kelas = models.ForeignKey(
        'academics.Kelas',
        on_delete=models.CASCADE,
        related_name='waitlists',
    )
    position = models.PositiveIntegerField(help_text='Posisi antrian (mulai dari 1)')
    created_at = models.DateTimeField(auto_now_add=True)
    notified_at = models.DateTimeField(
        null=True, blank=True,
        help_text='Kapan student dinotif slot kosong (NULL = belum dinotif).',
    )

    class Meta:
        verbose_name = 'Waitlist'
        verbose_name_plural = 'Waitlist'
        ordering = ['kelas', 'position']
        constraints = [
            models.UniqueConstraint(
                fields=['student_profile', 'kelas'],
                name='unique_waitlist_student_kelas',
            ),
        ]
        indexes = [
            models.Index(fields=['kelas', 'position']),
        ]

    def __str__(self):
        return f'{self.student_profile} → {self.kelas.name} (#{self.position})'
