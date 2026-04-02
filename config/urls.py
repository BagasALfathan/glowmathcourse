from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
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
]
