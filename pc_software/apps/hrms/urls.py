from django.urls import path

from apps.hrms import views

app_name = 'hrms'

urlpatterns = [
    path('', views.hrms_dashboard, name='dashboard'),
    path('shifts/templates/', views.shift_template_list, name='shift_template_list'),
    path('shifts/templates/create/', views.shift_template_create, name='shift_template_create'),
    path('shifts/versions/', views.shift_version_list, name='shift_version_list'),
    path('shifts/versions/create/', views.shift_version_create, name='shift_version_create'),
    path('shifts/assignments/', views.shift_assignment_list, name='shift_assignment_list'),
    path('shifts/assignments/create/', views.shift_assignment_create, name='shift_assignment_create'),
    path('work-calendar/', views.work_calendar_list, name='work_calendar_list'),
    path('work-calendar/create/', views.work_calendar_create, name='work_calendar_create'),
    path('work-calendar/generate/', views.work_calendar_bulk_generate, name='work_calendar_bulk_generate'),
    path('overtime/policies/', views.overtime_policy_list, name='overtime_policy_list'),
    path('overtime/policies/create/', views.overtime_policy_create, name='overtime_policy_create'),
    path('overtime/policies/<uuid:policy_id>/rules/create/', views.overtime_rule_create, name='overtime_rule_create'),
]
