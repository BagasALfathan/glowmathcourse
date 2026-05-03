from django.urls import path
from . import views

app_name = 'academics'

urlpatterns = [
    # Student schedule — /my-schedule/ redirects to /my-schedule/classes/
    path('my-schedule/', views.student_schedule_redirect, name='student_schedule'),
    path('my-schedule/classes/', views.student_schedule_classes, name='student_schedule_classes'),
    path('my-schedule/sessions/', views.student_schedule_sessions, name='student_schedule_sessions'),
    path('my-schedule/print/', views.student_schedule_print, name='student_schedule_print'),
    # Teacher schedule — /teacher/schedule/ redirects to /teacher/schedule/classes/
    path('teacher/schedule/', views.teacher_schedule_redirect, name='teacher_schedule'),
    path('teacher/schedule/classes/', views.teacher_schedule_classes, name='teacher_schedule_classes'),
    path('teacher/schedule/sessions/', views.teacher_schedule_sessions, name='teacher_schedule_sessions'),
    path('teacher/schedule/print/', views.teacher_schedule_print, name='teacher_schedule_print'),
    # Student-facing
    path('classes/', views.class_browse, name='class_browse'),
    path('classes/partial/', views.class_browse_partial, name='class_browse_partial'),
    path('classes/<int:pk>/', views.class_detail, name='class_detail'),
    # Teacher-facing
    path('teacher/classes/', views.teacher_classes_list, name='teacher_classes'),
    path('teacher/classes/create/', views.teacher_class_create, name='teacher_class_create'),
    path('teacher/classes/<int:pk>/edit/', views.teacher_class_edit, name='teacher_class_edit'),
    path('teacher/classes/<int:pk>/delete/', views.teacher_class_delete, name='teacher_class_delete'),
    path('teacher/classes/<int:pk>/students/', views.teacher_class_students, name='teacher_class_students'),
    path('teacher/classes/<int:pk>/complete/', views.teacher_complete_class, name='teacher_class_complete'),
    # Public teacher directory (any logged-in user)
    path('teachers/', views.teacher_list, name='teacher_list'),
    path('teachers/partial/', views.teacher_list_partial, name='teacher_list_partial'),
    path('teachers/<int:pk>/', views.teacher_profile, name='teacher_profile'),
]
