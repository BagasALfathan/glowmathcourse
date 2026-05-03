from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import role_required
from accounts.models import Role

from .models import Announcement


def _announcements_for_user(user):
    """Return active announcements relevant to this user, ordered pinned-first."""
    qs = Announcement.objects.filter(is_active=True).select_related('author')
    role = user.role
    if role == Role.STUDENT:
        try:
            level = user.student_profile.level
        except Exception:
            level = None
        q = Q(target_role=Announcement.TargetRole.ALL) | Q(
            target_role=Announcement.TargetRole.STUDENT,
            level=Announcement.TargetLevel.ALL,
        )
        if level:
            q |= Q(target_role=Announcement.TargetRole.STUDENT, level=level)
        return qs.filter(q).order_by('-is_pinned', '-created_at')
    elif role == Role.TEACHER:
        return qs.filter(
            Q(target_role=Announcement.TargetRole.ALL) |
            Q(target_role=Announcement.TargetRole.TEACHER)
        ).order_by('-is_pinned', '-created_at')
    else:  # ADMIN sees all
        return qs.order_by('-is_pinned', '-created_at')


@login_required
def announcements_list(request):
    announcements = _announcements_for_user(request.user)
    return render(request, 'announcements/list.html', {
        'announcements': announcements,
    })


@login_required
def announcement_detail(request, pk):
    ann = get_object_or_404(Announcement, pk=pk, is_active=True)
    # Check visibility
    user = request.user
    role = user.role
    if role == Role.STUDENT:
        visible = _announcements_for_user(user).filter(pk=pk).exists()
        if not visible:
            from django.http import Http404
            raise Http404
    elif role == Role.TEACHER:
        if ann.target_role == Announcement.TargetRole.STUDENT:
            from django.http import Http404
            raise Http404
    return render(request, 'announcements/detail.html', {'ann': ann})


@role_required('ADMIN', 'TEACHER')
def announcement_create(request):
    is_teacher = request.user.role == Role.TEACHER
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()
        is_pinned = request.POST.get('is_pinned') == 'on'
        if is_teacher:
            target_role = Announcement.TargetRole.STUDENT
        else:
            target_role = request.POST.get('target_role', Announcement.TargetRole.ALL)
        level = request.POST.get('level', Announcement.TargetLevel.ALL)
        if target_role != Announcement.TargetRole.STUDENT:
            level = Announcement.TargetLevel.ALL

        if not title or not content:
            messages.error(request, 'Judul dan isi pengumuman wajib diisi.')
        else:
            Announcement.objects.create(
                author=request.user,
                title=title,
                content=content,
                target_role=target_role,
                level=level,
                is_pinned=is_pinned,
            )
            messages.success(request, 'Pengumuman berhasil dibuat!')
            if is_teacher:
                return redirect('announcements:list')
            return redirect('admin_panel:announcements_list')
    return render(request, 'announcements/create.html', {
        'is_teacher': is_teacher,
        'target_role_choices': Announcement.TargetRole.choices,
        'level_choices': Announcement.TargetLevel.choices,
    })
