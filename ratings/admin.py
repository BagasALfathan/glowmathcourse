from django.contrib import admin

from .models import TeacherRating, ClassRating


@admin.register(TeacherRating)
class TeacherRatingAdmin(admin.ModelAdmin):
    list_display = ('enrollment', 'teacher_profile', 'score', 'is_anonymous', 'created_at')
    list_filter = ('score', 'is_anonymous')
    search_fields = (
        'enrollment__student_profile__user__first_name',
        'enrollment__student_profile__user__last_name',
        'enrollment__kelas__name',
        'teacher_profile__user__first_name',
        'teacher_profile__user__last_name',
    )
    readonly_fields = ('created_at', 'updated_at')


@admin.register(ClassRating)
class ClassRatingAdmin(admin.ModelAdmin):
    list_display = ('enrollment', 'kelas', 'score', 'is_anonymous', 'created_at')
    list_filter = ('score', 'is_anonymous')
    search_fields = (
        'enrollment__student_profile__user__first_name',
        'enrollment__student_profile__user__last_name',
        'kelas__name',
    )
    readonly_fields = ('created_at', 'updated_at')
