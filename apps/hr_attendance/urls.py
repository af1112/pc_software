from django.urls import path
from . import views

app_name = 'hr_attendance'

urlpatterns = [
    path('', views.attendance_hub, name='hub'),
    path('overview/', views.attendance_dashboard, name='dashboard'),
    path('card/', views.attendance_card, name='attendance_card'),
    path('card/pdf/', views.attendance_card_pdf, name='attendance_card_pdf'),
    path('clock-center/', views.attendance_clock_center, name='clock_center'),
    path('quick/', views.quick_clock, name='quick_clock'),
    path('quick/success/', views.quick_clock_success, name='quick_clock_success'),
    path('quick/my-card/', views.my_attendance_card, name='my_attendance_card'),
    path('quick/my-card/pdf/', views.my_attendance_card_pdf, name='my_attendance_card_pdf'),
    path('quick/my-card/excel/', views.my_attendance_card_excel, name='my_attendance_card_excel'),
    path('clock-in/', views.clock_in, name='clock_in'),
    path('clock-out/', views.clock_out, name='clock_out'),
    path('supervisor/', views.supervisor_panel, name='supervisor_panel'),
    path('supervisor/bulk-set/', views.supervisor_bulk_set_times, name='supervisor_bulk_set_times'),
    path('supervisor/bulk-range/', views.supervisor_bulk_range_entry, name='supervisor_bulk_range_entry'),
    path('supervisor/pdf/', views.supervisor_report_pdf, name='supervisor_report_pdf'),
    path('supervisor/action/<int:user_id>/', views.supervisor_attendance_action, name='supervisor_attendance_action'),
    path('supervisor/action/employee/<uuid:employee_id>/', views.supervisor_attendance_action_employee, name='supervisor_attendance_action_employee'),
    path('supervisor/clock-in/<int:user_id>/', views.supervisor_clock_in, name='supervisor_clock_in'),
    path('supervisor/clock-out/<int:user_id>/', views.supervisor_clock_out, name='supervisor_clock_out'),
]
