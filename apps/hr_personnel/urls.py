from django.urls import path

from . import views

app_name = 'hr_personnel'

urlpatterns = [
    path('', views.employee_list, name='employee_list'),
    path('create/', views.employee_create, name='employee_create'),
    path('<uuid:employee_id>/', views.employee_detail, name='employee_detail'),
    path('<uuid:employee_id>/edit/', views.employee_edit, name='employee_edit'),
    path('<uuid:employee_id>/delete/', views.employee_delete, name='employee_delete'),

    path('<uuid:employee_id>/salary/create/', views.salary_profile_create, name='salary_profile_create'),
    path('<uuid:employee_id>/salary/<uuid:profile_id>/component/create/', views.salary_component_create, name='salary_component_create'),

    path('<uuid:employee_id>/bank/create/', views.bank_account_create, name='bank_account_create'),

    path('<uuid:employee_id>/payroll/create/', views.payroll_create, name='payroll_create'),
]
