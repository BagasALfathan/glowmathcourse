from django.apps import AppConfig


class EnrollmentsConfig(AppConfig):
    name = 'enrollments'

    def ready(self):
        # Register signal handlers for cache invalidation.
        from . import signals  # noqa: F401
