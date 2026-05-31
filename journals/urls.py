from django.urls import path
from . import views

app_name = 'journals'

urlpatterns = [
    path('journals/', views.my_journals, name='my_journals'),
    path('journals/<int:pk>/', views.journal_detail, name='journal_detail'),
    # Teacher write/edit journal — single endpoint, get-or-edit per
    # unique (enrollment, month, year)
    path(
        'teacher/enrollments/<int:enrollment_id>/journal/<int:year>/<int:month>/',
        views.teacher_journal_write,
        name='teacher_journal_write',
    ),
]
