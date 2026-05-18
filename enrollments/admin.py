from django.contrib import admin

from .models import Enrollment


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('student_display', 'kelas', 'status', 'is_deleted', 'enrolled_at')
    list_filter = ('status', 'is_deleted', 'kelas__level')
    search_fields = (
        'student_profile__user__first_name',
        'student_profile__user__last_name',
        'student_profile__user__email',
        'kelas__name',
    )
    raw_id_fields = ('student_profile', 'kelas')
    readonly_fields = ('enrolled_at', 'updated_at')

    @admin.display(description='Siswa', ordering='student_profile__user__last_name')
    def student_display(self, obj):
        return obj.student_profile.user.get_full_name()
