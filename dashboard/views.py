from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q
from django.shortcuts import redirect, render
from django.utils import timezone

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
    from sessions_app.models import Session, Attendance, AttendanceStatus
    from grades.models import Grade

    enrollments = list(
        Enrollment.objects
        .filter(student=request.user, status=EnrollmentStatus.ACTIVE, is_deleted=False)
        .select_related('kelas__subject')
    )
    enrolled_count = len(enrollments)
    enrollment_ids = [e.pk for e in enrollments]
    kelas_ids = [e.kelas_id for e in enrollments]

    # Attendance percentage across all classes
    total_marked = Attendance.objects.filter(enrollment_id__in=enrollment_ids).count()
    total_present = Attendance.objects.filter(
        enrollment_id__in=enrollment_ids,
        status__in=[AttendanceStatus.PRESENT, AttendanceStatus.PERMITTED],
    ).count()
    avg_attendance = round(total_present / total_marked * 100) if total_marked > 0 else None

    # Average grade across all classes
    grade_avg = Grade.objects.filter(
        enrollment_id__in=enrollment_ids
    ).aggregate(avg=Avg('score'))['avg']
    avg_grade = round(float(grade_avg), 1) if grade_avg is not None else None

    # Recent 5 grades
    recent_grades = list(
        Grade.objects
        .filter(enrollment_id__in=enrollment_ids)
        .select_related('enrollment__kelas__subject')
        .order_by('-graded_at')[:5]
    )

    # Upcoming 3 sessions from enrolled classes
    today = timezone.now().date()
    upcoming_sessions = list(
        Session.objects
        .filter(kelas_id__in=kelas_ids, date__gte=today, status='SCHEDULED')
        .select_related('kelas__subject')
        .order_by('date')[:3]
    )

    return render(request, 'dashboard/student.html', {
        'enrolled_count': enrolled_count,
        'avg_attendance': avg_attendance,
        'avg_grade': avg_grade,
        'recent_grades': recent_grades,
        'upcoming_sessions': upcoming_sessions,
    })


@role_required('TEACHER')
def teacher_dashboard(request):
    from academics.models import Kelas
    from enrollments.models import Enrollment, EnrollmentStatus
    from sessions_app.models import Session, SessionStatus, Attendance

    classes = list(
        Kelas.objects
        .filter(teacher=request.user, is_deleted=False)
        .select_related('subject')
        .order_by('name')
    )
    class_count = len(classes)
    kelas_ids = [k.pk for k in classes]

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

    sessions_completed = Session.objects.filter(
        kelas_id__in=kelas_ids,
        status=SessionStatus.COMPLETED,
    ).count()

    # Last 5 attendance records marked across teacher's classes
    recent_attendance = list(
        Attendance.objects
        .filter(session__kelas_id__in=kelas_ids)
        .select_related('enrollment__student', 'session__kelas')
        .order_by('-marked_at')[:5]
    )

    # Classes with live enrolled count
    classes_overview = (
        Kelas.objects
        .filter(teacher=request.user, is_deleted=False)
        .select_related('subject')
        .annotate(
            active_enrolled=Count(
                'enrollments',
                filter=Q(
                    enrollments__status=EnrollmentStatus.ACTIVE,
                    enrollments__is_deleted=False,
                ),
            )
        )
        .order_by('name')
    )

    return render(request, 'dashboard/teacher.html', {
        'class_count': class_count,
        'student_count': student_count,
        'sessions_completed': sessions_completed,
        'recent_attendance': recent_attendance,
        'classes_overview': classes_overview,
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
