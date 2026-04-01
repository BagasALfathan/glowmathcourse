from django.urls import path
from . import views

app_name = 'admin_panel'

urlpatterns = [
    # User approval workflow
    path('pending-users/', views.pending_users_view, name='pending_users'),
    path('pending-users/partial/', views.users_table_partial, name='users_table_partial'),
    path('pending-users/<int:user_id>/change-status/', views.change_status_view, name='change_status'),

    # Stub admin management pages (full implementations in later days)
    path('users/', views.users_list, name='users_list'),
    path('classes/', views.classes_list, name='classes_list'),
    path('subjects/', views.subjects_list, name='subjects_list'),
    path('categories/', views.categories_list, name='categories_list'),
    path('periods/', views.periods_list, name='periods_list'),
    path('enrollments/', views.enrollments_list, name='enrollments_list'),
    path('grades/', views.grades_list, name='grades_list'),
    path('ratings/', views.ratings_list, name='ratings_list'),
    path('logs/', views.logs_list, name='logs_list'),
]
