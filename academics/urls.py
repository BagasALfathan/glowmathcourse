from django.urls import path
from . import views

app_name = 'academics'

urlpatterns = [
    # Student-facing
    path('classes/', views.class_browse, name='class_browse'),
    path('classes/<int:pk>/', views.class_detail, name='class_detail'),
    # Teacher-facing
    path('teacher/classes/', views.teacher_classes_list, name='teacher_classes'),
    path('teacher/classes/create/', views.teacher_class_create, name='teacher_class_create'),
    path('teacher/classes/<int:pk>/edit/', views.teacher_class_edit, name='teacher_class_edit'),
    path('teacher/classes/<int:pk>/delete/', views.teacher_class_delete, name='teacher_class_delete'),
    path('teacher/classes/<int:pk>/students/', views.teacher_class_students, name='teacher_class_students'),
]
