from .models import ActivityLog


def log_activity(user, action, target_type, target_id=None):
    """
    Record an activity log entry.

    Args:
        user: The User instance performing the action (can be None for system actions)
        action: String like "created", "updated", "deleted", "approved", "rejected"
        target_type: String like "kelas", "enrollment", "grade", "attendance", "rating", "user"
        target_id: Integer PK of the target object (optional)
    """
    ActivityLog.objects.create(
        user=user,
        action=action,
        target_type=target_type,
        target_id=target_id,
    )
