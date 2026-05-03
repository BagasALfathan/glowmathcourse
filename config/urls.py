from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView, TemplateView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('robots.txt', TemplateView.as_view(template_name='robots.txt', content_type='text/plain')),
    path('', RedirectView.as_view(url='/login/', permanent=False), name='home'),
    path('', include('accounts.urls')),
    path('dashboard/', include('dashboard.urls')),
    path('admin-panel/', include('admin_panel.urls')),
    path('', include('academics.urls')),
    path('', include('enrollments.urls')),
    path('', include('grades.urls')),
    path('', include('sessions.urls')),
    path('', include('sessions_app.urls')),
    path('', include('ratings.urls')),
    path('', include('announcements.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
