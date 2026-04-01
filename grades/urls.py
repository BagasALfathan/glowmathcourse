from django.urls import path
from . import views

app_name = 'grades'

urlpatterns = [
    path('my-grades/', views.my_grades, name='my_grades'),
    path('my-grades/<int:kelas_id>/', views.my_grades_detail, name='my_grades_detail'),
    path('teacher/classes/<int:pk>/grades/', views.teacher_grades, name='teacher_grades'),
]
