from django.contrib import admin

from .models import Rating


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ('enrollment', 'score', 'created_at')
    list_filter = ('score',)
    search_fields = (
        'enrollment__student__first_name',
        'enrollment__student__last_name',
        'enrollment__kelas__name',
    )
    readonly_fields = ('created_at', 'updated_at')
