from django.urls import path

from . import views

app_name = 'announcements'

urlpatterns = [
    path('announcements/', views.announcements_list, name='list'),
    path('announcements/create/', views.announcement_create, name='create'),
    path('announcements/<int:pk>/', views.announcement_detail, name='detail'),
]
