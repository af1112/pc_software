import datetime
import importlib.util
from unittest import skipUnless
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.hrms.models import (
    AttendanceLog,
    Company,
    Employee,
    EmployeeShiftAssignment,
    LeaveBalance,
    LeaveRequest,
    LeaveType,
    OvertimePolicy,
    OvertimeRateRule,
    PayrollPeriod,
    PayrollResult,
    SalaryStructure,
    ShiftTemplate,
    ShiftVersion,
    Timesheet,
    WorkCalendar,
)
from apps.hrms.services import LeaveManagementService, OvertimePayService, PayrollEngineService, TimesheetEngine
from apps.organizations.models import Organization

if importlib.util.find_spec('rest_framework'):
    from apps.hrms.api_views import ESSViewSet
    from rest_framework import status
    from rest_framework.test import APIRequestFactory, force_authenticate
else:
    ESSViewSet = None


User = get_user_model()


class HRMSOvertimeTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='HRMS Org', slug='hrms-org', timezone='Asia/Tehran')
        self.company, _ = Company.objects.update_or_create(
            organization=self.organization,
            defaults={
                'name': 'HRMS Company',
                'country': Company.Country.OMAN,
                'timezone': 'Asia/Tehran',
                'default_currency': 'OMR',
                'wps_enabled': True,
            },
        )
        self.user = User.objects.create_user(username='hrms-employee', password='pass1234')
        self.employee = Employee.objects.create(
            tenant=self.company,
            user=self.user,
            employee_code='EMP-001',
            first_name='Test',
            last_name='Employee',
            hire_date=datetime.date(2025, 1, 1),
            basic_salary=Decimal('720.000'),
        )

        self.shift = ShiftTemplate.objects.create(tenant=self.company, name='Day Shift')
        ShiftVersion.objects.create(
            tenant=self.company,
            shift=self.shift,
            valid_from=datetime.date(2026, 1, 1),
            valid_to=datetime.date(2026, 12, 31),
            start_time=datetime.time(8, 0),
            end_time=datetime.time(17, 0),
            break_minutes=60,
            required_work_minutes=480,
            grace_in_minutes=10,
            grace_out_minutes=10,
        )
        EmployeeShiftAssignment.objects.create(
            tenant=self.company,
            employee=self.employee,
            shift=self.shift,
            effective_from=datetime.date(2026, 1, 1),
            is_active=True,
        )

        self.policy = OvertimePolicy.objects.create(
            tenant=self.company,
            name='Oman 2026 OT',
            country=Company.Country.OMAN,
            effective_from=datetime.date(2026, 1, 1),
            is_active=True,
        )
        OvertimeRateRule.objects.create(
            policy=self.policy,
            day_type=OvertimeRateRule.DayType.WORKING_DAY,
            overtime_type=OvertimeRateRule.OvertimeType.NORMAL,
            rate_multiplier=Decimal('1.25'),
        )
        OvertimeRateRule.objects.create(
            policy=self.policy,
            day_type=OvertimeRateRule.DayType.WEEKEND,
            overtime_type=OvertimeRateRule.OvertimeType.NORMAL,
            rate_multiplier=Decimal('1.50'),
        )
        OvertimeRateRule.objects.create(
            policy=self.policy,
            day_type=OvertimeRateRule.DayType.PUBLIC_HOLIDAY,
            overtime_type=OvertimeRateRule.OvertimeType.NORMAL,
            rate_multiplier=Decimal('2.00'),
        )

    def test_timesheet_engine_calculates_working_day_overtime(self):
        work_date = datetime.date(2026, 2, 10)
        WorkCalendar.objects.create(
            tenant=self.company,
            date=work_date,
            day_type=WorkCalendar.DayType.WORKING,
            standard_work_minutes=480,
        )

        tz = ZoneInfo(self.company.timezone)
        check_in = timezone.make_aware(datetime.datetime(2026, 2, 10, 8, 5), tz)
        check_out = timezone.make_aware(datetime.datetime(2026, 2, 10, 18, 30), tz)
        AttendanceLog.objects.create(
            tenant=self.company,
            employee=self.employee,
            check_in=check_in,
            check_out=check_out,
            source=AttendanceLog.Source.WEB,
        )

        result = TimesheetEngine.build_for_date(self.company, self.employee, work_date)
        ts = result.timesheet

        self.assertEqual(ts.worked_minutes, 565)
        self.assertEqual(ts.required_minutes, 480)
        self.assertEqual(ts.normal_overtime_minutes, 85)
        self.assertEqual(ts.weekend_overtime_minutes, 0)
        self.assertEqual(ts.holiday_overtime_minutes, 0)

    def test_monthly_overtime_entry_aggregates_and_prices(self):
        work_date = datetime.date(2026, 2, 11)
        WorkCalendar.objects.create(
            tenant=self.company,
            date=work_date,
            day_type=WorkCalendar.DayType.WORKING,
            standard_work_minutes=480,
        )

        tz = ZoneInfo(self.company.timezone)
        check_in = timezone.make_aware(datetime.datetime(2026, 2, 11, 8, 0), tz)
        check_out = timezone.make_aware(datetime.datetime(2026, 2, 11, 18, 30), tz)
        AttendanceLog.objects.create(
            tenant=self.company,
            employee=self.employee,
            check_in=check_in,
            check_out=check_out,
            source=AttendanceLog.Source.WEB,
        )

        timesheet = TimesheetEngine.build_for_date(self.company, self.employee, work_date).timesheet
        daily_amount = OvertimePayService.apply_daily_overtime_pay(timesheet)
        entry = OvertimePayService.generate_monthly_entry(self.company, self.employee, 2026, 2)

        self.assertEqual(timesheet.normal_overtime_minutes, 90)
        self.assertEqual(daily_amount, Decimal('5.625'))
        self.assertEqual(entry.total_overtime_minutes, 90)
        self.assertEqual(entry.total_overtime_pay, Decimal('5.625'))


class HRMSLeaveAndPayrollTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='Payroll Org', slug='payroll-org', timezone='Asia/Muscat')
        self.company, _ = Company.objects.update_or_create(
            organization=self.organization,
            defaults={
                'name': 'Payroll Co',
                'country': Company.Country.OMAN,
                'timezone': 'Asia/Muscat',
                'default_currency': 'OMR',
                'wps_enabled': True,
            },
        )
        self.manager = User.objects.create_user(username='manager', password='pass1234')
        self.user = User.objects.create_user(username='employee-user', password='pass1234')

        self.employee = Employee.objects.create(
            tenant=self.company,
            user=self.user,
            employee_code='EMP-PAY-001',
            first_name='Pay',
            last_name='Employee',
            hire_date=datetime.date(2026, 1, 1),
            basic_salary=Decimal('900.000'),
        )

        self.annual_leave = LeaveType.objects.create(
            tenant=self.company,
            name='Annual Leave',
            code='AL',
            leave_category=LeaveType.LeaveCategory.ANNUAL,
            accrual_method=LeaveType.AccrualMethod.MONTHLY,
            accrual_rate_per_month=Decimal('2.00'),
            max_balance=Decimal('30.00'),
            carry_forward_allowed=True,
            max_carry_forward=Decimal('10.00'),
            requires_approval=True,
            is_active=True,
        )
        self.unpaid_leave = LeaveType.objects.create(
            tenant=self.company,
            name='Unpaid Leave',
            code='UL',
            leave_category=LeaveType.LeaveCategory.UNPAID,
            accrual_method=LeaveType.AccrualMethod.NONE,
            is_active=True,
        )
        LeaveBalance.objects.create(
            tenant=self.company,
            employee=self.employee,
            leave_type=self.annual_leave,
            balance_days=Decimal('10.00'),
        )

        self.period = PayrollPeriod.objects.create(
            tenant=self.company,
            name='2026-03',
            start_date=datetime.date(2026, 3, 1),
            end_date=datetime.date(2026, 3, 31),
            pay_date=datetime.date(2026, 4, 1),
        )
        SalaryStructure.objects.create(
            tenant=self.company,
            employee=self.employee,
            basic_salary=Decimal('1000.000'),
            housing_allowance=Decimal('200.000'),
            transport_allowance=Decimal('50.000'),
            other_allowances=Decimal('25.000'),
            effective_from=datetime.date(2026, 1, 1),
        )

    def test_leave_approval_deducts_and_cancel_restores_balance(self):
        leave_request = LeaveManagementService.submit_request(
            tenant=self.company,
            employee=self.employee,
            leave_type=self.annual_leave,
            start_date=datetime.date(2026, 3, 8),
            end_date=datetime.date(2026, 3, 10),
            reason='Family trip',
        )
        self.assertEqual(leave_request.status, LeaveRequest.Status.PENDING)

        LeaveManagementService.approve_request(leave_request, approver=self.manager)
        leave_request.refresh_from_db()
        self.assertEqual(leave_request.status, LeaveRequest.Status.APPROVED)

        balance = LeaveBalance.objects.get(tenant=self.company, employee=self.employee, leave_type=self.annual_leave)
        self.assertEqual(balance.balance_days, Decimal('7.00'))

        LeaveManagementService.cancel_request(leave_request)
        balance.refresh_from_db()
        self.assertEqual(balance.balance_days, Decimal('10.00'))

    def test_payroll_engine_calculates_and_is_idempotent(self):
        LeaveRequest.objects.create(
            tenant=self.company,
            employee=self.employee,
            leave_type=self.unpaid_leave,
            start_date=datetime.date(2026, 3, 15),
            end_date=datetime.date(2026, 3, 15),
            total_days=Decimal('1.00'),
            status=LeaveRequest.Status.APPROVED,
            approved_by=self.manager,
            approved_at=timezone.now(),
        )

        Timesheet.objects.create(
            tenant=self.company,
            employee=self.employee,
            work_date=datetime.date(2026, 3, 15),
            worked_minutes=600,
            required_minutes=480,
            normal_overtime_minutes=120,
            overtime_pay_amount=Decimal('12.000'),
        )

        first_count = PayrollEngineService.generate_payroll_for_period(self.company, self.period)
        second_count = PayrollEngineService.generate_payroll_for_period(self.company, self.period)
        self.assertEqual(first_count, 1)
        self.assertEqual(second_count, 1)

        result = PayrollResult.objects.get(tenant=self.company, employee=self.employee, period=self.period)
        self.assertEqual(result.total_allowances, Decimal('275.000'))
        self.assertEqual(result.overtime_pay, Decimal('9.375'))
        self.assertEqual(result.leave_deduction, Decimal('33.333'))
        self.assertEqual(result.gross_salary, Decimal('1284.375'))
        self.assertEqual(result.net_salary, Decimal('1251.042'))
        self.assertTrue(result.wps_ready)


