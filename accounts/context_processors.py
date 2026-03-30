from .models import ApprovalStatus, Role


def pending_users_count(request):
    if (
        request.user.is_authenticated
        and hasattr(request.user, 'role')
        and request.user.role == Role.ADMIN
    ):
        from .models import User
        count = User.objects.filter(
            approval_status=ApprovalStatus.PENDING, is_deleted=False
        ).count()
        return {'pending_users_count': count}
    return {'pending_users_count': 0}
