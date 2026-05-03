from django.urls import path
from . import views

app_name = 'admin_panel'

urlpatterns = [
    # User approval workflow
    path('pending-users/', views.pending_users_view, name='pending_users'),
    path('pending-users/partial/', views.users_table_partial, name='users_table_partial'),
    path('pending-users/<int:user_id>/change-status/', views.change_status_view, name='change_status'),

    # User management
    path('users/', views.users_list, name='users_list'),
    path('users/partial/', views.users_list_partial, name='users_list_partial'),
    path('users/<int:user_id>/', views.user_detail, name='user_detail'),
    path('users/<int:user_id>/edit/', views.user_edit, name='user_edit'),
    path('users/<int:user_id>/reset-password/', views.user_reset_password, name='user_reset_password'),
    path('users/<int:user_id>/delete/', views.user_delete, name='user_delete'),
    path('users/<int:user_id>/restore/', views.user_restore, name='user_restore'),

    # Categories
    path('categories/', views.categories_list, name='categories_list'),
    path('categories/create/', views.category_create, name='category_create'),
    path('categories/<int:category_id>/edit/', views.category_edit, name='category_edit'),
    path('categories/<int:category_id>/delete/', views.category_delete, name='category_delete'),

    # Subjects
    path('subjects/', views.subjects_list, name='subjects_list'),
    path('subjects/create/', views.subject_create, name='subject_create'),
    path('subjects/<int:subject_id>/edit/', views.subject_edit, name='subject_edit'),
    path('subjects/<int:subject_id>/delete/', views.subject_delete, name='subject_delete'),

    # Academic Periods
    path('periods/', views.periods_list, name='periods_list'),
    path('periods/create/', views.period_create, name='period_create'),
    path('periods/<int:period_id>/edit/', views.period_edit, name='period_edit'),
    path('periods/<int:period_id>/set-active/', views.period_set_active, name='period_set_active'),
    path('periods/<int:period_id>/delete/', views.period_delete, name='period_delete'),

    # Classes
    path('classes/', views.classes_list, name='classes_list'),
    path('classes/partial/', views.classes_list_partial, name='classes_list_partial'),
    path('classes/<int:kelas_id>/change-status/', views.class_change_status, name='class_change_status'),
    path('classes/<int:kelas_id>/delete/', views.class_soft_delete, name='class_soft_delete'),
    path('classes/<int:kelas_id>/restore/', views.class_restore, name='class_restore'),

    # Enrollments
    path('enrollments/', views.enrollments_list, name='enrollments_list'),
    path('enrollments/partial/', views.enrollments_list_partial, name='enrollments_list_partial'),
    path('enrollments/<int:enrollment_id>/change-status/', views.enrollment_change_status, name='enrollment_change_status'),
    path('enrollments/<int:enrollment_id>/progress/', views.enrollment_progress, name='enrollment_progress'),
    path('enrollments/<int:enrollment_id>/transfer/', views.enrollment_transfer, name='enrollment_transfer'),
    path('enrollments/bulk-action/', views.bulk_action, name='bulk_action'),

    # Grades
    path('grades/', views.grades_list, name='grades_list'),
    path('grades/partial/', views.grades_list_partial, name='grades_list_partial'),

    # Ratings
    path('ratings/', views.ratings_list, name='ratings_list'),
    path('ratings/partial/', views.ratings_list_partial, name='ratings_list_partial'),

    # Activity Logs
    path('logs/', views.logs_list, name='logs_list'),
    path('logs/partial/', views.logs_list_partial, name='logs_list_partial'),

    # Schedule
    path('schedule/', views.admin_schedule, name='admin_schedule'),
    path('schedule/print/', views.admin_schedule_print, name='admin_schedule_print'),
    # Exports
    path('export/students/', views.export_students_excel, name='export_students_excel'),
    path('export/classes/', views.export_classes_excel, name='export_classes_excel'),

    # Announcements
    path('announcements/', views.announcements_list, name='announcements_list'),
    path('announcements/<int:pk>/edit/', views.announcement_edit, name='announcement_edit'),
    path('announcements/<int:pk>/delete/', views.announcement_delete, name='announcement_delete'),
    path('announcements/<int:pk>/toggle/', views.announcement_toggle, name='announcement_toggle'),
]
