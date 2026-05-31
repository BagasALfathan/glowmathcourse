from django.urls import path
from . import views

app_name = 'course_materials'

urlpatterns = [
    path(
        'teacher/classes/<int:kelas_id>/materials/',
        views.teacher_materials,
        name='teacher_materials',
    ),
    path(
        'teacher/materials/<int:pk>/delete/',
        views.delete_material,
        name='delete_material',
    ),
    path(
        'teacher/materials/<int:pk>/toggle/',
        views.toggle_visibility,
        name='toggle_visibility',
    ),
    path(
        'my-classes/<int:enrollment_id>/materials/',
        views.student_materials,
        name='student_materials',
    ),
]
