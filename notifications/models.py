from django.conf import settings
from django.db import models


class NotificationType(models.TextChoices):
    GRADE = 'GRADE', 'Nilai'
    SESSION = 'SESSION', 'Sesi'
    PAYMENT = 'PAYMENT', 'Pembayaran'
    ANNOUNCEMENT = 'ANNOUNCEMENT', 'Pengumuman'
    ENROLLMENT = 'ENROLLMENT', 'Pendaftaran'
    RATING = 'RATING', 'Penilaian'
    OTHER = 'OTHER', 'Lainnya'


class Notification(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        db_index=True,
    )
    type = models.CharField(
        max_length=15, choices=NotificationType.choices, default=NotificationType.OTHER,
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    link_url = models.URLField(blank=True)
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Notifikasi'
        verbose_name_plural = 'Notifikasi'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read']),
        ]

    def __str__(self):
        return f'{self.user.username} — {self.title}'
