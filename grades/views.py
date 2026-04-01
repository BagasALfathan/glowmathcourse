from django.shortcuts import render
from accounts.decorators import role_required


@role_required('STUDENT')
def my_grades(request):
    return render(request, 'coming_soon.html', {'feature_name': 'Nilai Saya'})


@role_required('STUDENT')
def my_grades_detail(request, kelas_id):
    return render(request, 'coming_soon.html', {'feature_name': 'Nilai Per Kelas'})


@role_required('TEACHER')
def teacher_grades(request, pk):
    return render(request, 'coming_soon.html', {'feature_name': 'Manajemen Nilai'})
