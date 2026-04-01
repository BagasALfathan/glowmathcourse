from django.shortcuts import render
from accounts.decorators import role_required


@role_required('TEACHER')
def teacher_ratings(request):
    return render(request, 'coming_soon.html', {'feature_name': 'Penilaian Saya'})


@role_required('STUDENT')
def rate_teacher(request, enrollment_id):
    return render(request, 'coming_soon.html', {'feature_name': 'Beri Penilaian'})
