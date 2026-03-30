from django.urls import path
from . import views

app_name = 'admin_panel'

urlpatterns = [
    path('pending-users/', views.pending_users_view, name='pending_users'),
    path('pending-users/partial/', views.users_table_partial, name='users_table_partial'),
    path('pending-users/<int:user_id>/change-status/', views.change_status_view, name='change_status'),
]
