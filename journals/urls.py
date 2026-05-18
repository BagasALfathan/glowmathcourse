from django.urls import path
from . import views

app_name = 'journals'

urlpatterns = [
    path('journals/', views.my_journals, name='my_journals'),
    path('journals/<int:pk>/', views.journal_detail, name='journal_detail'),
]
