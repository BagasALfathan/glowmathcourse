from django.shortcuts import render
from accounts.decorators import role_required


@role_required('STUDENT')
def my_attendance(request):
    return render(request, 'coming_soon.html', {'feature_name': 'Kehadiran Saya'})


@role_required('STUDENT')
def my_attendance_detail(request, kelas_id):
    return render(request, 'coming_soon.html', {'feature_name': 'Detail Kehadiran'})


@role_required('TEACHER')
def teacher_sessions(request, pk):
    return render(request, 'coming_soon.html', {'feature_name': 'Sesi Kelas'})


@role_required('TEACHER')
def teacher_session_create(request, kelas_id):
    return render(request, 'coming_soon.html', {'feature_name': 'Buat Sesi'})


@role_required('TEACHER')
def teacher_attendance(request, pk):
    return render(request, 'coming_soon.html', {'feature_name': 'Absensi'})
