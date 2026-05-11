from django.urls import path

from . import views

app_name = 'hr_personnel'

urlpatterns = [
    path('', views.personnel_hub, name='personnel_hub'),
    path('compensation/', views.compensation_hub, name='compensation_hub'),
    path('setup/labor-supply/', views.labor_supply_company_manage, name='labor_supply_company_manage'),
    path('setup/work-units/', views.work_unit_manage, name='work_unit_manage'),
    path('payroll/', views.payroll_hub, name='payroll_hub'),
    path('payroll/periods/', views.payroll_periods, name='payroll_periods'),
    path('payroll/periods/<uuid:period_id>/run/', views.payroll_run_period, name='payroll_run_period'),
    path('payroll/periods/<uuid:period_id>/finalize/', views.payroll_finalize_period, name='payroll_finalize_period'),
    path('payroll/periods/<uuid:period_id>/delete/', views.payroll_delete_period, name='payroll_delete_period'),
    path('payroll/reports/', views.reports_hub, name='reports_hub'),
    path('payroll/reports/summary/', views.payroll_summary_report, name='payroll_summary_report'),
    path('payroll/slips/<uuid:slip_id>/pdf/', views.payroll_payslip_pdf, name='payroll_payslip_pdf'),
    path('payroll/<str:section>/<str:module>/', views.payroll_module_placeholder, name='payroll_module_placeholder'),
    path('employees/', views.employee_list, name='employee_list'),
    path('me/', views.employee_me, name='employee_me'),
    path('create/', views.employee_create, name='employee_create'),
    path('<uuid:employee_id>/', views.employee_detail, name='employee_detail'),
    path('<uuid:employee_id>/edit/', views.employee_edit, name='employee_edit'),
    path('<uuid:employee_id>/delete/', views.employee_delete, name='employee_delete'),

    path('<uuid:employee_id>/salary/create/', views.salary_profile_create, name='salary_profile_create'),
    path('<uuid:employee_id>/salary/<uuid:profile_id>/edit/', views.salary_profile_edit, name='salary_profile_edit'),
    path('<uuid:employee_id>/salary/<uuid:profile_id>/delete/', views.salary_profile_delete, name='salary_profile_delete'),
    path('<uuid:employee_id>/salary/<uuid:profile_id>/component/create/', views.salary_component_create, name='salary_component_create'),

    path('<uuid:employee_id>/bank/create/', views.bank_account_create, name='bank_account_create'),

    path('<uuid:employee_id>/payroll/create/', views.payroll_create, name='payroll_create'),

    # Leave request workflow
    path('leave-requests/', views.leave_request_list, name='leave_request_list'),
    path('leave-requests/new/', views.leave_request_create, name='leave_request_create'),
    path('leave-requests/<int:request_id>/', views.leave_request_detail, name='leave_request_detail'),
    path('leave-requests/<int:request_id>/approve/', views.leave_request_approve, name='leave_request_approve'),
    path('leave-requests/<int:request_id>/reject/', views.leave_request_reject, name='leave_request_reject'),
    path('leave-requests/<int:request_id>/cancel/', views.leave_request_cancel, name='leave_request_cancel'),

    path('api/salary-structure/', views.salary_structure_api_create, name='salary_structure_api_create'),
    path('api/salary-structure/<uuid:employee_id>/', views.salary_structure_api_get, name='salary_structure_api_get'),
    path('api/salary-component/', views.salary_component_api_create, name='salary_component_api_create'),
    path('api/salary-component/<uuid:component_id>/', views.salary_component_api_delete, name='salary_component_api_delete'),
]
