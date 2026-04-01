from django.contrib import admin

from .models import Enrollment


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'kelas', 'status', 'is_deleted', 'enrolled_at')
    list_filter = ('status', 'is_deleted', 'kelas__level')
    search_fields = ('student__first_name', 'student__last_name', 'student__email', 'kelas__name')
    raw_id_fields = ('student', 'kelas')
    readonly_fields = ('enrolled_at', 'updated_at')
