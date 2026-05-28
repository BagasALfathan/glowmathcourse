from django.urls import path
from . import views

app_name = 'enrollments'

urlpatterns = [
    path('enroll/<int:kelas_id>/', views.enroll, name='enroll'),
    path('classes/<int:kelas_id>/waitlist/', views.join_waitlist, name='join_waitlist'),
    path('my-classes/', views.my_classes, name='my_classes'),
    path('my-classes/<int:enrollment_id>/', views.my_class_detail, name='my_class_detail'),
    path('my-classes/<int:pk>/drop/', views.drop_class, name='drop_class'),
    path('teacher/enrollments/<int:pk>/update-status/', views.teacher_update_enrollment, name='teacher_update_enrollment'),
]
