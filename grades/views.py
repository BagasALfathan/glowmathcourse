from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from academics.models import Kelas
from accounts.decorators import role_required
from enrollments.models import Enrollment, EnrollmentStatus

from .forms import GradeForm
from .models import Grade


# ─── Teacher views ────────────────────────────────────────────────────────────

@role_required('TEACHER')
def teacher_grades(request, pk):
    kelas = get_object_or_404(Kelas, pk=pk, teacher=request.user, is_deleted=False)

    enrollments = (
        Enrollment.objects
        .filter(kelas=kelas, status=EnrollmentStatus.ACTIVE, is_deleted=False)
        .select_related('student__student_profile')
        .order_by('student__last_name', 'student__first_name')
    )

    # Prefetch grades per enrollment to avoid N+1
    enrollment_ids = [e.pk for e in enrollments]
    all_grades = (
        Grade.objects
        .filter(enrollment_id__in=enrollment_ids)
        .select_related('session')
        .order_by('grade_type', '-graded_at')
    )
    grades_by_enrollment = {}
    for grade in all_grades:
        grades_by_enrollment.setdefault(grade.enrollment_id, []).append(grade)

    rows = [
        {
            'enrollment': e,
            'grades': grades_by_enrollment.get(e.pk, []),
        }
        for e in enrollments
    ]

    return render(request, 'grades/teacher_grades.html', {
        'kelas': kelas,
        'rows': rows,
    })


@role_required('TEACHER')
def teacher_grade_create(request):
    # kelas_id comes from GET (initial load) or POST (hidden field on submit)
    kelas_id = request.POST.get('kelas_id') or request.GET.get('kelas_id')
    kelas = get_object_or_404(Kelas, pk=kelas_id, teacher=request.user, is_deleted=False)

    form = GradeForm(request.POST or None, kelas=kelas)

    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Nilai berhasil ditambahkan!')
        return redirect('grades:teacher_grades', pk=kelas.pk)

    return render(request, 'grades/teacher_grade_form.html', {
        'kelas': kelas,
        'form': form,
        'action': 'create',
        'form_title': 'Tambah Nilai',
    })


@role_required('TEACHER')
def teacher_grade_edit(request, pk):
    grade = get_object_or_404(Grade.objects.select_related('enrollment__kelas'), pk=pk)
    kelas = grade.enrollment.kelas

    if kelas.teacher != request.user:
        messages.error(request, 'Anda tidak memiliki akses untuk mengubah nilai ini.')
        return redirect('academics:teacher_classes')

    form = GradeForm(request.POST or None, instance=grade, kelas=kelas)

    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Nilai berhasil diperbarui!')
        return redirect('grades:teacher_grades', pk=kelas.pk)

    return render(request, 'grades/teacher_grade_form.html', {
        'kelas': kelas,
        'form': form,
        'grade': grade,
        'action': 'edit',
        'form_title': 'Edit Nilai',
    })


@role_required('TEACHER')
@require_POST
def teacher_grade_delete(request, pk):
    grade = get_object_or_404(Grade.objects.select_related('enrollment__kelas'), pk=pk)
    kelas = grade.enrollment.kelas

    if kelas.teacher != request.user:
        messages.error(request, 'Anda tidak memiliki akses untuk menghapus nilai ini.')
        return redirect('academics:teacher_classes')

    grade.delete()
    messages.success(request, 'Nilai berhasil dihapus.')
    return redirect('grades:teacher_grades', pk=kelas.pk)


# ─── Student views ─────────────────────────────────────────────────────────────

@role_required('STUDENT')
def my_grades(request):
    enrollments = list(
        Enrollment.objects
        .filter(student=request.user, status=EnrollmentStatus.ACTIVE, is_deleted=False)
        .select_related('kelas__subject', 'kelas__teacher')
        .order_by('kelas__name')
    )
    enrollment_ids = [e.pk for e in enrollments]

    all_grades = list(
        Grade.objects
        .filter(enrollment_id__in=enrollment_ids)
        .select_related('session')
        .order_by('grade_type', '-graded_at')
    )
    grades_by_enrollment = {}
    for grade in all_grades:
        grades_by_enrollment.setdefault(grade.enrollment_id, []).append(grade)

    rows = []
    for e in enrollments:
        grades = grades_by_enrollment.get(e.pk, [])
        avg = round(sum(float(g.score) for g in grades) / len(grades), 1) if grades else None
        rows.append({'enrollment': e, 'grades': grades, 'avg': avg})

    recent_grades = (
        Grade.objects
        .filter(enrollment_id__in=enrollment_ids)
        .select_related('enrollment__kelas__subject')
        .order_by('-graded_at')[:5]
    )

    return render(request, 'grades/my_grades.html', {
        'rows': rows,
        'recent_grades': recent_grades,
    })


@role_required('STUDENT')
def my_grades_detail(request, kelas_id):
    kelas = get_object_or_404(Kelas, pk=kelas_id, is_deleted=False)
    enrollment = get_object_or_404(
        Enrollment,
        student=request.user,
        kelas=kelas,
        is_deleted=False,
    )

    grades = list(
        Grade.objects
        .filter(enrollment=enrollment)
        .select_related('session')
        .order_by('grade_type', '-graded_at')
    )

    scores = [float(g.score) for g in grades]
    avg = round(sum(scores) / len(scores), 1) if scores else None
    highest = max(scores, default=None)
    lowest = min(scores, default=None)

    return render(request, 'grades/my_grades_detail.html', {
        'kelas': kelas,
        'enrollment': enrollment,
        'grades': grades,
        'avg': avg,
        'highest': highest,
        'lowest': lowest,
        'total': len(grades),
    })
