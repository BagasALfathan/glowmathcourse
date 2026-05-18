import os

from django.conf import settings
from django.db import models


class FileType(models.TextChoices):
    PDF = 'PDF', 'PDF'
    IMAGE = 'IMAGE', 'Gambar'
    VIDEO = 'VIDEO', 'Video'
    DOC = 'DOC', 'Dokumen'
    OTHER = 'OTHER', 'Lainnya'


_EXT_TO_TYPE = {
    '.pdf': FileType.PDF,
    '.jpg': FileType.IMAGE, '.jpeg': FileType.IMAGE,
    '.png': FileType.IMAGE, '.gif': FileType.IMAGE, '.webp': FileType.IMAGE,
    '.mp4': FileType.VIDEO, '.mov': FileType.VIDEO, '.avi': FileType.VIDEO,
    '.mkv': FileType.VIDEO, '.webm': FileType.VIDEO,
    '.doc': FileType.DOC, '.docx': FileType.DOC,
    '.xls': FileType.DOC, '.xlsx': FileType.DOC,
    '.ppt': FileType.DOC, '.pptx': FileType.DOC,
    '.txt': FileType.DOC,
}


def detect_file_type(filename: str) -> str:
    ext = os.path.splitext(filename or '')[1].lower()
    return _EXT_TO_TYPE.get(ext, FileType.OTHER)


class CourseMaterial(models.Model):
    kelas = models.ForeignKey(
        'academics.Kelas',
        on_delete=models.CASCADE,
        related_name='materials',
        db_index=True,
    )
    session = models.ForeignKey(
        'sessions_app.Session',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='materials',
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='uploaded_materials',
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    file = models.FileField(upload_to='course_materials/%Y/%m/')
    file_type = models.CharField(
        max_length=10, choices=FileType.choices, default=FileType.OTHER, blank=True,
    )
    file_size = models.PositiveIntegerField(default=0)
    is_visible = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Materi Pembelajaran'
        verbose_name_plural = 'Materi Pembelajaran'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['kelas']),
        ]

    def save(self, *args, **kwargs):
        if self.file:
            if not self.file_type:
                self.file_type = detect_file_type(self.file.name)
            try:
                self.file_size = self.file.size
            except Exception:
                pass
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title
