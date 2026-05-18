from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from accounts.models import TeacherProfile
from enrollments.models import Enrollment


class TeacherRating(models.Model):
    enrollment = models.OneToOneField(
        Enrollment,
        on_delete=models.CASCADE,
        related_name='teacher_rating',
    )
    teacher_profile = models.ForeignKey(
        TeacherProfile,
        on_delete=models.CASCADE,
        related_name='ratings_received',
    )
    score = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    comment = models.TextField(blank=True)
    is_anonymous = models.BooleanField(default=False)
    # Future: per-axis breakdown {clarity, punctuality, ...}
    axes = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Penilaian Guru'
        verbose_name_plural = 'Penilaian Guru'

    def __str__(self):
        return f'{self.enrollment} — Guru — {self.score}★'


class ClassRating(models.Model):
    enrollment = models.OneToOneField(
        Enrollment,
        on_delete=models.CASCADE,
        related_name='class_rating',
    )
    kelas = models.ForeignKey(
        'academics.Kelas',
        on_delete=models.CASCADE,
        related_name='ratings_received',
    )
    score = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    comment = models.TextField(blank=True)
    is_anonymous = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Penilaian Kelas'
        verbose_name_plural = 'Penilaian Kelas'

    def __str__(self):
        return f'{self.enrollment} — Kelas — {self.score}★'
