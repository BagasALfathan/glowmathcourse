from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from accounts.models import TeacherProfile


class GradeType(models.TextChoices):
    QUIZ = 'QUIZ', 'Kuis'
    MIDTERM = 'MIDTERM', 'UTS'
    FINAL = 'FINAL', 'UAS'
    ASSIGNMENT = 'ASSIGNMENT', 'Tugas'


class Grade(models.Model):
    enrollment = models.ForeignKey(
        'enrollments.Enrollment',
        on_delete=models.CASCADE,
        related_name='grades',
        db_index=True,
    )
    session = models.ForeignKey(
        'sessions_app.Session',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='grades',
        db_index=True,
    )
    grade_type = models.CharField(
        max_length=12,
        choices=GradeType.choices,
    )
    score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    notes = models.CharField(max_length=500, blank=True)
    graded_by_teacher = models.ForeignKey(
        TeacherProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='graded_entries',
    )
    graded_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Nilai'
        verbose_name_plural = 'Nilai'
        ordering = ['enrollment', 'grade_type', '-graded_at']
        indexes = [
            models.Index(fields=['enrollment']),
            models.Index(fields=['session']),
        ]

    def clean(self):
        super().clean()
        if self.grade_type in (GradeType.QUIZ, GradeType.ASSIGNMENT) and self.session_id is None:
            raise ValidationError({
                'session': f'Sesi wajib diisi untuk {self.get_grade_type_display()}.'
            })

    def __str__(self):
        return (
            f'{self.enrollment.student.get_full_name()} — '
            f'{self.get_grade_type_display()} — {self.score}'
        )
