from django.urls import path
from . import views

app_name = 'sessions_app'

urlpatterns = [
    path('teacher/attendance/', views.teacher_attendance_overview, name='teacher_attendance_overview'),
    path('teacher/classes/<int:pk>/sessions/', views.teacher_sessions, name='teacher_sessions'),
    path('teacher/sessions/create/<int:kelas_id>/', views.teacher_session_create, name='teacher_session_create'),
    path('teacher/sessions/<int:pk>/edit/', views.teacher_session_edit, name='teacher_session_edit'),
    path('teacher/sessions/<int:pk>/update-status/', views.teacher_session_update_status, name='teacher_session_update_status'),
    path('teacher/sessions/<int:pk>/attendance/', views.teacher_attendance, name='teacher_attendance'),
    # Exports
    path('teacher/classes/<int:pk>/export/attendance/excel/', views.export_attendance_excel, name='export_attendance_excel'),
    path('teacher/classes/<int:pk>/export/attendance/pdf/', views.export_attendance_pdf, name='export_attendance_pdf'),
    # Student session booking
    path('sessions/<int:pk>/', views.student_session_redirect, name='session_detail'),
    path('my-classes/<int:enrollment_id>/sessions/', views.student_session_list, name='student_session_list'),
    path('my-classes/<int:enrollment_id>/sessions/<int:session_id>/book/', views.student_book_session, name='student_book_session'),
    path('my-classes/<int:enrollment_id>/sessions/<int:session_id>/cancel/', views.student_cancel_booking, name='student_cancel_booking'),
]
