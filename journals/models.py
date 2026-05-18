from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from accounts.models import TeacherProfile


class NoteType(models.TextChoices):
    BEHAVIOR = 'BEHAVIOR', 'Perilaku'
    UNDERSTANDING = 'UNDERSTANDING', 'Pemahaman'
    PARTICIPATION = 'PARTICIPATION', 'Partisipasi'
    GENERAL = 'GENERAL', 'Umum'


class NoteVisibility(models.TextChoices):
    TEACHER_ONLY = 'TEACHER_ONLY', 'Hanya Guru'
    VISIBLE_TO_PARENT = 'VISIBLE_TO_PARENT', 'Terlihat Orang Tua'


class MonthlyJournal(models.Model):
    enrollment = models.ForeignKey(
        'enrollments.Enrollment',
        on_delete=models.CASCADE,
        related_name='monthly_journals',
        db_index=True,
    )
    month = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)],
    )
    year = models.PositiveSmallIntegerField()
    written_by_teacher = models.ForeignKey(
        TeacherProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='monthly_journals_written',
    )
    summary = models.TextField()
    topics_covered = models.TextField()
    strengths = models.TextField()
    areas_for_improvement = models.TextField()
    viewed_by_parent = models.BooleanField(default=False)
    viewed_at = models.DateTimeField(null=True, blank=True)
    parent_response = models.TextField(blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Jurnal Bulanan'
        verbose_name_plural = 'Jurnal Bulanan'
        ordering = ['-year', '-month']
        unique_together = [('enrollment', 'month', 'year')]
        indexes = [
            models.Index(fields=['enrollment']),
            models.Index(fields=['year', 'month']),
        ]

    def __str__(self):
        return f'Jurnal {self.year}-{self.month:02d} — {self.enrollment}'


class SessionNote(models.Model):
    session = models.ForeignKey(
        'sessions_app.Session',
        on_delete=models.CASCADE,
        related_name='notes',
        db_index=True,
    )
    enrollment = models.ForeignKey(
        'enrollments.Enrollment',
        on_delete=models.CASCADE,
        related_name='session_notes',
        db_index=True,
    )
    written_by_teacher = models.ForeignKey(
        TeacherProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='session_notes_written',
    )
    note_type = models.CharField(
        max_length=15, choices=NoteType.choices, default=NoteType.GENERAL,
    )
    content = models.TextField()
    visibility = models.CharField(
        max_length=20, choices=NoteVisibility.choices, default=NoteVisibility.TEACHER_ONLY,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Catatan Sesi'
        verbose_name_plural = 'Catatan Sesi'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['session', 'enrollment']),
        ]

    def __str__(self):
        return f'{self.get_note_type_display()} — {self.session} — {self.enrollment}'
