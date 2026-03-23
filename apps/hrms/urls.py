from django.urls import path

from apps.hrms import views

app_name = 'hrms'

urlpatterns = [
    path('', views.hrms_dashboard, name='dashboard'),
    path('shifts/templates/', views.shift_template_list, name='shift_template_list'),
    path('shifts/templates/create/', views.shift_template_create, name='shift_template_create'),
    path('shifts/templates/<uuid:template_id>/edit/', views.shift_template_edit, name='shift_template_edit'),
    path('shifts/templates/<uuid:template_id>/delete/', views.shift_template_delete, name='shift_template_delete'),
    path('shifts/versions/', views.shift_version_list, name='shift_version_list'),
    path('shifts/versions/create/', views.shift_version_create, name='shift_version_create'),
    path('shifts/versions/<uuid:version_id>/edit/', views.shift_version_edit, name='shift_version_edit'),
    path('shifts/versions/<uuid:version_id>/delete/', views.shift_version_delete, name='shift_version_delete'),
    path('shifts/assignments/', views.shift_assignment_list, name='shift_assignment_list'),
    path('shifts/assignments/create/', views.shift_assignment_create, name='shift_assignment_create'),
    path('shifts/assignments/<uuid:assignment_id>/edit/', views.shift_assignment_edit, name='shift_assignment_edit'),
    path('shifts/assignments/<uuid:assignment_id>/delete/', views.shift_assignment_delete, name='shift_assignment_delete'),
    path('shifts/work-unit-assignments/', views.work_unit_shift_assignment_list, name='work_unit_shift_assignment_list'),
    path('shifts/work-unit-assignments/create/', views.work_unit_shift_assignment_create, name='work_unit_shift_assignment_create'),
    path('shifts/work-unit-assignments/<uuid:assignment_id>/edit/', views.work_unit_shift_assignment_edit, name='work_unit_shift_assignment_edit'),
    path('shifts/work-unit-assignments/<uuid:assignment_id>/delete/', views.work_unit_shift_assignment_delete, name='work_unit_shift_assignment_delete'),
    path('work-calendar/', views.work_calendar_list, name='work_calendar_list'),
    path('work-calendar/create/', views.work_calendar_create, name='work_calendar_create'),
    path('work-calendar/<int:row_id>/edit/', views.work_calendar_edit, name='work_calendar_edit'),
    path('work-calendar/<int:row_id>/delete/', views.work_calendar_delete, name='work_calendar_delete'),
    path('work-calendar/delete-year/', views.work_calendar_delete_year, name='work_calendar_delete_year'),
    path('work-calendar/generate/', views.work_calendar_bulk_generate, name='work_calendar_bulk_generate'),
    path('work-closures/', views.work_closure_list, name='work_closure_list'),
    path('work-closures/create/', views.work_closure_create, name='work_closure_create'),
    path('work-closures/<uuid:closure_id>/edit/', views.work_closure_edit, name='work_closure_edit'),
    path('work-closures/<uuid:closure_id>/delete/', views.work_closure_delete, name='work_closure_delete'),
    path('overtime/policies/', views.overtime_policy_list, name='overtime_policy_list'),
    path('overtime/policies/create/', views.overtime_policy_create, name='overtime_policy_create'),
    path('overtime/policies/<uuid:policy_id>/edit/', views.overtime_policy_edit, name='overtime_policy_edit'),
    path('overtime/policies/<uuid:policy_id>/delete/', views.overtime_policy_delete, name='overtime_policy_delete'),
    path('overtime/policies/<uuid:policy_id>/rules/create/', views.overtime_rule_create, name='overtime_rule_create'),
    path('overtime/policies/<uuid:policy_id>/rules/<uuid:rule_id>/edit/', views.overtime_rule_edit, name='overtime_rule_edit'),
    path('overtime/policies/<uuid:policy_id>/rules/<uuid:rule_id>/delete/', views.overtime_rule_delete, name='overtime_rule_delete'),
]
