"""Email-as-credential authentication backend.

The client revision (Phase 3R Grup A item 1) moved login from username
to email. The Django ModelBackend ships configured for username — this
backend wraps a lookup-by-email path so Django's `authenticate()` call
sites work uniformly with email credentials.

ModelBackend stays as a fallback in AUTHENTICATION_BACKENDS so users
who logged in with their generated username (or whose registration was
pre-rebrand) still resolve.
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        User = get_user_model()
        # Django's `authenticate(username=...)` is the canonical call; treat
        # the value as either email or kwargs['email'].
        email = (kwargs.get('email') or username or '').strip()
        if not email or password is None:
            return None
        try:
            user = User.objects.get(email__iexact=email, is_deleted=False)
        except User.DoesNotExist:
            return None
        except User.MultipleObjectsReturned:
            # Defensive — email should be unique post-Phase-3R, but legacy
            # rows might violate. Pick the oldest (lowest pk) deterministically.
            user = (
                User.objects
                .filter(email__iexact=email, is_deleted=False)
                .order_by('id')
                .first()
            )
            if user is None:
                return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
