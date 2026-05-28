"""Feature-rich 'see all' pages for the student role.

These three views replace the simpler enrollments/sessions versions at the
same URLs. The student URLconf is mounted before enrollments/sessions in
config/urls.py so /my-classes/ and /my-attendance/ resolve here.
"""
from collections import defaultdict
from datetime import date

from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q
from django.shortcuts import render

from accounts.decorators import role_required
from enrollments.models import Enrollment, EnrollmentStatus
from grades.models import Grade
from journals.models import MonthlyJournal
from sessions_app.models import Attendance, AttendanceStatus, SessionStatus


# ─── My Classes ────────────────────────────────────────────────────────────


@role_required('STUDENT')
def my_classes(request):
    student_profile = request.user.student_profile

    qs = (
        Enrollment.objects
        .filter(student_profile=student_profile, is_deleted=False)
        .select_related(
            'kelas__subject',
            'kelas__teacher_profile__user',
            'kelas__academic_period',
        )
        .annotate(
            total_sessions_count=Count('kelas__sessions', distinct=True),
            completed_sessions_count=Count(
                'kelas__sessions',
                filter=Q(kelas__sessions__status=SessionStatus.COMPLETED),
                distinct=True,
            ),
        )
    )

    search = (request.GET.get('search') or '').strip()
    status_filter = (request.GET.get('status') or '').strip()

    if search:
        qs = qs.filter(
            Q(kelas__name__icontains=search)
            | Q(kelas__subject__name__icontains=search)
            | Q(kelas__teacher_profile__user__first_name__icontains=search)
            | Q(kelas__teacher_profile__user__last_name__icontains=search)
        )
    if status_filter in {EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED, EnrollmentStatus.DROPPED}:
        qs = qs.filter(status=status_filter)

    qs = qs.order_by('-enrolled_at')

    paginator = Paginator(qs, 12)
    page_obj = paginator.get_page(request.GET.get('page') or 1)

    # Mark COMPLETED enrollments on this page that still need a rating.
    from ratings.models import TeacherRating
    completed_ids_in_page = [
        e.pk for e in page_obj.object_list if e.status == EnrollmentStatus.COMPLETED
    ]
    rated_ids = set(
        TeacherRating.objects.filter(enrollment_id__in=completed_ids_in_page)
        .values_list('enrollment_id', flat=True)
    ) if completed_ids_in_page else set()

    for enr in page_obj.object_list:
        total = enr.kelas.total_sessions or enr.total_sessions_count or 0
        completed = enr.completed_sessions_count or 0
        enr.progress_pct = int(completed * 100 / total) if total else 0
        enr.needs_rating = (
            enr.status == EnrollmentStatus.COMPLETED and enr.pk not in rated_ids
        )

    return render(request, 'student/my_classes.html', {
        'page_obj': page_obj,
        'total_count': paginator.count,
        'search': search,
        'status_filter': status_filter,
        'qs_preserve': _qs_without_page(request),
    })


# ─── My Attendance ─────────────────────────────────────────────────────────


@role_required('STUDENT')
def my_attendance(request):
    student_profile = request.user.student_profile

    records = (
        Attendance.objects
        .filter(enrollment__student_profile=student_profile)
        .select_related(
            'enrollment__kelas__subject',
            'enrollment__kelas__teacher_profile__user',
            'session',
        )
        .order_by('-session__date', '-session__start_time')
    )

    class_filter = (request.GET.get('class') or '').strip()
    status_filter = (request.GET.get('status') or '').strip()

    if class_filter.isdigit():
        records = records.filter(enrollment__kelas_id=int(class_filter))
    if status_filter in {AttendanceStatus.PRESENT, AttendanceStatus.PERMITTED, AttendanceStatus.ABSENT}:
        records = records.filter(status=status_filter)

    # KPI totals (re-query with the same filters, no slice)
    base_for_totals = records  # before pagination
    total = base_for_totals.count()
    present = base_for_totals.filter(status=AttendanceStatus.PRESENT).count()
    permitted = base_for_totals.filter(status=AttendanceStatus.PERMITTED).count()
    absent = base_for_totals.filter(status=AttendanceStatus.ABSENT).count()
    attendance_rate = round(present * 100 / total) if total else 0

    paginator = Paginator(records, 25)
    page_obj = paginator.get_page(request.GET.get('page') or 1)

    my_classes_list = list(
        Enrollment.objects
        .filter(student_profile=student_profile, is_deleted=False)
        .select_related('kelas')
        .values('kelas_id', 'kelas__name')
        .distinct()
        .order_by('kelas__name')
    )

    return render(request, 'student/my_attendance.html', {
        'page_obj': page_obj,
        'total_records': total,
        'present_count': present,
        'permitted_count': permitted,
        'absent_count': absent,
        'attendance_rate': attendance_rate,
        'class_filter': class_filter,
        'status_filter': status_filter,
        'my_classes': my_classes_list,
        'qs_preserve': _qs_without_page(request),
    })


