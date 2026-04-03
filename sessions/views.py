from django.shortcuts import get_object_or_404, render

from academics.models import Kelas
from accounts.decorators import role_required
from enrollments.models import Enrollment, EnrollmentStatus
from sessions_app.models import Attendance, AttendanceStatus, Session


@role_required('STUDENT')
def my_attendance(request):
    enrollments = (
        Enrollment.objects
        .filter(student=request.user, status=EnrollmentStatus.ACTIVE, is_deleted=False)
        .select_related('kelas__subject', 'kelas__academic_period')
        .order_by('kelas__name')
    )

    summary_list = []
    for enrollment in enrollments:
        total_sessions = Session.objects.filter(kelas=enrollment.kelas).count()
        attendances = Attendance.objects.filter(enrollment=enrollment)
        present_count = attendances.filter(status=AttendanceStatus.PRESENT).count()
        permitted_count = attendances.filter(status=AttendanceStatus.PERMITTED).count()
        absent_count = attendances.filter(status=AttendanceStatus.ABSENT).count()
        marked_count = attendances.count()

        if marked_count > 0:
            pct = round((present_count + permitted_count) / marked_count * 100)
        else:
            pct = None

        summary_list.append({
            'enrollment': enrollment,
            'total_sessions': total_sessions,
            'marked_count': marked_count,
            'present_count': present_count,
            'permitted_count': permitted_count,
            'absent_count': absent_count,
            'pct': pct,
        })

    return render(request, 'sessions/my_attendance.html', {
        'summary_list': summary_list,
    })


@role_required('STUDENT')
def my_attendance_detail(request, kelas_id):
    kelas = get_object_or_404(Kelas, pk=kelas_id, is_deleted=False)
    enrollment = get_object_or_404(
        Enrollment,
        student=request.user,
        kelas=kelas,
        is_deleted=False,
    )

    sessions = Session.objects.filter(kelas=kelas).order_by('session_number')

    # Build lookup: session_id → Attendance
    att_map = {
        a.session_id: a
        for a in Attendance.objects.filter(enrollment=enrollment)
    }

    rows = []
    for session in sessions:
        att = att_map.get(session.pk)
        rows.append({
            'session': session,
            'attendance': att,
        })

    # Compute totals from marked records only
    present_count = sum(1 for r in rows if r['attendance'] and r['attendance'].status == AttendanceStatus.PRESENT)
    permitted_count = sum(1 for r in rows if r['attendance'] and r['attendance'].status == AttendanceStatus.PERMITTED)
    absent_count = sum(1 for r in rows if r['attendance'] and r['attendance'].status == AttendanceStatus.ABSENT)
    marked_count = present_count + permitted_count + absent_count

    if marked_count > 0:
        pct = round((present_count + permitted_count) / marked_count * 100)
    else:
        pct = None

    return render(request, 'sessions/my_attendance_detail.html', {
        'kelas': kelas,
        'enrollment': enrollment,
        'rows': rows,
        'present_count': present_count,
        'permitted_count': permitted_count,
        'absent_count': absent_count,
        'marked_count': marked_count,
        'pct': pct,
        'AttendanceStatus': AttendanceStatus,
    })
