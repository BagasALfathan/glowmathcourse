from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from academics.models import Kelas
from accounts.decorators import role_required

from .forms import SessionForm
from .models import Session, SessionStatus


@role_required('TEACHER')
def teacher_sessions(request, pk):
    kelas = get_object_or_404(Kelas, pk=pk, teacher=request.user, is_deleted=False)
    sessions = Session.objects.filter(kelas=kelas).order_by('session_number')
    completed_count = sessions.filter(status=SessionStatus.COMPLETED).count()
    next_number = sessions.count() + 1  # next session_number if all are created in order

    # Check how many have been created so far (regardless of status)
    created_count = sessions.count()
    can_create = created_count < kelas.total_sessions

    return render(request, 'sessions_app/teacher_sessions.html', {
        'kelas': kelas,
        'sessions': sessions,
        'completed_count': completed_count,
        'created_count': created_count,
        'can_create': can_create,
        'SessionStatus': SessionStatus,
    })


@role_required('TEACHER')
def teacher_session_create(request, kelas_id):
    kelas = get_object_or_404(Kelas, pk=kelas_id, teacher=request.user, is_deleted=False)

    # Determine next session number
    last_session = Session.objects.filter(kelas=kelas).order_by('-session_number').first()
    next_number = (last_session.session_number + 1) if last_session else 1

    # Guard: cannot exceed total_sessions
    if next_number > kelas.total_sessions:
        messages.warning(request, 'Semua pertemuan sudah dibuat.')
        return redirect('sessions_app:teacher_sessions', pk=kelas.pk)

    form = SessionForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        session = form.save(commit=False)
        session.kelas = kelas
        session.session_number = next_number
        session.status = SessionStatus.SCHEDULED
        session.save()
        messages.success(request, f'Pertemuan ke-{next_number} berhasil dibuat!')
        return redirect('sessions_app:teacher_sessions', pk=kelas.pk)

    return render(request, 'sessions_app/teacher_session_create.html', {
        'kelas': kelas,
        'form': form,
        'next_number': next_number,
    })


@role_required('TEACHER')
@require_POST
def teacher_session_update_status(request, pk):
    session = get_object_or_404(Session, pk=pk)

    # Ownership check: session's kelas must belong to this teacher
    if session.kelas.teacher != request.user:
        messages.error(request, 'Anda tidak memiliki akses untuk mengubah sesi ini.')
        return redirect('academics:teacher_classes')

    new_status = request.POST.get('status', '').strip()
    if new_status not in SessionStatus.values:
        messages.error(request, 'Status tidak valid.')
        return redirect('sessions_app:teacher_sessions', pk=session.kelas_id)

    if session.status == new_status:
        return redirect('sessions_app:teacher_sessions', pk=session.kelas_id)

    session.status = new_status
    session.save(update_fields=['status', 'updated_at'])

    status_label = dict(SessionStatus.choices).get(new_status, new_status)
    messages.success(
        request,
        f'Pertemuan ke-{session.session_number} diubah menjadi {status_label}.'
    )
    return redirect('sessions_app:teacher_sessions', pk=session.kelas_id)


@role_required('TEACHER')
def teacher_attendance(request, pk):
    """Attendance marking — stub, to be implemented in a later day."""
    session = get_object_or_404(Session, pk=pk)
    if session.kelas.teacher != request.user:
        messages.error(request, 'Akses ditolak.')
        return redirect('academics:teacher_classes')
    return render(request, 'coming_soon.html', {'feature_name': 'Absensi Pertemuan'})
