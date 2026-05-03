from django.urls import path

from . import views

app_name = 'grades'

urlpatterns = [
    # Teacher — overview & per-class
    path('teacher/grades/', views.teacher_grades_overview, name='teacher_grades_overview'),
    path('teacher/classes/<int:pk>/grades/', views.teacher_grades, name='teacher_grades'),
    path('teacher/grades/create/', views.teacher_grade_create, name='teacher_grade_create'),
    path('teacher/grades/<int:pk>/edit/', views.teacher_grade_edit, name='teacher_grade_edit'),
    path('teacher/grades/<int:pk>/delete/', views.teacher_grade_delete, name='teacher_grade_delete'),
    path('teacher/grades/<int:pk>/inline-edit/', views.teacher_grade_inline_edit, name='teacher_grade_inline_edit'),
    path('teacher/grades/<int:pk>/inline-save/', views.teacher_grade_inline_save, name='teacher_grade_inline_save'),
    # Teacher exports
    path('teacher/classes/<int:pk>/export/grades/excel/', views.export_grades_excel, name='export_grades_excel'),
    path('teacher/classes/<int:pk>/export/grades/pdf/', views.export_grades_pdf, name='export_grades_pdf'),
    # Student
    path('my-grades/', views.my_grades, name='my_grades'),
    path('my-grades/<int:kelas_id>/', views.my_grades_detail, name='my_grades_detail'),
    path('my-grades/print/', views.print_my_grades, name='print_my_grades'),
    # Progress reports — teacher
    path('teacher/classes/<int:pk>/students/<int:enrollment_id>/progress/', views.teacher_student_progress, name='teacher_student_progress'),
    path('teacher/classes/<int:pk>/students/<int:enrollment_id>/progress/print/', views.teacher_student_progress_print, name='teacher_student_progress_print'),
    path('teacher/classes/<int:pk>/students/<int:enrollment_id>/progress/pdf/', views.teacher_student_progress_pdf, name='teacher_student_progress_pdf'),
    # Progress reports — student
    path('my-progress/<int:kelas_id>/', views.student_progress, name='student_progress'),
    path('my-progress/<int:kelas_id>/print/', views.student_progress_print, name='student_progress_print'),
]
