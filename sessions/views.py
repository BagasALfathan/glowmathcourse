from django.shortcuts import render
from accounts.decorators import role_required


# Student-facing attendance views (stubs — full implementation in a later day)

@role_required('STUDENT')
def my_attendance(request):
    return render(request, 'coming_soon.html', {'feature_name': 'Kehadiran Saya'})


@role_required('STUDENT')
def my_attendance_detail(request, kelas_id):
    return render(request, 'coming_soon.html', {'feature_name': 'Detail Kehadiran'})
