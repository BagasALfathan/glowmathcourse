from django.contrib import admin

from .models import CourseMaterial


@admin.register(CourseMaterial)
class CourseMaterialAdmin(admin.ModelAdmin):
    list_display = ('title', 'kelas', 'session', 'file_type', 'is_visible', 'created_at')
    list_filter = ('file_type', 'is_visible')
    search_fields = ('title', 'description', 'kelas__name')
    readonly_fields = ('file_size', 'created_at', 'updated_at')
