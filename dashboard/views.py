import calendar
import datetime
import json
from datetime import date

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
    from academics.utils import update_expired_classes
    from enrollments.models import Enrollment, EnrollmentStatus
    from sessions_app.models import Session, Attendance, AttendanceStatus, BookingStatus, SessionBooking, SessionStatus
    from grades.models import Grade

    update_expired_classes()

    today = timezone.localdate()

    enrollments = list(
        Enrollment.objects
        .filter(student=request.user, status=EnrollmentStatus.ACTIVE, is_deleted=False)
        .select_related('kelas__subject')
    )
    enrolled_count = len(enrollments)
    completed_enrolled_count = Enrollment.objects.filter(
        student=request.user, status=EnrollmentStatus.COMPLETED, is_deleted=False
    ).count()
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

    # Today's sessions from enrolled classes
    today_sessions_qs = list(
        Session.objects
        .filter(kelas_id__in=kelas_ids, date=today)
        .select_related('kelas__subject')
        .prefetch_related('kelas__schedules')
        .order_by('kelas__name')
    )
    _WEEKDAY_TO_DAY_DASH = ['MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY', 'SUNDAY']
    current_time_now = timezone.localtime().time()
    for _s in today_sessions_qs:
        _sched_map = {sc.day: sc for sc in _s.kelas.schedules.all()}
        _day = _WEEKDAY_TO_DAY_DASH[_s.date.weekday()]
        _sched = _sched_map.get(_day)
        _st = _s.start_time or (_sched.start_time if _sched else None)
        _et = _s.end_time or (_sched.end_time if _sched else None)
        _s.is_live = bool(_st and _et and _st <= current_time_now <= _et)
    today_sessions = today_sessions_qs

    # Next upcoming session (first date > today or today if still scheduled)
    next_session = (
        Session.objects
        .filter(kelas_id__in=kelas_ids, date__gte=today, status=SessionStatus.SCHEDULED)
        .select_related('kelas__subject')
        .order_by('date', 'session_number')
        .first()
    )

    # Upcoming sessions (excluding today, next 3)
    upcoming_sessions = list(
        Session.objects
        .filter(kelas_id__in=kelas_ids, date__gt=today, status=SessionStatus.SCHEDULED)
        .select_related('kelas__subject')
        .order_by('date')[:3]
    )

    # Total booked sessions across all active enrollments
    booked_sessions_count = SessionBooking.objects.filter(
        enrollment_id__in=enrollment_ids,
        status=BookingStatus.BOOKED,
    ).count()

    # Next booked session with countdown timestamps
    _WEEKDAY_TO_DAY = ['MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY', 'SUNDAY']
    booked_session_ids = SessionBooking.objects.filter(
        enrollment_id__in=enrollment_ids,
        status=BookingStatus.BOOKED,
    ).values_list('session_id', flat=True)
    next_booked_session = (
        Session.objects
        .filter(pk__in=booked_session_ids, date__gte=today, status=SessionStatus.SCHEDULED)
        .select_related('kelas__subject')
        .prefetch_related('kelas__schedules')
        .order_by('date', 'session_number')
        .first()
    )
    next_booked_start_ts = None
    next_booked_end_ts = None
    if next_booked_session:
        schedules_by_day = {s.day: s for s in next_booked_session.kelas.schedules.all()}
        day_name = _WEEKDAY_TO_DAY[next_booked_session.date.weekday()]
        sched = schedules_by_day.get(day_name)
        next_booked_session.display_schedule = sched
        # Prefer session's own stored times; fall back to class schedule
        st = next_booked_session.start_time or (sched.start_time if sched else None)
        et = next_booked_session.end_time or (sched.end_time if sched else None)
        if st and et:
            aware_start = timezone.make_aware(
                datetime.datetime.combine(next_booked_session.date, st)
            )
            aware_end = timezone.make_aware(
                datetime.datetime.combine(next_booked_session.date, et)
            )
            next_booked_start_ts = int(aware_start.timestamp() * 1000)
            next_booked_end_ts = int(aware_end.timestamp() * 1000)

    # --- Announcements ---
    from announcements.views import _announcements_for_user
    recent_announcements = list(_announcements_for_user(request.user)[:4])

    # --- Chart data ---
    # Attendance pie: Hadir / Izin / Alpha
    total_hadir = Attendance.objects.filter(
        enrollment_id__in=enrollment_ids, status=AttendanceStatus.PRESENT
    ).count()
    total_izin = Attendance.objects.filter(
        enrollment_id__in=enrollment_ids, status=AttendanceStatus.PERMITTED
    ).count()
    total_alpha = Attendance.objects.filter(
        enrollment_id__in=enrollment_ids, status=AttendanceStatus.ABSENT
    ).count()
    chart_attendance = json.dumps({'hadir': total_hadir, 'izin': total_izin, 'alpha': total_alpha})

    # Grades bar: average score per enrolled class
    grades_per_class = []
    for enrollment in enrollments:
        avg = Grade.objects.filter(enrollment=enrollment).aggregate(avg=Avg('score'))['avg']
        if avg is not None:
            grades_per_class.append({'name': enrollment.kelas.subject.name, 'avg': round(float(avg), 1)})
    chart_grades = json.dumps(grades_per_class)

    return render(request, 'dashboard/student.html', {
        'enrolled_count': enrolled_count,
        'completed_enrolled_count': completed_enrolled_count,
        'avg_attendance': avg_attendance,
        'avg_grade': avg_grade,
        'booked_sessions_count': booked_sessions_count,
        'recent_grades': recent_grades,
        'today_sessions': today_sessions,
        'next_session': next_session,
        'next_booked_session': next_booked_session,
        'next_booked_start_ts': next_booked_start_ts,
        'next_booked_end_ts': next_booked_end_ts,
        'upcoming_sessions': upcoming_sessions,
        'today': today,
        'chart_attendance': chart_attendance,
        'chart_grades': chart_grades,
        'recent_announcements': recent_announcements,
    })


