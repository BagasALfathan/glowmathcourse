from django.contrib import admin

from .models import Session


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ('kelas', 'session_number', 'date', 'topic', 'status', 'created_at')
    list_filter = ('status', 'kelas__level')
    search_fields = ('kelas__name', 'topic')
    raw_id_fields = ('kelas',)
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('kelas', 'session_number')
