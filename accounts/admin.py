from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User, StudentProfile, TeacherProfile, AdminProfile


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_active', 'is_deleted')
    list_filter = ('role', 'is_active', 'is_deleted')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('-date_joined',)
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Role & Status', {'fields': ('role', 'is_deleted', 'deleted_at')}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Role', {'fields': ('role',)}),
    )


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'level', 'school_name', 'school_grade', 'phone')
    list_filter = ('level',)
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'school_name')
    raw_id_fields = ('user',)


@admin.register(TeacherProfile)
class TeacherProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'education', 'specialization', 'experience_years', 'phone')
    list_filter = ('education',)
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'specialization')
    raw_id_fields = ('user',)


@admin.register(AdminProfile)
class AdminProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone')
    search_fields = ('user__username', 'user__first_name', 'user__last_name')
    raw_id_fields = ('user',)
