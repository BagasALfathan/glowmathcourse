from django.urls import path
from . import views

app_name = 'sessions'

# Student-facing attendance pages (teacher session management is in sessions_app)
urlpatterns = [
    path('my-attendance/', views.my_attendance, name='my_attendance'),
    path('my-attendance/<int:kelas_id>/', views.my_attendance_detail, name='my_attendance_detail'),
    path('my-attendance/print/', views.print_my_attendance, name='print_my_attendance'),
]