@role_required('TEACHER')
def teacher_dashboard(request):
    from academics.models import Kelas, KelasStatus
    from academics.utils import update_expired_classes
    from enrollments.models import Enrollment, EnrollmentStatus
    from sessions_app.models import Session, SessionStatus, Attendance, BookingStatus, SessionBooking

    update_expired_classes()
    today = timezone.localdate()

    classes = list(
        Kelas.objects
        .filter(teacher=request.user, is_deleted=False)
        .select_related('subject')
        .order_by('name')
    )
    class_count = len(classes)
    active_class_count_t = sum(
        1 for k in classes if k.status in (KelasStatus.OPEN, KelasStatus.FULL)
    )
    closed_class_count = sum(1 for k in classes if k.status == KelasStatus.CLOSED)
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

    # Today's sessions across all teacher's classes (with booked count)
    _current_time_t = timezone.localtime().time()
    _today_sessions_raw = list(
        Session.objects
        .filter(kelas_id__in=kelas_ids, date=today)
        .annotate(booked_count_ann=Count(
            'bookings',
            filter=Q(bookings__status=BookingStatus.BOOKED),
        ))
        .select_related('kelas__subject')
        .prefetch_related('kelas__schedules')
        .order_by('kelas__name')
    )
    _WKDAY_T = ['MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY', 'SUNDAY']
    for _ts in _today_sessions_raw:
        _sm = {sc.day: sc for sc in _ts.kelas.schedules.all()}
        _sc = _sm.get(_WKDAY_T[_ts.date.weekday()])
        _ts.schedule = _sc
        _ts_st = _ts.start_time or (_sc.start_time if _sc else None)
        _ts_et = _ts.end_time or (_sc.end_time if _sc else None)
        _ts.is_live = bool(_ts_st and _ts_et and _ts_st <= _current_time_t <= _ts_et)
    today_sessions = _today_sessions_raw

    # Next upcoming session
    next_session = (
        Session.objects
        .filter(kelas_id__in=kelas_ids, date__gte=today, status=SessionStatus.SCHEDULED)
        .select_related('kelas__subject')
        .prefetch_related('kelas__schedules')
        .order_by('date', 'session_number')
        .first()
    )
    if next_session:
        _ns_sched_map = {sc.day: sc for sc in next_session.kelas.schedules.all()}
        next_session.schedule = _ns_sched_map.get(_WKDAY_T[next_session.date.weekday()])

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

    # --- Announcements ---
    from announcements.views import _announcements_for_user as _ann_for_user
    recent_announcements_t = list(_ann_for_user(request.user)[:4])

    # --- Chart data ---
    from grades.models import Grade
    from sessions_app.models import AttendanceStatus as AStatus

    # Attendance % per class bar chart
    attendance_chart = []
    for kelas in classes:
        total_att = Attendance.objects.filter(session__kelas=kelas).count()
        present_att = Attendance.objects.filter(
            session__kelas=kelas, status=AStatus.PRESENT
        ).count()
        pct = round(present_att / total_att * 100) if total_att > 0 else 0
        attendance_chart.append({'name': kelas.subject.name, 'pct': pct})
    chart_attendance = json.dumps(attendance_chart)

    # Grade distribution pie: A/B/C/D buckets across all classes
    all_grades = Grade.objects.filter(
        enrollment__kelas__teacher=request.user,
        enrollment__kelas__is_deleted=False,
    ).values_list('score', flat=True)
    grade_dist = {'A': 0, 'B': 0, 'C': 0, 'D': 0}
    for score in all_grades:
        if score >= 80:
            grade_dist['A'] += 1
        elif score >= 60:
            grade_dist['B'] += 1
        elif score >= 40:
            grade_dist['C'] += 1
        else:
            grade_dist['D'] += 1
    chart_grade_dist = json.dumps(grade_dist)

    # Students per class doughnut
    students_chart = [
        {'name': k.name, 'count': k.active_enrolled}
        for k in classes_overview
    ]
    chart_students = json.dumps(students_chart)

    return render(request, 'dashboard/teacher.html', {
        'class_count': class_count,
        'active_class_count_t': active_class_count_t,
        'closed_class_count': closed_class_count,
        'student_count': student_count,
        'sessions_completed': sessions_completed,
        'recent_attendance': recent_attendance,
        'today_sessions': today_sessions,
        'next_session': next_session,
        'classes_overview': classes_overview,
        'today': today,
        'chart_attendance': chart_attendance,
        'chart_grade_dist': chart_grade_dist,
        'chart_students': chart_students,
        'recent_announcements': recent_announcements_t,
    })


