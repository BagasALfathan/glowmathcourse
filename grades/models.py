from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


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
    graded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Nilai'
        verbose_name_plural = 'Nilai'
        ordering = ['enrollment', 'grade_type', '-graded_at']
        indexes = [
            models.Index(fields=['enrollment']),
            models.Index(fields=['session']),
        ]

    def __str__(self):
        return (
            f'{self.enrollment.student.get_full_name()} — '
            f'{self.get_grade_type_display()} — {self.score}'
        )
