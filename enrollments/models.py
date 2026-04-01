from django.conf import settings
from django.db import models
from django.utils import timezone


class EnrollmentStatus(models.TextChoices):
    ACTIVE = 'ACTIVE', 'Aktif'
    COMPLETED = 'COMPLETED', 'Selesai'
    DROPPED = 'DROPPED', 'Keluar'


class Enrollment(models.Model):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='enrollments',
        db_index=True,
        limit_choices_to={'role': 'STUDENT'},
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
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    enrolled_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Pendaftaran'
        verbose_name_plural = 'Pendaftaran'
        unique_together = [('student', 'kelas')]
        indexes = [
            models.Index(fields=['student']),
            models.Index(fields=['kelas']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f'{self.student.get_full_name()} → {self.kelas.name}'

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()
