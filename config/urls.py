from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView

from dashboard.views import help_view

urlpatterns = [
    # Django built-in admin moved here to free /admin/ for the custom admin portal
    path('django-admin/', admin.site.urls),
    path('robots.txt', TemplateView.as_view(template_name='robots.txt', content_type='text/plain')),

    # Auth (3-portal layout)
    path('', include('accounts.urls')),

    path('dashboard/', include('dashboard.urls')),
    path('admin-panel/', include('admin_panel.urls')),

    # Help/Bantuan — mounted at root so the URL is /help/
    path('help/', help_view, name='help'),

    # Student see-all pages — must come BEFORE enrollments/sessions/grades
    # so /my-classes/, /my-attendance/, /my-monthly-score/ resolve here.
    path('', include('student.urls')),

    path('', include('academics.urls')),
    path('', include('enrollments.urls')),
    path('', include('grades.urls')),
    path('', include('sessions.urls')),
    path('', include('sessions_app.urls')),
    path('', include('ratings.urls')),
    path('', include('announcements.urls')),
    path('', include('journals.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
