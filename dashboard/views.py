import calendar
import datetime
import json
from datetime import date

from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, F, Q
from django.shortcuts import redirect, render
from django.utils import timezone

from accounts.decorators import role_required
from accounts.models import User, Role


@login_required
def help_view(request):
    return render(request, 'dashboard/help.html')


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
    """V3 Khan Academy student dashboard — discovery-focused.

    Layout (top → bottom):
      1. Announcement HERO
      2. 3 KPI stats inline
      3. 3 active class mini cards
      4. Best teacher of the month (1 featured + 2 runners-up)
      5. Kelas Populer + Kelas Baru (2 col)
      6. Today's sessions + Latest journal (2 col)
    """
    from academics.models import Kelas, KelasStatus
    from academics.utils import update_expired_classes
    from accounts.models import TeacherProfile
    from announcements.models import Announcement
    from enrollments.models import Enrollment, EnrollmentStatus
    from grades.models import Grade
    from journals.models import MonthlyJournal
    from ratings.models import TeacherRating
    from sessions_app.models import (
        Attendance, AttendanceStatus, Session, SessionStatus,
    )
    from django.core.cache import cache

    update_expired_classes()

    student = request.user
    student_profile = student.student_profile
    today = timezone.localdate()

    # ── Active enrollments (top 3 for the mini cards) ────────────────────────
    active_enrollments_qs = (
        Enrollment.objects
        .filter(
            student_profile=student_profile,
            status=EnrollmentStatus.ACTIVE,
            is_deleted=False,
            kelas__is_deleted=False,
        )
        .select_related(
            'kelas__subject',
            'kelas__teacher_profile__user',
        )
        .annotate(
            total_sessions_count=Count('kelas__sessions', distinct=True),
            completed_sessions_count=Count(
                'kelas__sessions',
                filter=Q(kelas__sessions__status=SessionStatus.COMPLETED),
                distinct=True,
            ),
        )
        .order_by('-enrolled_at')
    )
    total_active_classes = active_enrollments_qs.count()
    active_enrollments = list(active_enrollments_qs[:3])

    # Inline progress % per active enrollment (avoid template arithmetic)
    for e in active_enrollments:
        total = getattr(e, 'total_sessions_count', 0) or e.kelas.total_sessions or 0
        done = getattr(e, 'completed_sessions_count', 0) or 0
        e.progress_pct = round(done * 100 / total) if total else 0

    # ── KPI: attendance % and average score ─────────────────────────────────
    att_qs = Attendance.objects.filter(
        enrollment__student_profile=student_profile,
        enrollment__status=EnrollmentStatus.ACTIVE,
    )
    total_marked = att_qs.count()
    present_count = att_qs.filter(status=AttendanceStatus.PRESENT).count()
    attendance_rate = round(present_count * 100 / total_marked) if total_marked else 0

    grade_avg = (
        Grade.objects
        .filter(enrollment__student_profile=student_profile)
        .aggregate(avg=Avg('score'))['avg']
    )
    avg_score = round(float(grade_avg), 1) if grade_avg is not None else 0

    # ── Featured announcement (1 prominent, others get dots) ────────────────
    ann_qs = Announcement.objects.filter(
        is_active=True,
        target_role__in=[Announcement.TargetRole.ALL, Announcement.TargetRole.STUDENT],
        level__in=[Announcement.TargetLevel.ALL, student_profile.level or ''],
    ).select_related('author').order_by('-is_pinned', '-created_at')
    featured_announcement = ann_qs.first()
    other_announcements_count = max(ann_qs.count() - 1, 0)

    # ── Best teacher of the month (cached 1h) ───────────────────────────────
    top_teachers = cache.get('top_teachers_dashboard')
    if top_teachers is None:
        top_teachers = []
        leaderboard = (
            TeacherRating.objects
            .values('teacher_profile')
            .annotate(avg_score=Avg('score'), rating_count=Count('id'))
            .filter(rating_count__gte=3)
            .order_by('-avg_score', '-rating_count')[:3]
        )
        rows = list(leaderboard)
        tp_ids = [r['teacher_profile'] for r in rows]
        profiles_by_id = {
            tp.pk: tp
            for tp in TeacherProfile.objects.filter(pk__in=tp_ids).select_related('user')
        }
        student_counts = dict(
            Enrollment.objects
            .filter(
                kelas__teacher_profile_id__in=tp_ids,
                status=EnrollmentStatus.ACTIVE,
                is_deleted=False,
            )
            .values('kelas__teacher_profile')
            .annotate(n=Count('student_profile', distinct=True))
            .values_list('kelas__teacher_profile', 'n')
        )
        for r in rows:
            tp = profiles_by_id.get(r['teacher_profile'])
            if not tp:
                continue
            top_teachers.append({
                'profile': tp,
                'avg_score': round(r['avg_score'], 1),
                'rating_count': r['rating_count'],
                'student_count': student_counts.get(r['teacher_profile'], 0),
            })
        cache.set('top_teachers_dashboard', top_teachers, 3600)

    # ── Kelas Populer + Kelas Baru ─────────────────────────────────────────
    level_filter = {'level': student_profile.level} if student_profile.level else {}
    base_open = Kelas.objects.filter(
        status=KelasStatus.OPEN, is_deleted=False, **level_filter,
    ).select_related('subject', 'teacher_profile__user')

    popular_classes = list(
        base_open
        .annotate(
            enrollment_count=Count(
                'enrollments',
                filter=Q(enrollments__status=EnrollmentStatus.ACTIVE, enrollments__is_deleted=False),
            ),
        )
        .order_by('-enrollment_count', '-created_at')[:2]
    )
    new_classes = list(base_open.order_by('-created_at')[:2])

    # ── Today's sessions (deduped) ─────────────────────────────────────────
    today_sessions = list(
        Session.objects
        .filter(
            kelas__enrollments__student_profile=student_profile,
            kelas__enrollments__status=EnrollmentStatus.ACTIVE,
            kelas__enrollments__is_deleted=False,
            date=today,
            status=SessionStatus.SCHEDULED,
        )
        .select_related('kelas__subject', 'kelas__teacher_profile__user')
        .distinct()
        .order_by('start_time')
    )

    # ── Latest published monthly journal ───────────────────────────────────
    latest_journal = (
        MonthlyJournal.objects
        .filter(
            enrollment__student_profile=student_profile,
            published_at__isnull=False,
        )
        .select_related(
            'enrollment__kelas__subject',
            'written_by_teacher__user',
        )
        .order_by('-year', '-month')
        .first()
    )
    if latest_journal:
        m_start = datetime.date(latest_journal.year, latest_journal.month, 1)
        if latest_journal.month == 12:
            m_end = datetime.date(latest_journal.year + 1, 1, 1)
        else:
            m_end = datetime.date(latest_journal.year, latest_journal.month + 1, 1)
        month_avg = (
            Grade.objects
            .filter(
                enrollment=latest_journal.enrollment,
                graded_at__date__gte=m_start,
                graded_at__date__lt=m_end,
            )
            .aggregate(avg=Avg('score'))['avg']
        )
        latest_journal.month_score = round(float(month_avg), 1) if month_avg is not None else None

    return render(request, 'dashboard/student.html', {
        'student': student,
        'student_profile': student_profile,
        'total_active_classes': total_active_classes,
        'attendance_rate': attendance_rate,
        'avg_score': avg_score,
        'active_enrollments': active_enrollments,
        'featured_announcement': featured_announcement,
        'other_announcements_count': other_announcements_count,
        'top_teachers': top_teachers,
        'popular_classes': popular_classes,
        'new_classes': new_classes,
        'today_sessions': today_sessions,
        'today_sessions_count': len(today_sessions),
        'latest_journal': latest_journal,
        'today': today,
    })


