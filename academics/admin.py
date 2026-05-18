from django.contrib import admin

from .models import Category, Subject, AcademicPeriod, Kelas, Schedule


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'subject_count']
    search_fields = ['name', 'description']
    list_filter = ['is_active']

    @admin.display(description='Jumlah Mapel')
    def subject_count(self, obj):
        return obj.subjects.count()


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'is_active']
    search_fields = ['name', 'category__name']
    list_filter = ['is_active', 'category']
    raw_id_fields = ['category']


@admin.register(AcademicPeriod)
class AcademicPeriodAdmin(admin.ModelAdmin):
    list_display = ['name', 'year', 'quarter', 'start_date', 'end_date', 'is_active']
    search_fields = ['name', 'year']
    list_filter = ['quarter', 'is_active', 'year']


class ScheduleInline(admin.TabularInline):
    model = Schedule
    extra = 1
    fields = ['day', 'start_time', 'end_time', 'room']


@admin.register(Kelas)
class KelasAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'teacher_display', 'subject', 'level', 'status',
        'capacity', 'total_sessions', 'academic_period', 'is_deleted',
    ]
    search_fields = [
        'name',
        'teacher_profile__user__first_name',
        'teacher_profile__user__last_name',
        'teacher_profile__user__username',
        'subject__name',
    ]
    list_filter = ['level', 'status', 'is_deleted', 'subject__category', 'academic_period']
    raw_id_fields = ['teacher_profile', 'subject', 'academic_period']
    inlines = [ScheduleInline]
    readonly_fields = ['created_at', 'updated_at', 'deleted_at']

    @admin.display(description='Guru', ordering='teacher_profile__user__last_name')
    def teacher_display(self, obj):
        return obj.teacher_profile.user.get_full_name()

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'teacher_profile__user', 'subject', 'subject__category', 'academic_period'
        )


@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = ['kelas', 'day', 'start_time', 'end_time', 'room']
    search_fields = ['kelas__name', 'room']
    list_filter = ['day']
    raw_id_fields = ['kelas']
