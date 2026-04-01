from django.urls import path
from . import views

app_name = 'enrollments'

urlpatterns = [
    path('enroll/<int:kelas_id>/', views.enroll, name='enroll'),
    path('my-classes/', views.my_classes, name='my_classes'),
    path('my-classes/<int:pk>/drop/', views.drop_class, name='drop_class'),
    path('teacher/enrollments/<int:pk>/update-status/', views.teacher_update_enrollment, name='teacher_update_enrollment'),
]
