from django.apps import AppConfig


class RatingsConfig(AppConfig):
    name = 'ratings'

    def ready(self):
        from . import signals  # noqa: F401
