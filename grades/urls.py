from django.urls import path

from . import views

app_name = 'grades'

urlpatterns = [
    # Teacher
    path('teacher/classes/<int:pk>/grades/', views.teacher_grades, name='teacher_grades'),
    path('teacher/grades/create/', views.teacher_grade_create, name='teacher_grade_create'),
    path('teacher/grades/<int:pk>/edit/', views.teacher_grade_edit, name='teacher_grade_edit'),
    path('teacher/grades/<int:pk>/delete/', views.teacher_grade_delete, name='teacher_grade_delete'),
    # Student
    path('my-grades/', views.my_grades, name='my_grades'),
    path('my-grades/<int:kelas_id>/', views.my_grades_detail, name='my_grades_detail'),
]