@role_required('ADMIN')
def admin_dashboard(request):
    from academics.models import Kelas, KelasStatus
    from accounts.models import ApprovalStatus
    from enrollments.models import Enrollment, EnrollmentStatus
    from sessions_app.models import Session, SessionStatus
    from ratings.models import Rating

    student_count = User.objects.filter(
        role=Role.STUDENT, approval_status=ApprovalStatus.APPROVED, is_deleted=False,
    ).count()
    teacher_count = User.objects.filter(
        role=Role.TEACHER, approval_status=ApprovalStatus.APPROVED, is_deleted=False,
    ).count()
    admin_count = User.objects.filter(
        role=Role.ADMIN, is_deleted=False,
    ).count()

    active_class_count = Kelas.objects.filter(
        is_deleted=False, status=KelasStatus.OPEN,
    ).count()
    active_enrollment_count = Enrollment.objects.filter(
        status=EnrollmentStatus.ACTIVE, is_deleted=False,
    ).count()
    sessions_completed_count = Session.objects.filter(
        status=SessionStatus.COMPLETED,
    ).count()

    pending_count = User.objects.filter(
        approval_status=ApprovalStatus.PENDING, is_deleted=False,
    ).count()

    rating_avg = Rating.objects.aggregate(avg=Avg('score'))['avg']
    avg_teacher_rating = round(float(rating_avg), 1) if rating_avg else None

    recent_registrations = list(
        User.objects.filter(is_deleted=False)
        .order_by('-date_joined')[:10]
    )

    # --- Announcements ---
    from announcements.views import _announcements_for_user as _ann_admin
    recent_announcements_a = list(_ann_admin(request.user)[:4])

    # --- Chart data ---
    # Users by role pie
    chart_users = json.dumps({
        'Siswa': student_count,
        'Guru': teacher_count,
        'Admin': admin_count,
    })

    # Enrollments by level bar
    enroll_level = {}
    for level in ['SD', 'SMP', 'SMA']:
        enroll_level[level] = Enrollment.objects.filter(
            student__student_profile__level=level,
            is_deleted=False,
        ).count()
    chart_enroll_level = json.dumps(enroll_level)

    # Classes by status doughnut
    kelas_by_status = {}
    for status_val, label in [('OPEN', 'Buka'), ('FULL', 'Penuh'), ('CLOSED', 'Tutup')]:
        kelas_by_status[label] = Kelas.objects.filter(
            status=status_val, is_deleted=False
        ).count()
    chart_kelas_status = json.dumps(kelas_by_status)

    # Monthly registrations — last 6 months
    today_date = date.today()
    months_id = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun',
                 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des']
    monthly_data = []
    for i in range(5, -1, -1):
        # compute year/month for "i months ago"
        month_raw = today_date.month - i
        year = today_date.year + (month_raw - 1) // 12
        month = ((month_raw - 1) % 12) + 1
        start = date(year, month, 1)
        end_day = calendar.monthrange(year, month)[1]
        end = date(year, month, end_day)
        count = User.objects.filter(
            date_joined__date__gte=start,
            date_joined__date__lte=end,
            is_deleted=False,
        ).count()
        monthly_data.append({'month': months_id[month - 1], 'count': count})
    chart_monthly = json.dumps(monthly_data)

    context = {
        'student_count': student_count,
        'teacher_count': teacher_count,
        'admin_count': admin_count,
        'active_class_count': active_class_count,
        'active_enrollment_count': active_enrollment_count,
        'sessions_completed_count': sessions_completed_count,
        'pending_count': pending_count,
        'avg_teacher_rating': avg_teacher_rating,
        'recent_registrations': recent_registrations,
        'chart_users': chart_users,
        'chart_enroll_level': chart_enroll_level,
        'chart_kelas_status': chart_kelas_status,
        'chart_monthly': chart_monthly,
        'recent_announcements': recent_announcements_a,
    }
    return render(request, 'dashboard/admin.html', context)
