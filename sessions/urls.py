from django.urls import path
from . import views

app_name = 'sessions'

urlpatterns = [
    path('my-attendance/', views.my_attendance, name='my_attendance'),
    path('my-attendance/<int:kelas_id>/', views.my_attendance_detail, name='my_attendance_detail'),
    path('teacher/classes/<int:pk>/sessions/', views.teacher_sessions, name='teacher_sessions'),
    path('teacher/sessions/create/<int:kelas_id>/', views.teacher_session_create, name='teacher_session_create'),
    path('teacher/sessions/<int:pk>/attendance/', views.teacher_attendance, name='teacher_attendance'),
]
