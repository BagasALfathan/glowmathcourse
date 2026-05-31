from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.decorators import role_required
from activity_logs.utils import log_activity

from .models import MonthlyJournal


@role_required('TEACHER')
def teacher_journal_write(request, enrollment_id, year, month):
    """Teacher writes / edits a MonthlyJournal for one enrollment + (year, month).

    Single endpoint handles BOTH create and edit thanks to the unique constraint
    on (enrollment, month, year) — we look the row up first; if it exists we
    edit, otherwise we create on save. Ownership: enrollment must belong to a
    kelas this teacher owns, else 404.
    """
    from enrollments.models import Enrollment

    teacher_profile = request.user.teacher_profile
    enrollment = get_object_or_404(
        Enrollment.objects.select_related(
            'student_profile__user', 'kelas__subject', 'kelas__teacher_profile',
        ),
        pk=enrollment_id,
        kelas__teacher_profile=teacher_profile,
        kelas__is_deleted=False,
        is_deleted=False,
    )

    if not (1 <= month <= 12):
        messages.error(request, 'Bulan tidak valid.')
        return redirect(
            'grades:teacher_student_progress',
            pk=enrollment.kelas_id, enrollment_id=enrollment.pk,
        )

    journal = MonthlyJournal.objects.filter(
        enrollment=enrollment, month=month, year=year,
    ).first()
    mode = 'edit' if journal else 'create'

    if request.method == 'POST':
        data = {
            'summary': (request.POST.get('summary') or '').strip(),
            'topics_covered': (request.POST.get('topics_covered') or '').strip(),
            'strengths': (request.POST.get('strengths') or '').strip(),
            'areas_for_improvement': (request.POST.get('areas_for_improvement') or '').strip(),
        }
        errors = [k for k, v in data.items() if not v]
        publish_now = request.POST.get('publish') == '1'

        if errors:
            messages.error(request, 'Semua kolom wajib diisi (ringkasan, topik, kekuatan, perlu ditingkatkan).')
            return render(request, 'journals/teacher_journal_form.html', {
                'mode': mode, 'enrollment': enrollment,
                'year': year, 'month': month,
                'journal': journal, 'form_data': data,
            })

        if journal is None:
            journal = MonthlyJournal.objects.create(
                enrollment=enrollment,
                month=month, year=year,
                written_by_teacher=teacher_profile,
                **data,
                published_at=timezone.now() if publish_now else None,
            )
            log_activity(request.user, 'created', 'monthly_journal', journal.pk)
            messages.success(request, f'✓ Jurnal {month:02d}/{year} berhasil dibuat.')
        else:
            for k, v in data.items():
                setattr(journal, k, v)
            journal.written_by_teacher = teacher_profile
            if publish_now and journal.published_at is None:
                journal.published_at = timezone.now()
            journal.save()
            log_activity(request.user, 'updated', 'monthly_journal', journal.pk)
            messages.success(request, f'✓ Jurnal {month:02d}/{year} berhasil diperbarui.')

        return redirect(
            'grades:teacher_student_progress',
            pk=enrollment.kelas_id, enrollment_id=enrollment.pk,
        )

    return render(request, 'journals/teacher_journal_form.html', {
        'mode': mode, 'enrollment': enrollment,
        'year': year, 'month': month,
        'journal': journal, 'form_data': None,
    })


@role_required('STUDENT')
def my_journals(request):
    qs = (
        MonthlyJournal.objects
        .filter(
            enrollment__student_profile__user=request.user,
            published_at__isnull=False,
        )
        .select_related(
            'enrollment__kelas__subject',
            'written_by_teacher__user',
        )
        .order_by('-year', '-month')
    )
    return render(request, 'journals/my_journals.html', {'journals': qs})


@role_required('STUDENT')
def journal_detail(request, pk):
    journal = get_object_or_404(
        MonthlyJournal.objects.select_related(
            'enrollment__kelas__subject',
            'enrollment__student_profile__user',
            'written_by_teacher__user',
        ),
        pk=pk,
        enrollment__student_profile__user=request.user,
    )

    if not journal.viewed_by_parent and request.user.role == 'STUDENT':
        from django.utils import timezone
        journal.viewed_by_parent = True
        journal.viewed_at = timezone.now()
        journal.save(update_fields=['viewed_by_parent', 'viewed_at', 'updated_at'])

    return render(request, 'journals/journal_detail.html', {'journal': journal})
