from django.apps import AppConfig


class SessionsAppConfig(AppConfig):
    name = 'sessions_app'

    def ready(self):
        # Register signal handlers for cache invalidation.
        from . import signals  # noqa: F401
