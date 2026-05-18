from django.db import models

from accounts.models import User


class Announcement(models.Model):
    class TargetRole(models.TextChoices):
        ALL = 'ALL', 'Semua'
        STUDENT = 'STUDENT', 'Siswa'
        TEACHER = 'TEACHER', 'Guru'

    class TargetLevel(models.TextChoices):
        ALL = 'ALL', 'Semua Jenjang'
        SD = 'SD', 'SD'
        SMP = 'SMP', 'SMP'
        SMA = 'SMA', 'SMA'

    author = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='announcements',
    )
    title = models.CharField(max_length=255)
    content = models.TextField()
    target_role = models.CharField(
        max_length=10, choices=TargetRole.choices, default=TargetRole.ALL,
    )
    level = models.CharField(
        max_length=5, choices=TargetLevel.choices, default=TargetLevel.ALL, blank=True,
    )
    is_pinned = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    scheduled_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_pinned', '-created_at']

    def __str__(self):
        return self.title
