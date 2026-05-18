from django.contrib import admin

from .models import MonthlyJournal, SessionNote


@admin.register(MonthlyJournal)
class MonthlyJournalAdmin(admin.ModelAdmin):
    list_display = ('enrollment', 'year', 'month', 'written_by_teacher', 'viewed_by_parent', 'published_at')
    list_filter = ('year', 'month', 'viewed_by_parent')
    search_fields = (
        'enrollment__student_profile__user__first_name',
        'enrollment__student_profile__user__last_name',
        'enrollment__kelas__name',
    )
    readonly_fields = ('created_at', 'updated_at')


@admin.register(SessionNote)
class SessionNoteAdmin(admin.ModelAdmin):
    list_display = ('session', 'enrollment', 'note_type', 'visibility', 'created_at')
    list_filter = ('note_type', 'visibility')
    search_fields = (
        'enrollment__student_profile__user__first_name',
        'enrollment__student_profile__user__last_name',
        'content',
    )
    readonly_fields = ('created_at', 'updated_at')
