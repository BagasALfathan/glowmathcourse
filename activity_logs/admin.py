from django.contrib import admin
from .models import ActivityLog


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'action', 'target_type', 'target_id', 'created_at']
    list_filter = ['action', 'target_type']
    search_fields = ['user__first_name', 'user__last_name', 'user__username']
    readonly_fields = ['user', 'action', 'target_type', 'target_id', 'created_at']
    ordering = ['-created_at']
