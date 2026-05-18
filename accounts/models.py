from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class Role(models.TextChoices):
    STUDENT = 'STUDENT', 'Siswa'
    TEACHER = 'TEACHER', 'Guru'
    ADMIN = 'ADMIN', 'Admin'


class ApprovalStatus(models.TextChoices):
    PENDING = 'PENDING', 'Menunggu'
    APPROVED = 'APPROVED', 'Disetujui'
    REJECTED = 'REJECTED', 'Ditolak'


class Level(models.TextChoices):
    TK = 'TK', 'TK'
    SD = 'SD', 'SD'
    SMP = 'SMP', 'SMP'
    SMA = 'SMA', 'SMA'
    UMUM = 'UMUM', 'Umum'


class Education(models.TextChoices):
    S1 = 'S1', 'S1'
    S2 = 'S2', 'S2'
    S3 = 'S3', 'S3'


class Gender(models.TextChoices):
    MALE = 'MALE', 'Laki-laki'
    FEMALE = 'FEMALE', 'Perempuan'


class User(AbstractUser):
    role = models.CharField(max_length=10, choices=Role.choices, db_index=True)
    approval_status = models.CharField(
        max_length=10,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.PENDING,
    )
    phone = models.CharField(max_length=20, blank=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['role']),
        ]

    def __str__(self):
        return f'{self.get_full_name()} ({self.role})'

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.is_active = False
        self.save()


class StudentProfile(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='student_profile'
    )
    level = models.CharField(max_length=5, choices=Level.choices, blank=True)
    school_name = models.CharField(max_length=200, blank=True)
    school_grade = models.PositiveSmallIntegerField(null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=Gender.choices, blank=True)
    parent_name = models.CharField(max_length=150, blank=True)
    parent_phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Backward-compat: phone moved to User model
    @property
    def phone(self):
        return self.user.phone

    @phone.setter
    def phone(self, value):
        self.user.phone = value or ''
        self.user.save(update_fields=['phone', 'updated_at'])

    def __str__(self):
        return f'Profil Siswa: {self.user.get_full_name()}'


class TeacherProfile(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='teacher_profile'
    )
    education = models.CharField(max_length=5, choices=Education.choices, blank=True)
    specialization = models.CharField(max_length=200, blank=True)
    bio = models.TextField(blank=True)
    experience_years = models.PositiveSmallIntegerField(default=0)
    address = models.TextField(blank=True)
    photo = models.ImageField(upload_to='teacher_photos/', null=True, blank=True)
    hourly_rate = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
    )
    # 🔒 should be encrypted at rest in production
    bank_account = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ── Jenjang helpers (read from TeacherJenjang relation) ─────────────────
    def get_jenjang_list(self):
        return [j.level for j in self.jenjang_set.all()]

    def get_jenjang_display(self):
        labels = [j.get_level_display() for j in self.jenjang_set.all()]
        return ', '.join(labels) or '—'

    # Backward-compat: code/templates that used teaches_sd/teaches_smp/teaches_sma
    @property
    def teaches_tk(self):
        return self.jenjang_set.filter(level=Level.TK).exists()

    @property
    def teaches_sd(self):
        return self.jenjang_set.filter(level=Level.SD).exists()

    @property
    def teaches_smp(self):
        return self.jenjang_set.filter(level=Level.SMP).exists()

    @property
    def teaches_sma(self):
        return self.jenjang_set.filter(level=Level.SMA).exists()

    @property
    def teaches_umum(self):
        return self.jenjang_set.filter(level=Level.UMUM).exists()

    def set_jenjang(self, levels):
        """Replace the teacher's jenjang set with the given iterable of level codes."""
        TeacherJenjang.objects.filter(teacher_profile=self).delete()
        TeacherJenjang.objects.bulk_create(
            [TeacherJenjang(teacher_profile=self, level=lvl) for lvl in dict.fromkeys(levels)]
        )

    # Backward-compat: phone moved to User model
    @property
    def phone(self):
        return self.user.phone

    @phone.setter
    def phone(self, value):
        self.user.phone = value or ''
        self.user.save(update_fields=['phone', 'updated_at'])

    def __str__(self):
        return f'Profil Guru: {self.user.get_full_name()}'


class TeacherJenjang(models.Model):
    """One row per (TeacherProfile, level) — supports multi-level teachers."""
    teacher_profile = models.ForeignKey(
        TeacherProfile, on_delete=models.CASCADE, related_name='jenjang_set'
    )
    level = models.CharField(max_length=5, choices=Level.choices)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        verbose_name = 'Jenjang Guru'
        verbose_name_plural = 'Jenjang Guru'
        unique_together = [('teacher_profile', 'level')]
        ordering = ['teacher_profile_id', 'level']

    def __str__(self):
        return f'{self.teacher_profile} — {self.get_level_display()}'


class AdminProfile(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='admin_profile'
    )
    department = models.CharField(max_length=100, blank=True)
    permissions = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Backward-compat: phone moved to User model
    @property
    def phone(self):
        return self.user.phone

    @phone.setter
    def phone(self, value):
        self.user.phone = value or ''
        self.user.save(update_fields=['phone', 'updated_at'])

    def __str__(self):
        return f'Profil Admin: {self.user.get_full_name()}'
