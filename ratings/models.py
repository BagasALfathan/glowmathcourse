from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from enrollments.models import Enrollment


class Rating(models.Model):
    enrollment = models.OneToOneField(
        Enrollment,
        on_delete=models.CASCADE,
        related_name='rating',
    )
    score = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    comment = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Penilaian'
        verbose_name_plural = 'Penilaian'

    def __str__(self):
        return f'{self.enrollment} — {self.score}★'
