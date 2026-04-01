from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.dashboard_router, name='router'),
    path('student/', views.student_dashboard, name='student'),
    path('teacher/', views.teacher_dashboard, name='teacher'),
    path('admin/', views.admin_dashboard, name='admin'),
]
