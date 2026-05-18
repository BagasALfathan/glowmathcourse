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
