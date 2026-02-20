"""
URL configuration for core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
import importlib.util

from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve
from django.http import HttpResponse
from . import views
from apps.users.views import CustomLoginView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/login/', CustomLoginView.as_view(), name='login'),
    path('accounts/', include('django.contrib.auth.urls')),  # Add Django auth URLs
    path('', views.main_dashboard, name='main_dashboard'), # Main Landing Dashboard
    path('restore-data/', views.restore_data_view, name='restore_data'),
    path('run-migrations/', views.run_migrations_view, name='run_migrations'),
    path('diag/login-flow/', views.login_flow_diag_view, name='login_flow_diag'),
    path('ping/', lambda r: HttpResponse("pong"), name='ping'),
    path('expenses/', include('apps.expenses.urls')), # Move expenses to sub-path
    path('ticketing/', include('apps.ticketing.urls')), # Ticketing System
    path('attendance/', include('apps.hr_attendance.urls')), # Attendance System
    path('personnel/', include('apps.hr_personnel.urls')), # Personnel & Payroll
    path('hrms/', include('apps.hrms.urls')),
    path('users/', include('apps.users.urls')),
    path('organizations/', include('apps.organizations.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if importlib.util.find_spec('rest_framework'):
    urlpatterns.append(path('api/hrms/', include('apps.hrms.api_urls')))

if not settings.DEBUG:
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
    ]
