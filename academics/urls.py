from django.urls import path
from . import views

app_name = 'academics'

urlpatterns = [
    path('teacher/classes/', views.teacher_classes_list, name='teacher_classes'),
    path('teacher/classes/create/', views.teacher_class_create, name='teacher_class_create'),
]
