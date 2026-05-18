from django.urls import path

from . import views

app_name = 'student'

urlpatterns = [
    path('my-classes/',        views.my_classes,       name='my_classes'),
    path('my-attendance/',     views.my_attendance,    name='my_attendance'),
    path('my-monthly-score/',  views.my_monthly_score, name='my_monthly_score'),
]
