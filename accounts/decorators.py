from functools import wraps
from django.shortcuts import redirect, render


def role_required(*roles):
    """Restrict a view to users with one of the specified roles.

    - Unauthenticated → redirect to login
    - Wrong role      → 403 Forbidden page
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('accounts:login')
            if request.user.role not in roles:
                return render(request, '403.html', status=403)
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
