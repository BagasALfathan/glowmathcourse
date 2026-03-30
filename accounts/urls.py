from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    path('register/siswa/', views.register_student_view, name='register_student'),
    path('register/guru/', views.register_teacher_view, name='register_teacher'),
    path('register/waiting/', views.waiting_view, name='waiting'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/edit/', views.profile_edit_view, name='profile_edit'),
]
