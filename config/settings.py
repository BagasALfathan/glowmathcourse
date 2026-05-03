# This file is superseded by the config/settings/ package.
# Python imports config.settings as the package (directory), not this file.
#
# Use:
#   config.settings.dev        — local development (default in manage.py)
#   config.settings.production — Railway / production (default in wsgi.py)
#
# Set DJANGO_SETTINGS_MODULE env variable to override.
raise ImportError(
    "Import config.settings.dev or config.settings.production directly. "
    "This file exists only as a redirect notice."
)
