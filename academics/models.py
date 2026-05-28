from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from accounts.models import Level, TeacherProfile


class Quarter(models.TextChoices):
    Q1 = 'Q1', 'Kuartal 1'
    Q2 = 'Q2', 'Kuartal 2'
    Q3 = 'Q3', 'Kuartal 3'
    Q4 = 'Q4', 'Kuartal 4'


class Semester(models.TextChoices):
    GANJIL = 'GANJIL', 'Ganjil'
    GENAP = 'GENAP', 'Genap'


class PeriodType(models.TextChoices):
    QUARTER = 'QUARTER', 'Kuartal'
    SEMESTER = 'SEMESTER', 'Semester'


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
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

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
    icon = models.CharField(
        max_length=10, blank=True, default='',
        help_text='Optional emoji shown on the class card. Falls back to subject_emoji filter.',
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

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
    period_type = models.CharField(
        max_length=10,
        choices=PeriodType.choices,
        default=PeriodType.QUARTER,
    )
    quarter = models.CharField(
        max_length=2, choices=Quarter.choices, blank=True,
    )
    semester = models.CharField(
        max_length=10, choices=Semester.choices, blank=True,
    )
    name = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Periode Akademik'
        verbose_name_plural = 'Periode Akademik'
        ordering = ['-year', 'quarter', 'semester']

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if self.period_type == PeriodType.QUARTER and not self.quarter:
            raise ValidationError({'quarter': 'Quarter wajib diisi untuk period_type=QUARTER.'})
        if self.period_type == PeriodType.SEMESTER and not self.semester:
            raise ValidationError({'semester': 'Semester wajib diisi untuk period_type=SEMESTER.'})


# ── Kelas ─────────────────────────────────────────────────────────────────────

class Kelas(models.Model):
    teacher_profile = models.ForeignKey(
        TeacherProfile,
        on_delete=models.PROTECT,
        related_name='taught_classes',
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.PROTECT, related_name='classes'
    )
    academic_period = models.ForeignKey(
        AcademicPeriod, on_delete=models.PROTECT, related_name='classes'
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    level = models.CharField(max_length=5, choices=Level.choices)
    start_date = models.DateField()
    end_date = models.DateField()
    capacity = models.PositiveSmallIntegerField()
    total_sessions = models.PositiveSmallIntegerField()
    price = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
    )
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
            models.Index(fields=['teacher_profile']),
            models.Index(fields=['subject']),
            models.Index(fields=['academic_period']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return self.name

    # Backward-compat: code/templates still use `kelas.teacher` to get the User
    @property
    def teacher(self):
        return self.teacher_profile.user

    def get_enrolled_count(self):
        try:
            return self.enrollments.filter(status='ACTIVE', is_deleted=False).count()
        except Exception:
            return 0

    def check_and_update_status(self):
        """Auto-close this kelas if end_date has passed. Returns True if status changed."""
        today = timezone.localdate()
        if self.end_date < today and self.status != KelasStatus.CLOSED:
            self.status = KelasStatus.CLOSED
            self.save(update_fields=['status', 'updated_at'])
            return True
        return False

    @property
    def is_expired(self):
        return self.end_date < timezone.localdate()

    @property
    def is_upcoming(self):
        return self.start_date > timezone.localdate()

    def get_schedule_display(self):
        """Return 'Senin & Rabu, 09:00–10:30' or 'Senin 09:00–10:30, Rabu 14:00–15:30'."""
        from collections import defaultdict
        schedules = sorted(self.schedules.all(), key=lambda s: s.start_time)
        if not schedules:
            return '—'
        by_time = defaultdict(list)
        order = []
        for s in schedules:
            key = (s.start_time.strftime('%H:%M'), s.end_time.strftime('%H:%M'))
            if key not in by_time:
                order.append(key)
            by_time[key].append(s.get_day_display())
        parts = []
        for key in order:
            start, end = key
            days = by_time[key]
            if len(days) > 1:
                parts.append(f"{' & '.join(days)}, {start}–{end}")
            else:
                parts.append(f"{days[0]} {start}–{end}")
        return ', '.join(parts)

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
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        verbose_name = 'Jadwal'
        verbose_name_plural = 'Jadwal'
        unique_together = [('kelas', 'day', 'start_time')]
        indexes = [models.Index(fields=['kelas'])]

    def __str__(self):
        return f'{self.kelas.name} — {self.get_day_display()} {self.start_time:%H:%M}–{self.end_time:%H:%M}'
