from django.contrib import admin

from .models import Grade


@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    list_display = (
        'get_student', 'get_kelas', 'grade_type', 'score', 'session', 'graded_at',
    )
    list_filter = ('grade_type', 'enrollment__kelas__level')
    search_fields = (
        'enrollment__student__first_name',
        'enrollment__student__last_name',
        'enrollment__kelas__name',
    )
    raw_id_fields = ('enrollment', 'session')
    readonly_fields = ('graded_at', 'updated_at')
    ordering = ('-graded_at',)

    @admin.display(description='Siswa', ordering='enrollment__student__last_name')
    def get_student(self, obj):
        return obj.enrollment.student.get_full_name()

    @admin.display(description='Kelas', ordering='enrollment__kelas__name')
    def get_kelas(self, obj):
        return obj.enrollment.kelas.name
