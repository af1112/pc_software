from rest_framework.routers import DefaultRouter

from apps.hrms.api_views import (
    AttendanceLogViewSet,
    EmployeeViewSet,
    ESSViewSet,
    ExecutiveDashboardViewSet,
    LeaveBalanceViewSet,
    LeaveRequestViewSet,
    LeaveTypeViewSet,
    PayrollPeriodViewSet,
    PayrollOvertimeEntryViewSet,
    PayrollResultViewSet,
    SalaryStructureViewSet,
    ShiftTemplateViewSet,
    ShiftVersionViewSet,
    TimesheetViewSet,
    WorkCalendarViewSet,
)

router = DefaultRouter()
router.register('employees', EmployeeViewSet, basename='hrms-employees')
router.register('work-calendars', WorkCalendarViewSet, basename='hrms-work-calendars')
router.register('shift-templates', ShiftTemplateViewSet, basename='hrms-shift-templates')
router.register('shift-versions', ShiftVersionViewSet, basename='hrms-shift-versions')
router.register('attendance-logs', AttendanceLogViewSet, basename='hrms-attendance-logs')
router.register('timesheets', TimesheetViewSet, basename='hrms-timesheets')
router.register('payroll-overtime', PayrollOvertimeEntryViewSet, basename='hrms-payroll-overtime')
router.register('leave-types', LeaveTypeViewSet, basename='hrms-leave-types')
router.register('leave-balances', LeaveBalanceViewSet, basename='hrms-leave-balances')
router.register('leave-requests', LeaveRequestViewSet, basename='hrms-leave-requests')
router.register('payroll-periods', PayrollPeriodViewSet, basename='hrms-payroll-periods')
router.register('salary-structures', SalaryStructureViewSet, basename='hrms-salary-structures')
router.register('payroll-results', PayrollResultViewSet, basename='hrms-payroll-results')
router.register('ess', ESSViewSet, basename='hrms-ess')
router.register('executive-dashboard', ExecutiveDashboardViewSet, basename='hrms-executive-dashboard')

urlpatterns = router.urls
