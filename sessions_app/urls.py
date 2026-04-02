from django.urls import path
from . import views

app_name = 'sessions_app'

urlpatterns = [
    path('teacher/classes/<int:pk>/sessions/', views.teacher_sessions, name='teacher_sessions'),
    path('teacher/sessions/create/<int:kelas_id>/', views.teacher_session_create, name='teacher_session_create'),
    path('teacher/sessions/<int:pk>/update-status/', views.teacher_session_update_status, name='teacher_session_update_status'),
    path('teacher/sessions/<int:pk>/attendance/', views.teacher_attendance, name='teacher_attendance'),
]
