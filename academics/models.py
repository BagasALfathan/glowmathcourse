from django.conf import settings
from django.db import models
from django.utils import timezone

from accounts.models import Level


class Quarter(models.TextChoices):
    Q1 = 'Q1', 'Kuartal 1'
    Q2 = 'Q2', 'Kuartal 2'
    Q3 = 'Q3', 'Kuartal 3'
    Q4 = 'Q4', 'Kuartal 4'


class Day(models.TextChoices):
    MONDAY = 'MONDAY', 'Senin'
    TUESDAY = 'TUESDAY', 'Selasa'
    WEDNESDAY = 'WEDNESDAY', 'Rabu'
    THURSDAY = 'THURSDAY', 'Kamis'
    FRIDAY = 'FRIDAY', 'Jumat'
    SATURDAY = 'SATURDAY', 'Sabtu'


class KelasStatus(models.TextChoices):
    OPEN = 'OPEN', 'Buka'
    FULL = 'FULL', 'Penuh'
    CLOSED = 'CLOSED', 'Tutup'


# ── Category ──────────────────────────────────────────────────────────────────

class Category(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Kategori'
        verbose_name_plural = 'Kategori'
        ordering = ['name']

    def __str__(self):
        return self.name


# ── Subject ───────────────────────────────────────────────────────────────────

class Subject(models.Model):
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name='subjects'
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Mata Pelajaran'
        verbose_name_plural = 'Mata Pelajaran'
        ordering = ['category', 'name']
        indexes = [models.Index(fields=['category'])]

    def __str__(self):
        return f'{self.name} ({self.category.name})'


# ── AcademicPeriod ────────────────────────────────────────────────────────────

class AcademicPeriod(models.Model):
    year = models.CharField(max_length=10)          # e.g. "2026-2027"
    quarter = models.CharField(max_length=2, choices=Quarter.choices)
    name = models.CharField(max_length=100)         # e.g. "Q1 2026-2027"
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Periode Akademik'
        verbose_name_plural = 'Periode Akademik'
        ordering = ['-year', 'quarter']
        unique_together = [('year', 'quarter')]

    def __str__(self):
        return self.name


# ── Kelas ─────────────────────────────────────────────────────────────────────

class Kelas(models.Model):
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='taught_classes',
        limit_choices_to={'role': 'TEACHER'},
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.PROTECT, related_name='classes'
    )
    academic_period = models.ForeignKey(
        AcademicPeriod, on_delete=models.PROTECT, related_name='classes'
    )
    name = models.CharField(max_length=200)
    level = models.CharField(max_length=5, choices=Level.choices)
    start_date = models.DateField()
    end_date = models.DateField()
    capacity = models.PositiveSmallIntegerField()
    total_sessions = models.PositiveSmallIntegerField()
    status = models.CharField(
        max_length=10, choices=KelasStatus.choices, default=KelasStatus.OPEN
    )
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Kelas'
        verbose_name_plural = 'Kelas'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['teacher']),
            models.Index(fields=['subject']),
            models.Index(fields=['academic_period']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return self.name

    def get_enrolled_count(self):
        try:
            return self.enrollments.filter(status='ACTIVE', is_deleted=False).count()
        except Exception:
            return 0

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()


# ── Schedule ──────────────────────────────────────────────────────────────────

class Schedule(models.Model):
    kelas = models.ForeignKey(
        Kelas, on_delete=models.CASCADE, related_name='schedules'
    )
    day = models.CharField(max_length=10, choices=Day.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()
    room = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name = 'Jadwal'
        verbose_name_plural = 'Jadwal'
        unique_together = [('kelas', 'day', 'start_time')]
        indexes = [models.Index(fields=['kelas'])]

    def __str__(self):
        return f'{self.kelas.name} — {self.get_day_display()} {self.start_time:%H:%M}–{self.end_time:%H:%M}'
