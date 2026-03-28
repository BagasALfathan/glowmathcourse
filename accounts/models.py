from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class Role(models.TextChoices):
    STUDENT = 'STUDENT', 'Siswa'
    TEACHER = 'TEACHER', 'Guru'
    ADMIN = 'ADMIN', 'Admin'


class Level(models.TextChoices):
    SD = 'SD', 'SD'
    SMP = 'SMP', 'SMP'
    SMA = 'SMA', 'SMA'


class Education(models.TextChoices):
    S1 = 'S1', 'S1'
    S2 = 'S2', 'S2'
    S3 = 'S3', 'S3'


class User(AbstractUser):
    role = models.CharField(max_length=10, choices=Role.choices, db_index=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

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
    phone = models.CharField(max_length=20, blank=True)
    parent_name = models.CharField(max_length=150, blank=True)
    parent_phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

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
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Profil Guru: {self.user.get_full_name()}'


class AdminProfile(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='admin_profile'
    )
    phone = models.CharField(max_length=20, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Profil Admin: {self.user.get_full_name()}'
