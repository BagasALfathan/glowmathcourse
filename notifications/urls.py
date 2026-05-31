from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    path('notifications/', views.my_notifications, name='list'),
    path('notifications/<int:pk>/read/', views.mark_notification_read, name='mark_read'),
    path('notifications/mark-all-read/', views.mark_all_read, name='mark_all_read'),
]
