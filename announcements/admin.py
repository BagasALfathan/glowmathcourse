from django.contrib import admin

from .models import Announcement


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'target_role', 'level', 'is_pinned', 'is_active', 'created_at')
    list_filter = ('target_role', 'level', 'is_pinned', 'is_active')
    search_fields = ('title', 'content')
    ordering = ('-is_pinned', '-created_at')
