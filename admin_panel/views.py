from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from accounts.models import User, Role, ApprovalStatus

PAGE_SIZE = 20

_STATUS_TABLE_ID = {
    ApprovalStatus.PENDING: 'pending-table-wrapper',
    ApprovalStatus.APPROVED: 'approved-table-wrapper',
    ApprovalStatus.REJECTED: 'rejected-table-wrapper',
}


@role_required('ADMIN')
def pending_users_view(request):
    pending_count = User.objects.filter(
        approval_status=ApprovalStatus.PENDING, is_deleted=False
    ).count()
    return render(request, 'admin_panel/pending_users.html', {
        'pending_count': pending_count,
    })


@role_required('ADMIN')
def users_table_partial(request):
    status = request.GET.get('status', ApprovalStatus.PENDING)
    if status not in [ApprovalStatus.PENDING, ApprovalStatus.APPROVED, ApprovalStatus.REJECTED]:
        status = ApprovalStatus.PENDING

    q = request.GET.get('q', '').strip()
    role_filter = request.GET.get('role', '')
    page_num = request.GET.get('page', 1)

    qs = User.objects.filter(approval_status=status, is_deleted=False)
    if status == ApprovalStatus.APPROVED:
        qs = qs.filter(role__in=[Role.STUDENT, Role.TEACHER])

    if q:
        qs = qs.filter(
            Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(email__icontains=q)
            | Q(username__icontains=q)
        )

    if role_filter in [Role.STUDENT, Role.TEACHER]:
        qs = qs.filter(role=role_filter)

    qs = qs.order_by('-date_joined')
    paginator = Paginator(qs, PAGE_SIZE)
    page_obj = paginator.get_page(page_num)

    return render(request, 'admin_panel/_users_table.html', {
        'page_obj': page_obj,
        'status': status,
        'q': q,
        'role_filter': role_filter,
        'table_id': _STATUS_TABLE_ID.get(status, 'pending-table-wrapper'),
    })


@role_required('ADMIN')
@require_POST
def change_status_view(request, user_id):
    user = get_object_or_404(User, pk=user_id, is_deleted=False)
    new_status = request.POST.get('new_status')

    if new_status == ApprovalStatus.APPROVED:
        user.approval_status = ApprovalStatus.APPROVED
        user.is_active = True
        user.save()
        messages.success(
            request,
            f'Akun {user.get_full_name() or user.username} berhasil disetujui.',
        )
    elif new_status == ApprovalStatus.REJECTED:
        user.approval_status = ApprovalStatus.REJECTED
        user.is_active = False
        user.save()
        messages.warning(
            request,
            f'Akun {user.get_full_name() or user.username} telah ditolak/dicabut.',
        )
    else:
        messages.error(request, 'Status tidak valid.')

    return redirect('admin_panel:pending_users')


# ── Admin stub views (to be replaced with full implementations) ────────────────

def _admin_stub(request, feature_name):
    return render(request, 'coming_soon.html', {'feature_name': feature_name})


@role_required('ADMIN')
def users_list(request):
    return _admin_stub(request, 'Manajemen Pengguna')


@role_required('ADMIN')
def classes_list(request):
    return _admin_stub(request, 'Manajemen Kelas')


@role_required('ADMIN')
def subjects_list(request):
    return _admin_stub(request, 'Manajemen Mata Pelajaran')


@role_required('ADMIN')
def categories_list(request):
    return _admin_stub(request, 'Manajemen Kategori')


@role_required('ADMIN')
def periods_list(request):
    return _admin_stub(request, 'Periode Akademik')


@role_required('ADMIN')
def enrollments_list(request):
    return _admin_stub(request, 'Manajemen Pendaftaran')


@role_required('ADMIN')
def grades_list(request):
    return _admin_stub(request, 'Manajemen Nilai')


@role_required('ADMIN')
def ratings_list(request):
    return _admin_stub(request, 'Manajemen Rating')


@role_required('ADMIN')
def logs_list(request):
    return _admin_stub(request, 'Log Aktivitas')