@role_required('TEACHER')
def teacher_dashboard(request):
    """V2 Notion-clean teacher dashboard — priority on 'Sesi Hari Ini',
    plus 4 KPIs, a To-Do list, a class table, and an at-risk-student list."""
    from academics.models import Kelas, KelasStatus
    from academics.utils import update_expired_classes
    from enrollments.models import Enrollment, EnrollmentStatus
    from sessions_app.models import Session, SessionStatus, Attendance, AttendanceStatus
    from grades.models import Grade
    from journals.models import MonthlyJournal
    from ratings.models import TeacherRating
    from django.core.cache import cache

    update_expired_classes()

    teacher = request.user
    teacher_profile = teacher.teacher_profile
    today = timezone.localdate()
    now_dt = timezone.localtime()
    now_time = now_dt.time()
    start_of_week = today - datetime.timedelta(days=today.weekday())
    end_of_week = start_of_week + datetime.timedelta(days=6)

    # ── My classes (annotated with completed sessions + student count) ─────
    my_classes_qs = (
        Kelas.objects
        .filter(teacher_profile=teacher_profile, is_deleted=False)
        .exclude(status=KelasStatus.CLOSED)
        .select_related('subject', 'academic_period')
        .annotate(
            completed_sessions_n=Count(
                'sessions',
                filter=Q(sessions__status=SessionStatus.COMPLETED),
                distinct=True,
            ),
            active_students=Count(
                'enrollments',
                filter=Q(enrollments__status=EnrollmentStatus.ACTIVE, enrollments__is_deleted=False),
                distinct=True,
            ),
        )
        .order_by('-created_at')
    )
    my_classes = list(my_classes_qs)
    active_classes_count = len(my_classes)

    # ── Stats ─────────────────────────────────────────────────────────────
    total_students = (
        Enrollment.objects
        .filter(
            kelas__teacher_profile=teacher_profile,
            status=EnrollmentStatus.ACTIVE,
            is_deleted=False,
        )
        .values('student_profile').distinct().count()
    )

    sessions_this_week = Session.objects.filter(
        kelas__teacher_profile=teacher_profile,
        date__gte=start_of_week, date__lte=end_of_week,
    ).count()
    sessions_prev_week = Session.objects.filter(
        kelas__teacher_profile=teacher_profile,
        date__gte=start_of_week - datetime.timedelta(days=7),
        date__lte=start_of_week - datetime.timedelta(days=1),
    ).count()
    sessions_trend = sessions_this_week - sessions_prev_week

    rating_agg = TeacherRating.objects.filter(
        teacher_profile=teacher_profile,
    ).aggregate(avg=Avg('score'), n=Count('id'))
    my_rating = round(float(rating_agg['avg']), 1) if rating_agg['avg'] is not None else 0
    rating_count = rating_agg['n'] or 0

    # ── Today's sessions ───────────────────────────────────────────────────
    today_sessions = list(
        Session.objects
        .filter(kelas__teacher_profile=teacher_profile, date=today)
        .select_related('kelas__subject')
        .annotate(
            att_total=Count('attendances', distinct=True),
            att_present=Count(
                'attendances',
                filter=Q(attendances__status=AttendanceStatus.PRESENT),
                distinct=True,
            ),
            enrolled_n=Count(
                'kelas__enrollments',
                filter=Q(
                    kelas__enrollments__status=EnrollmentStatus.ACTIVE,
                    kelas__enrollments__is_deleted=False,
                ),
                distinct=True,
            ),
        )
        .order_by('start_time', 'session_number')
    )
    today_sessions_data = []
    for s in today_sessions:
        st, et = s.start_time, s.end_time
        is_now = bool(st and et and st <= now_time <= et)
        duration_min = 0
        if st and et:
            duration_min = int(
                (datetime.datetime.combine(today, et) - datetime.datetime.combine(today, st)).total_seconds() // 60
            )
        today_sessions_data.append({
            'session': s,
            'is_now': is_now,
            'attendance_marked': s.att_total > 0,
            'attended_count': s.att_present,
            'enrolled_count': s.enrolled_n,
            'duration_minutes': duration_min,
        })

    # ── Sessions in last 7 days that have ZERO attendance rows ────────────
    sessions_needing_attendance_count = (
        Session.objects
        .filter(
            kelas__teacher_profile=teacher_profile,
            date__lte=today,
            date__gte=today - datetime.timedelta(days=7),
        )
        .annotate(n=Count('attendances'))
        .filter(n=0)
        .count()
    )

    # ── To-do ─────────────────────────────────────────────────────────────
    todo_items = []
    if sessions_needing_attendance_count > 0:
        todo_items.append({
            'urgency': 'urgent',
            'icon': 'ti-clipboard-x',
            'title': f'{sessions_needing_attendance_count} sesi belum diabsen',
            'subtitle': '7 hari terakhir',
            'url': '/teacher/attendance/',
        })

    # Monthly journals expected this past month
    first_of_month = today.replace(day=1)
    last_month = first_of_month - datetime.timedelta(days=1)
    last_month_journals_existing = (
        MonthlyJournal.objects
        .filter(
            enrollment__kelas__teacher_profile=teacher_profile,
            month=last_month.month, year=last_month.year,
        )
        .values_list('enrollment_id', flat=True)
    )
    last_month_journals_existing_set = set(last_month_journals_existing)
    journals_pending = 0
    for k in my_classes:
        active_enr_ids = list(
            Enrollment.objects
            .filter(kelas=k, status=EnrollmentStatus.ACTIVE, is_deleted=False)
            .values_list('id', flat=True)
        )
        for eid in active_enr_ids:
            if eid not in last_month_journals_existing_set:
                journals_pending += 1
    if journals_pending > 0:
        _id_months = ['Januari','Februari','Maret','April','Mei','Juni','Juli','Agustus','September','Oktober','November','Desember']
        todo_items.append({
            'urgency': 'info',
            'icon': 'ti-notebook',
            'title': f'{journals_pending} jurnal bulanan belum ditulis',
            'subtitle': f'Untuk bulan {_id_months[last_month.month - 1]}',
            'url': '/teacher/journals/',
        })

    # ── Class summary table (top 5) ───────────────────────────────────────
    my_classes_list = []
    for k in my_classes[:5]:
        completed = getattr(k, 'completed_sessions_n', 0) or 0
        total = k.total_sessions or 0
        my_classes_list.append({
            'kelas': k,
            'completed_sessions': completed,
            'total_sessions': total,
            'progress_pct': int(completed * 100 / total) if total else 0,
            'student_count': getattr(k, 'active_students', 0) or 0,
        })

    # ── Students needing attention (cached 30 min) ────────────────────────
    cache_key = f'teacher_attention_{teacher_profile.pk}'
    students_attention = cache.get(cache_key)
    if students_attention is None:
        active_enr = (
            Enrollment.objects
            .filter(
                kelas__teacher_profile=teacher_profile,
                status=EnrollmentStatus.ACTIVE,
                is_deleted=False,
            )
            .select_related('student_profile__user', 'kelas')
            .annotate(
                att_total=Count('attendances', distinct=True),
                att_present=Count(
                    'attendances',
                    filter=Q(attendances__status=AttendanceStatus.PRESENT),
                    distinct=True,
                ),
                grade_avg=Avg('grades__score'),
            )
        )
        flagged = []
        for e in active_enr:
            if e.att_total < 3:
                continue
            rate = round(e.att_present * 100 / e.att_total) if e.att_total else 100
            avg = round(float(e.grade_avg), 1) if e.grade_avg is not None else None
            flag = None
            if rate < 60 and (avg is not None and avg < 70):
                flag = 'critical'
            elif rate < 70:
                flag = 'attendance'
            elif avg is not None and avg < 70:
                flag = 'score'
            if flag:
                flagged.append({
                    'student_id': e.student_profile.user_id,
                    'student_name': e.student_profile.user.get_full_name() or e.student_profile.user.username,
                    'first_letter': (e.student_profile.user.first_name or e.student_profile.user.username)[:1].upper(),
                    'kelas_name': e.kelas.name,
                    'attendance_rate': rate,
                    'avg_score': avg if avg is not None else 0,
                    'flag': flag,
                })
        flagged.sort(key=lambda x: 0 if x['flag'] == 'critical' else 1)
        students_attention = flagged[:5]
        cache.set(cache_key, students_attention, 1800)

    return render(request, 'dashboard/teacher.html', {
        'teacher_profile': teacher_profile,
        'today': today,
        'today_sessions_data': today_sessions_data,
        'today_sessions_count': len(today_sessions_data),
        'sessions_needing_attendance_count': sessions_needing_attendance_count,
        'active_classes_count': active_classes_count,
        'total_students': total_students,
        'sessions_this_week': sessions_this_week,
        'sessions_trend': sessions_trend,
        'my_rating': my_rating,
        'rating_count': rating_count,
        'todo_items': todo_items,
        'my_classes_list': my_classes_list,
        'students_attention': students_attention,
    })