# ─── My Monthly Score ──────────────────────────────────────────────────────


@role_required('STUDENT')
def my_monthly_score(request):
    student_profile = request.user.student_profile

    grades = (
        Grade.objects
        .filter(enrollment__student_profile=student_profile)
        .select_related('enrollment__kelas__subject', 'enrollment__kelas__teacher_profile__user')
    )

    # Aggregate per (year, month, kelas_id) in Python — cheap for typical N
    bucket = defaultdict(lambda: {'scores': [], 'enrollment': None, 'kelas': None})
    for g in grades:
        when = g.graded_at if g.graded_at else g.created_at
        if not when:
            continue
        key = (when.year, when.month, g.enrollment.kelas_id)
        b = bucket[key]
        b['scores'].append(float(g.score))
        b['enrollment'] = g.enrollment
        b['kelas'] = g.enrollment.kelas

    monthly_list = []
    for (year, month, _kelas_id), data in bucket.items():
        if not data['scores']:
            continue
        avg = sum(data['scores']) / len(data['scores'])
        monthly_list.append({
            'year': year,
            'month': month,
            'kelas': data['kelas'],
            'enrollment': data['enrollment'],
            'avg_score': round(avg, 1),
            'grade_count': len(data['scores']),
            'journal': None,  # filled below
        })

    # Attach journals (single batch query per unique enrollment)
    enrollment_ids = {m['enrollment'].id for m in monthly_list}
    journals_by_key = {}
    if enrollment_ids:
        for j in MonthlyJournal.objects.filter(
            enrollment_id__in=enrollment_ids, published_at__isnull=False,
        ).select_related('written_by_teacher__user'):
            journals_by_key[(j.year, j.month, j.enrollment_id)] = j
    for m in monthly_list:
        m['journal'] = journals_by_key.get((m['year'], m['month'], m['enrollment'].id))

    monthly_list.sort(key=lambda x: (x['year'], x['month']), reverse=True)

    class_filter = (request.GET.get('class') or '').strip()
    if class_filter.isdigit():
        cf = int(class_filter)
        monthly_list = [m for m in monthly_list if m['kelas'].id == cf]

    paginator = Paginator(monthly_list, 12)
    page_obj = paginator.get_page(request.GET.get('page') or 1)

    overall = grades.aggregate(avg=Avg('score'))['avg']
    overall_avg = round(float(overall), 1) if overall is not None else 0

    my_classes_list = list(
        Enrollment.objects
        .filter(student_profile=student_profile, is_deleted=False)
        .select_related('kelas')
        .values('kelas_id', 'kelas__name')
        .distinct()
        .order_by('kelas__name')
    )

    return render(request, 'student/my_monthly_score.html', {
        'page_obj': page_obj,
        'total_months': len(monthly_list),
        'overall_avg': overall_avg,
        'class_filter': class_filter,
        'my_classes': my_classes_list,
        'qs_preserve': _qs_without_page(request),
    })


# ─── Shared helper ─────────────────────────────────────────────────────────


def _qs_without_page(request):
    """Rebuild the current querystring without the `page` key (for pagination links)."""
    parts = []
    for key, values in request.GET.lists():
        if key == 'page':
            continue
        for v in values:
            if v:
                parts.append(f'{key}={v}')
    return '&'.join(parts)