@skipUnless(importlib.util.find_spec('rest_framework'), 'DRF not installed in runtime environment')
class HrmSESSPermissionTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.organization = Organization.objects.create(name='ESS Org', slug='ess-org', timezone='Asia/Tehran')
        self.company, _ = Company.objects.update_or_create(
            organization=self.organization,
            defaults={
                'name': 'ESS Co',
                'country': Company.Country.IRAN,
                'timezone': 'Asia/Tehran',
                'default_currency': 'IRR',
                'wps_enabled': False,
            },
        )
        self.user_1 = User.objects.create_user(username='ess-user-1', password='pass1234')
        self.user_2 = User.objects.create_user(username='ess-user-2', password='pass1234')
        self.employee_1 = Employee.objects.create(
            tenant=self.company,
            user=self.user_1,
            employee_code='ESS-001',
            first_name='ESS',
            last_name='One',
            hire_date=datetime.date(2026, 1, 1),
        )
        Employee.objects.create(
            tenant=self.company,
            user=self.user_2,
            employee_code='ESS-002',
            first_name='ESS',
            last_name='Two',
            hire_date=datetime.date(2026, 1, 1),
        )

    def test_ess_profile_returns_authenticated_employee_only(self):
        view = ESSViewSet.as_view({'get': 'profile'})
        request = self.factory.get('/api/hrms/ess/profile/')
        request.organization = self.organization
        force_authenticate(request, user=self.user_1)
        response = view(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(str(response.data['id']), str(self.employee_1.id))
