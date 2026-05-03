from django.conf import settings
from django.db import models


class ActivityLog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='activity_logs',
        db_index=True,
    )
    action = models.CharField(max_length=50)       # "created", "updated", "deleted", etc.
    target_type = models.CharField(max_length=50)  # "kelas", "enrollment", "grade", etc.
    target_id = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Log Aktivitas'
        verbose_name_plural = 'Log Aktivitas'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
        ]

    def __str__(self):
        user_str = self.user.get_full_name() if self.user else 'System'
        return f'{user_str} — {self.action} {self.target_type} #{self.target_id}'