@role_required('ADMIN')
def admin_dashboard(request):
    """V4 Data Pro admin dashboard — dense, table-heavy, no charts.

    Sections: 6 KPI cards · Pending Approvals · Top/Worst students+teachers ·
    Popular + Sepi classes · Activity Log.
    """
    from academics.models import Kelas, KelasStatus
    from academics.utils import update_expired_classes
    from accounts.models import ApprovalStatus, StudentProfile, TeacherProfile
    from activity_logs.models import ActivityLog
    from enrollments.models import Enrollment, EnrollmentStatus
    from sessions_app.models import Session
    from ratings.models import TeacherRating
    from django.core.cache import cache

    update_expired_classes()

    today = timezone.localdate()
    now_dt = timezone.localtime()

    # ── KPI stats (cached 5min) ────────────────────────────────────────────
    kpi = cache.get('admin_kpi_stats')
    if kpi is None:
        kpi = {
            'total_users':    User.objects.filter(is_deleted=False).count(),
            'total_classes':  Kelas.objects.filter(is_deleted=False).exclude(status=KelasStatus.CLOSED).count(),
            'sessions_today': Session.objects.filter(date=today).count(),
            'pending_users':  User.objects.filter(approval_status=ApprovalStatus.PENDING, is_deleted=False).count(),
            'activity_today': ActivityLog.objects.filter(created_at__date=today).count(),
        }
        cache.set('admin_kpi_stats', kpi, 300)

    # Alerts: full classes + idle approved teachers (recompute fresh — cheap)
    full_classes_count = (
        Kelas.objects
        .filter(is_deleted=False)
        .exclude(status=KelasStatus.CLOSED)
        .annotate(active_enr=Count(
            'enrollments',
            filter=Q(enrollments__status=EnrollmentStatus.ACTIVE, enrollments__is_deleted=False),
        ))
        .filter(active_enr__gte=F('capacity'))
        .count()
    )
    idle_teachers_count = (
        TeacherProfile.objects
        .filter(user__approval_status=ApprovalStatus.APPROVED, user__is_deleted=False)
        .annotate(active_classes=Count(
            'taught_classes',
            filter=Q(taught_classes__is_deleted=False) & ~Q(taught_classes__status=KelasStatus.CLOSED),
        ))
        .filter(active_classes=0)
        .count()
    )
    kpi = dict(kpi)  # don't mutate the cached dict
    kpi['alerts_count'] = full_classes_count + min(idle_teachers_count, 3)

    # ── Pending approvals (top 5) ──────────────────────────────────────────
    pending_qs = (
        User.objects
        .filter(approval_status=ApprovalStatus.PENDING, is_deleted=False)
        .select_related('student_profile', 'teacher_profile')
        .order_by('-date_joined')[:5]
    )
    pending_users_data = []
    for u in pending_qs:
        info = '—'
        if u.role == 'STUDENT' and hasattr(u, 'student_profile') and u.student_profile:
            sp = u.student_profile
            info = f'{sp.level or "—"} · {sp.school_name or "—"}'
        elif u.role == 'TEACHER' and hasattr(u, 'teacher_profile') and u.teacher_profile:
            tp = u.teacher_profile
            info = f'{tp.education or "—"} · {tp.specialization or "—"}'
        delta = now_dt - u.date_joined
        if delta.days >= 1:
            time_str = f'{delta.days} hari lalu'
        elif delta.seconds >= 3600:
            time_str = f'{delta.seconds // 3600} jam lalu'
        else:
            time_str = f'{max(delta.seconds // 60, 1)} menit lalu'
        pending_users_data.append({'user': u, 'info': info, 'time_ago': time_str})

    # ── Top students (cached 30min) ────────────────────────────────────────
    top_students = cache.get('admin_top_students')
    if top_students is None:
        rows = (
            StudentProfile.objects
            .select_related('user')
            .annotate(
                avg_score=Avg('enrollments__grades__score'),
                grade_count=Count('enrollments__grades', distinct=True),
                active_class_count=Count(
                    'enrollments',
                    filter=Q(enrollments__status=EnrollmentStatus.ACTIVE, enrollments__is_deleted=False),
                    distinct=True,
                ),
            )
            .filter(grade_count__gte=5)
            .order_by('-avg_score')[:5]
        )
        top_students = [{
            'profile': sp,
            'avg_score': round(float(sp.avg_score), 1) if sp.avg_score is not None else 0,
            'active_classes': sp.active_class_count or 0,
        } for sp in rows]
        cache.set('admin_top_students', top_students, 1800)

    # ── Worst students (cached 30min) ──────────────────────────────────────
    from sessions_app.models import AttendanceStatus
    worst_students = cache.get('admin_worst_students')
    if worst_students is None:
        rows = (
            StudentProfile.objects
            .select_related('user')
            .annotate(
                avg_score=Avg('enrollments__grades__score'),
                grade_count=Count('enrollments__grades', distinct=True),
                active_class_count=Count(
                    'enrollments',
                    filter=Q(enrollments__status=EnrollmentStatus.ACTIVE, enrollments__is_deleted=False),
                    distinct=True,
                ),
                total_att=Count('enrollments__attendances', distinct=True),
                present_att=Count(
                    'enrollments__attendances',
                    filter=Q(enrollments__attendances__status=AttendanceStatus.PRESENT),
                    distinct=True,
                ),
            )
            .filter(grade_count__gte=3)
            .order_by('avg_score')[:5]
        )
        worst_students = []
        for sp in rows:
            att_rate = int(sp.present_att * 100 / sp.total_att) if sp.total_att else 0
            worst_students.append({
                'profile': sp,
                'avg_score': round(float(sp.avg_score), 1) if sp.avg_score is not None else 0,
                'attendance_rate': att_rate,
                'active_classes': sp.active_class_count or 0,
            })
        cache.set('admin_worst_students', worst_students, 1800)

    # ── Top teachers (cached 30min) ────────────────────────────────────────
    top_teachers = cache.get('admin_top_teachers')
    if top_teachers is None:
        leaderboard = (
            TeacherRating.objects.values('teacher_profile')
            .annotate(avg_score=Avg('score'), rating_count=Count('id'))
            .filter(rating_count__gte=3)
            .order_by('-avg_score')[:5]
        )
        rows = list(leaderboard)
        tp_ids = [r['teacher_profile'] for r in rows]
        profiles_by_id = {
            tp.pk: tp for tp in
            TeacherProfile.objects.filter(pk__in=tp_ids).select_related('user')
        }
        student_counts = dict(
            Enrollment.objects
            .filter(
                kelas__teacher_profile_id__in=tp_ids,
                status=EnrollmentStatus.ACTIVE,
                is_deleted=False,
            )
            .values('kelas__teacher_profile')
            .annotate(n=Count('student_profile', distinct=True))
            .values_list('kelas__teacher_profile', 'n')
        )
        top_teachers = []
        for r in rows:
            tp = profiles_by_id.get(r['teacher_profile'])
            if tp:
                top_teachers.append({
                    'profile': tp,
                    'avg_rating': round(r['avg_score'], 1),
                    'rating_count': r['rating_count'],
                    'student_count': student_counts.get(r['teacher_profile'], 0),
                })
        cache.set('admin_top_teachers', top_teachers, 1800)

    # ── Worst teachers (low rating + idle teachers) ────────────────────────
    worst_teachers = cache.get('admin_worst_teachers')
    if worst_teachers is None:
        rated_low = (
            TeacherRating.objects.values('teacher_profile')
            .annotate(avg_score=Avg('score'), rating_count=Count('id'))
            .filter(rating_count__gte=2)
            .order_by('avg_score')[:3]
        )
        rows = list(rated_low)
        tp_ids = [r['teacher_profile'] for r in rows]
        profiles_by_id = {
            tp.pk: tp for tp in
            TeacherProfile.objects.filter(pk__in=tp_ids).select_related('user')
        }
        student_counts = dict(
            Enrollment.objects
            .filter(kelas__teacher_profile_id__in=tp_ids, status=EnrollmentStatus.ACTIVE, is_deleted=False)
            .values('kelas__teacher_profile')
            .annotate(n=Count('student_profile', distinct=True))
            .values_list('kelas__teacher_profile', 'n')
        )
        active_class_counts = dict(
            Kelas.objects
            .filter(teacher_profile_id__in=tp_ids, is_deleted=False)
            .exclude(status=KelasStatus.CLOSED)
            .values('teacher_profile')
            .annotate(n=Count('id'))
            .values_list('teacher_profile', 'n')
        )
        worst_teachers = []
        already_listed_ids = set()
        for r in rows:
            tp = profiles_by_id.get(r['teacher_profile'])
            if tp:
                already_listed_ids.add(tp.pk)
                worst_teachers.append({
                    'profile': tp,
                    'avg_rating': round(r['avg_score'], 1),
                    'student_count': student_counts.get(r['teacher_profile'], 0),
                    'active_classes': active_class_counts.get(r['teacher_profile'], 0),
                })
        # Pad with idle teachers (no active classes)
        idle = (
            TeacherProfile.objects
            .filter(user__approval_status=ApprovalStatus.APPROVED, user__is_deleted=False)
            .exclude(pk__in=already_listed_ids)
            .annotate(active_n=Count(
                'taught_classes',
                filter=Q(taught_classes__is_deleted=False) & ~Q(taught_classes__status=KelasStatus.CLOSED),
            ))
            .filter(active_n=0)
            .select_related('user')[:2]
        )
        for tp in idle:
            worst_teachers.append({
                'profile': tp,
                'avg_rating': None,
                'student_count': 0,
                'active_classes': 0,
            })
        worst_teachers = worst_teachers[:5]
        cache.set('admin_worst_teachers', worst_teachers, 1800)

    # ── Popular + Sepi classes ─────────────────────────────────────────────
    base_classes = (
        Kelas.objects
        .filter(is_deleted=False, status=KelasStatus.OPEN)
        .select_related('teacher_profile__user', 'subject')
        .annotate(active_count=Count(
            'enrollments',
            filter=Q(enrollments__status=EnrollmentStatus.ACTIVE, enrollments__is_deleted=False),
        ))
    )
    popular_classes = list(base_classes.order_by('-active_count')[:3])
    sepi_classes = list(base_classes.order_by('active_count')[:3])

    # ── Activity log (8 latest) ────────────────────────────────────────────
    activity_logs = list(
        ActivityLog.objects
        .select_related('user')
        .order_by('-created_at')[:8]
    )

    # ── Foundation KPIs (Data Pro v5) ──────────────────────────────────────
    # The redesigned dashboard surfaces four canonical counters.
    total_students = User.objects.filter(role=Role.STUDENT, is_deleted=False).count()
    total_teachers = User.objects.filter(role=Role.TEACHER, is_deleted=False).count()
    active_classes_count = Kelas.objects.filter(
        is_deleted=False, status=KelasStatus.OPEN
    ).count()
    pending_count = kpi['pending_users']

    # ── Enrollment trend (last 6 calendar months, oldest → newest) ─────────
    # Group by (year, month) of enrolled_at. Build six buckets so months with
    # zero enrollments still render as a 0-height bar.
    from collections import OrderedDict
    today_d = today
    months = []
    for i in range(5, -1, -1):
        year = today_d.year
        month = today_d.month - i
        while month <= 0:
            month += 12
            year -= 1
        months.append((year, month))
    enroll_rows = (
        Enrollment.objects
        .filter(is_deleted=False,
                enrolled_at__date__gte=date(months[0][0], months[0][1], 1))
        .values_list('enrolled_at', flat=True)
    )
    counts = {(y, m): 0 for y, m in months}
    for ts in enroll_rows:
        key = (ts.year, ts.month)
        if key in counts:
            counts[key] += 1
    _MONTH_ID = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun',
                 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des']
    enrollment_chart_6mo = []
    max_count = max(counts.values()) if counts else 0
    for (y, m) in months:
        c = counts[(y, m)]
        pct = int(c * 100 / max_count) if max_count else 0
        enrollment_chart_6mo.append({
            'label': _MONTH_ID[m],
            'count': c,
            'pct': pct,
        })

    # ── Jenjang distribution (students only, by level) ─────────────────────
    jenjang_rows = (
        StudentProfile.objects
        .filter(user__is_deleted=False, user__role=Role.STUDENT)
        .values('level')
        .annotate(n=Count('id'))
    )
    jenjang_distribution_map = {r['level'] or 'Lainnya': r['n'] for r in jenjang_rows}
    jenjang_order = ['TK', 'SD', 'SMP', 'SMA', 'UMUM']
    jenjang_total = sum(jenjang_distribution_map.values()) or 0
    # Teal shade per slice — light → dark to match the donut spec.
    _JENJANG_COLORS = {
        'TK':   '#c2e4e6',
        'SD':   '#7fcacd',
        'SMP':  '#5fb3b7',
        'SMA':  '#4a9499',
        'UMUM': '#326568',
    }
    jenjang_distribution = []
    cumulative_pct = 0.0
    for lvl in jenjang_order:
        n = jenjang_distribution_map.get(lvl, 0)
        pct = (n * 100.0 / jenjang_total) if jenjang_total else 0.0
        jenjang_distribution.append({
            'level': lvl,
            'count': n,
            'pct': round(pct, 1),
            'pct_start': round(cumulative_pct, 2),
            'pct_end': round(cumulative_pct + pct, 2),
            'color': _JENJANG_COLORS[lvl],
        })
        cumulative_pct += pct

    return render(request, 'dashboard/admin.html', {
        'today': today,
        'now_dt': now_dt,
        'kpi': kpi,
        'pending_users_data': pending_users_data,
        'pending_total': kpi['pending_users'],
        'top_students': top_students,
        'worst_students': worst_students,
        'top_teachers': top_teachers,
        'worst_teachers': worst_teachers,
        'popular_classes': popular_classes,
        'sepi_classes': sepi_classes,
        'activity_logs': activity_logs,
        # Data Pro v5 foundation
        'total_students': total_students,
        'total_teachers': total_teachers,
        'active_classes_count': active_classes_count,
        'pending_count': pending_count,
        'enrollment_chart_6mo': enrollment_chart_6mo,
        'jenjang_distribution': jenjang_distribution,
        'jenjang_total': jenjang_total,
    })
