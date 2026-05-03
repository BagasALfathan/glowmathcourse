from django.contrib import admin

from .models import Attendance, Session, SessionBooking


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ('kelas', 'session_number', 'date', 'topic', 'status', 'created_at')
    list_filter = ('status', 'kelas__level')
    search_fields = ('kelas__name', 'topic')
    raw_id_fields = ('kelas',)
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('kelas', 'session_number')


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('get_student', 'get_kelas', 'get_session_number', 'status', 'marked_at')
    list_filter = ('status', 'session__kelas__level')
    search_fields = (
        'enrollment__student__first_name',
        'enrollment__student__last_name',
        'session__kelas__name',
    )
    raw_id_fields = ('enrollment', 'session')
    readonly_fields = ('marked_at', 'updated_at')
    ordering = ('session__kelas', 'session__session_number', 'enrollment__student__last_name')

    @admin.display(description='Siswa', ordering='enrollment__student__last_name')
    def get_student(self, obj):
        return obj.enrollment.student.get_full_name()

    @admin.display(description='Kelas', ordering='session__kelas__name')
    def get_kelas(self, obj):
        return obj.session.kelas.name

    @admin.display(description='Pertemuan ke-', ordering='session__session_number')
    def get_session_number(self, obj):
        return obj.session.session_number


@admin.register(SessionBooking)
class SessionBookingAdmin(admin.ModelAdmin):
    list_display = ('get_student', 'get_kelas', 'get_session_number', 'status', 'booked_at')
    list_filter = ('status', 'session__kelas__level')
    search_fields = (
        'enrollment__student__first_name',
        'enrollment__student__last_name',
        'session__kelas__name',
    )
    raw_id_fields = ('enrollment', 'session')
    readonly_fields = ('booked_at', 'updated_at')

    @admin.display(description='Siswa')
    def get_student(self, obj):
        return obj.enrollment.student.get_full_name()

    @admin.display(description='Kelas')
    def get_kelas(self, obj):
        return obj.session.kelas.name

    @admin.display(description='Pertemuan ke-')
    def get_session_number(self, obj):
        return obj.session.session_number
