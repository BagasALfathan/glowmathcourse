from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Notification


@login_required
def my_notifications(request):
    """List the signed-in user's notifications, newest first, paginated."""
    qs = Notification.objects.filter(user=request.user).order_by('-created_at')
    paginator = Paginator(qs, 25)
    page = paginator.get_page(request.GET.get('page') or 1)
    unread_count = qs.filter(is_read=False).count()
    return render(request, 'notifications/list.html', {
        'page_obj': page,
        'notifications': page.object_list,
        'unread_count': unread_count,
        'total_count': qs.count(),
    })


@login_required
@require_POST
def mark_notification_read(request, pk):
    """Mark a single notification as read. Ownership enforced via filter."""
    notif = get_object_or_404(Notification, pk=pk, user=request.user)
    if not notif.is_read:
        notif.is_read = True
        notif.read_at = timezone.now()
        notif.save(update_fields=['is_read', 'read_at', 'updated_at'])

    next_url = request.POST.get('next') or notif.link_url
    if next_url:
        return HttpResponseRedirect(next_url)
    return redirect('notifications:list')


@login_required
@require_POST
def mark_all_read(request):
    """Mark every unread notification for the signed-in user as read."""
    now = timezone.now()
    updated = Notification.objects.filter(
        user=request.user, is_read=False,
    ).update(is_read=True, read_at=now, updated_at=now)
    if updated:
        messages.success(request, f'✓ {updated} notifikasi ditandai dibaca.')
    return redirect('notifications:list')
