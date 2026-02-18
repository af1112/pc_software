from django.urls import path
from . import views

app_name = 'hr_attendance'

urlpatterns = [
    path('', views.attendance_dashboard, name='dashboard'),
    path('quick/', views.quick_clock, name='quick_clock'),
    path('clock-in/', views.clock_in, name='clock_in'),
    path('clock-out/', views.clock_out, name='clock_out'),
    path('supervisor/', views.supervisor_panel, name='supervisor_panel'),
    path('supervisor/pdf/', views.supervisor_report_pdf, name='supervisor_report_pdf'),
    path('supervisor/clock-in/<int:user_id>/', views.supervisor_clock_in, name='supervisor_clock_in'),
    path('supervisor/clock-out/<int:user_id>/', views.supervisor_clock_out, name='supervisor_clock_out'),
]
