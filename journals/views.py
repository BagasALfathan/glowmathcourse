from django.contrib import messages
from django.shortcuts import get_object_or_404, render

from accounts.decorators import role_required

from .models import MonthlyJournal


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
