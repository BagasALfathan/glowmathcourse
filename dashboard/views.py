from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from accounts.decorators import role_required
from accounts.models import User, Role


@login_required
def dashboard_router(request):
    role = request.user.role
    if role == Role.STUDENT:
        return redirect('dashboard:student')
    elif role == Role.TEACHER:
        return redirect('dashboard:teacher')
    elif role == Role.ADMIN:
        return redirect('dashboard:admin')
    return redirect('accounts:login')


@role_required('STUDENT')
def student_dashboard(request):
    from enrollments.models import Enrollment, EnrollmentStatus
    enrolled_count = Enrollment.objects.filter(
        student=request.user,
        status=EnrollmentStatus.ACTIVE,
        is_deleted=False,
    ).count()
    return render(request, 'dashboard/student.html', {
        'enrolled_count': enrolled_count,
        'upcoming_sessions': 0,  # populated in Day 11 (sessions app)
    })


@role_required('TEACHER')
def teacher_dashboard(request):
    from academics.models import Kelas
    from enrollments.models import Enrollment, EnrollmentStatus
    class_count = Kelas.objects.filter(
        teacher=request.user, is_deleted=False
    ).count()
    student_count = (
        Enrollment.objects
        .filter(
            kelas__teacher=request.user,
            kelas__is_deleted=False,
            status=EnrollmentStatus.ACTIVE,
            is_deleted=False,
        )
        .values('student')
        .distinct()
        .count()
    )
    return render(request, 'dashboard/teacher.html', {
        'class_count': class_count,
        'student_count': student_count,
    })


@role_required('ADMIN')
def admin_dashboard(request):
    from academics.models import Kelas, KelasStatus
    context = {
        'student_count': User.objects.filter(
            role=Role.STUDENT, is_deleted=False, is_active=True
        ).count(),
        'teacher_count': User.objects.filter(
            role=Role.TEACHER, is_deleted=False, is_active=True
        ).count(),
        'class_count': Kelas.objects.filter(
            is_deleted=False, status=KelasStatus.OPEN
        ).count(),
    }
    return render(request, 'dashboard/admin.html', context)
