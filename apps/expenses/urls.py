from django.urls import path
from . import views

app_name = 'expenses'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('statements/', views.statement_list, name='statement_list'),
    path('unreported/', views.unreported_expenses, name='unreported_expenses'),
    path('categories/', views.category_list, name='category_list'),
    path('categories/create/', views.category_create, name='category_create'),
    path('categories/<int:category_id>/update/', views.category_update, name='category_update'),
    path('categories/<int:category_id>/delete/', views.category_delete, name='category_delete'),
    path('create/', views.create_expense, name='create_expense'),
    path('statement/create/', views.create_report, name='create_report'),
    path('trip/create/', views.create_trip, name='create_trip'),
    path('advance/create/', views.create_advance, name='create_advance'),
    path('report/<uuid:report_id>/', views.report_detail, name='report_detail'),
    path('report/<uuid:report_id>/submit/', views.submit_report, name='submit_report'),
    path('report/<uuid:report_id>/approve/', views.approve_report, name='approve_report'),
    path('report/<uuid:report_id>/pdf/', views.export_report_pdf, name='export_report_pdf'),
    path('api/scan-receipt/', views.scan_receipt_api, name='scan_receipt_api'),
]
