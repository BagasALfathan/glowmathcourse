from django.urls import path
from . import views

app_name = 'ratings'

urlpatterns = [
    path('teacher/ratings/', views.teacher_ratings, name='teacher_ratings'),
    path('rate/<int:enrollment_id>/', views.rate_teacher, name='rate_teacher'),
]
