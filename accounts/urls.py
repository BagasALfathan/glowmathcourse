from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    # ── Student portal (default / root) ─────────────────────────────────────
    path('', views.login_student_view, name='login'),                         # /
    path('register/', views.register_student_view, name='register'),          # /register/
    path('forgot-password/', views.forgot_password_student_view, name='forgot_password'),  # /forgot-password/

    # ── Teacher portal ──────────────────────────────────────────────────────
    path('guru/login/', views.login_teacher_view, name='login_teacher'),
    path('guru/register/', views.register_teacher_view, name='register_teacher'),
    path('guru/forgot-password/', views.forgot_password_teacher_view, name='forgot_password_teacher'),

    # ── Admin portal (hidden URL — Django admin moved to /django-admin/) ────
    path('admin/login/', views.login_admin_view, name='login_admin'),

    # ── Universal logout ────────────────────────────────────────────────────
    path('logout/', views.logout_view, name='logout'),                        # /logout/

    # ── Misc / shared ───────────────────────────────────────────────────────
    path('waiting/', views.waiting_view, name='waiting'),
    path('register/waiting/', views.waiting_view, name='waiting_legacy'),  # legacy alias
    path('register/student/', views.register_student_view, name='register_student'),  # legacy alias
    path('profile/', views.profile_view, name='profile'),
    path('profile/settings/', views.profile_settings_view, name='profile_settings'),
    path('profile/edit/', views.profile_edit_view, name='profile_edit'),
    path('profile/change-password/', views.change_password_view, name='change_password'),
]
