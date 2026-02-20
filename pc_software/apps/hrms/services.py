from __future__ import annotations

import calendar
import datetime
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

from django.db import models, transaction
from django.db.models import Sum
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
    PayrollOvertimeEntry,
    PayrollResult,
    SalaryStructure,
    ShiftVersion,
    Timesheet,
    WorkCalendar,
    resolve_shift_window,
)


@dataclass
class TimesheetResult:
    timesheet: Timesheet
    created: bool


class TimesheetEngine:
    @classmethod
    @transaction.atomic
    def build_for_date(cls, tenant: Company, employee: Employee, work_date: datetime.date) -> TimesheetResult:
        calendar_day = WorkCalendar.objects.filter(tenant=tenant, date=work_date).first()

        assignment = (
            EmployeeShiftAssignment.objects.filter(
                tenant=tenant,
                employee=employee,
                is_active=True,
                effective_from__lte=work_date,
            )
            .filter(models.Q(effective_to__isnull=True) | models.Q(effective_to__gte=work_date))
            .select_related('shift')
            .order_by('-effective_from')
            .first()
        )

        shift_version = None
        scheduled_start = None
        scheduled_end = None
        required_minutes = calendar_day.standard_work_minutes if calendar_day else 480

        if assignment is not None:
            shift_version = (
                ShiftVersion.objects.filter(
                    tenant=tenant,
                    shift=assignment.shift,
                    valid_from__lte=work_date,
                    valid_to__gte=work_date,
                )
                .order_by('-valid_from')
                .first()
            )

        if shift_version is not None:
            tz = ZoneInfo(tenant.timezone or 'UTC')
            scheduled_start, scheduled_end = resolve_shift_window(shift_version, work_date, tz)
            required_minutes = shift_version.required_work_minutes

        day_logs = AttendanceLog.objects.filter(tenant=tenant, employee=employee, check_in__date=work_date)
        first_log = day_logs.order_by('check_in').first()
        last_log = day_logs.order_by('-check_in').first()

        actual_in = first_log.check_in if first_log else None
        actual_out = None
        if last_log:
            actual_out = last_log.check_out or last_log.check_in

        worked_minutes = 0
        late_minutes = 0
        early_leave_minutes = 0

        if actual_in and actual_out and actual_out > actual_in:
            gross_minutes = int((actual_out - actual_in).total_seconds() // 60)
            break_minutes = shift_version.break_minutes if shift_version else 0
            worked_minutes = max(gross_minutes - break_minutes, 0)

        if scheduled_start and actual_in:
            grace_in = datetime.timedelta(minutes=shift_version.grace_in_minutes if shift_version else 0)
            late_minutes = max(int((actual_in - (scheduled_start + grace_in)).total_seconds() // 60), 0)

        if scheduled_end and actual_out:
            grace_out = datetime.timedelta(minutes=shift_version.grace_out_minutes if shift_version else 0)
            early_leave_minutes = max(int(((scheduled_end - grace_out) - actual_out).total_seconds() // 60), 0)

        is_weekend = calendar_day and calendar_day.day_type == WorkCalendar.DayType.WEEKEND
        is_holiday = calendar_day and calendar_day.day_type == WorkCalendar.DayType.PUBLIC_HOLIDAY

        normal_ot = 0
        weekend_ot = 0
        holiday_ot = 0

        if worked_minutes > 0:
            if is_holiday:
                holiday_ot = worked_minutes
            elif is_weekend:
                weekend_ot = worked_minutes
            else:
                normal_ot = max(worked_minutes - required_minutes, 0)

        timesheet, created = Timesheet.objects.update_or_create(
            tenant=tenant,
            employee=employee,
            work_date=work_date,
            defaults={
                'scheduled_start': scheduled_start,
                'scheduled_end': scheduled_end,
                'actual_in': actual_in,
                'actual_out': actual_out,
                'worked_minutes': worked_minutes,
                'required_minutes': required_minutes,
                'normal_overtime_minutes': normal_ot,
                'weekend_overtime_minutes': weekend_ot,
                'holiday_overtime_minutes': holiday_ot,
                'late_minutes': late_minutes,
                'early_leave_minutes': early_leave_minutes,
                'is_absent': actual_in is None,
                'anomaly_flag': actual_in is not None and actual_out is None,
                'ai_features': {
                    'logs_count': day_logs.count(),
                    'source_mix': list(day_logs.values_list('source', flat=True)),
                },
            },
        )
        return TimesheetResult(timesheet=timesheet, created=created)


class OvertimePayService:
    DEFAULT_MONTHLY_WORK_HOURS = Decimal('240')

    @classmethod
    def _effective_policy(cls, tenant: Company, on_date: datetime.date) -> OvertimePolicy | None:
        return (
            OvertimePolicy.objects.filter(
                tenant=tenant,
                country=tenant.country,
                is_active=True,
                effective_from__lte=on_date,
            )
            .filter(models.Q(effective_to__isnull=True) | models.Q(effective_to__gte=on_date))
            .order_by('-effective_from')
            .first()
        )

    @classmethod
    def _rate_for(cls, policy: OvertimePolicy | None, day_type: str) -> Decimal:
        if policy is None:
            if day_type == OvertimeRateRule.DayType.WEEKEND:
                return Decimal('1.50')
            if day_type == OvertimeRateRule.DayType.PUBLIC_HOLIDAY:
                return Decimal('2.00')
            return Decimal('1.25')

        rule = (
            OvertimeRateRule.objects.filter(policy=policy, day_type=day_type, overtime_type=OvertimeRateRule.OvertimeType.NORMAL)
            .order_by('-min_minutes_threshold')
            .first()
        )
        if rule is None:
            return Decimal('1.25')
        return rule.rate_multiplier

    @classmethod
    def _minute_rate(cls, employee: Employee) -> Decimal:
        monthly_salary = employee.basic_salary or Decimal('0')
        if monthly_salary <= 0:
            return Decimal('0')
        return (monthly_salary / cls.DEFAULT_MONTHLY_WORK_HOURS / Decimal('60')).quantize(Decimal('0.000001'))

    @classmethod
    @transaction.atomic
    def apply_daily_overtime_pay(cls, timesheet: Timesheet) -> Decimal:
        policy = cls._effective_policy(timesheet.tenant, timesheet.work_date)
        minute_rate = cls._minute_rate(timesheet.employee)

        normal_rate = cls._rate_for(policy, OvertimeRateRule.DayType.WORKING_DAY)
        weekend_rate = cls._rate_for(policy, OvertimeRateRule.DayType.WEEKEND)
        holiday_rate = cls._rate_for(policy, OvertimeRateRule.DayType.PUBLIC_HOLIDAY)

        amount = (
            Decimal(timesheet.normal_overtime_minutes) * minute_rate * normal_rate
            + Decimal(timesheet.weekend_overtime_minutes) * minute_rate * weekend_rate
            + Decimal(timesheet.holiday_overtime_minutes) * minute_rate * holiday_rate
        ).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)

        timesheet.overtime_pay_amount = amount
        timesheet.save(update_fields=['overtime_pay_amount'])
        return amount

    @classmethod
    @transaction.atomic
    def generate_monthly_entry(cls, tenant: Company, employee: Employee, year: int, month: int) -> PayrollOvertimeEntry:
        start_date = datetime.date(year, month, 1)
        end_date = datetime.date(year, month, calendar.monthrange(year, month)[1])

        monthly_timesheets = Timesheet.objects.filter(
            tenant=tenant,
            employee=employee,
            work_date__gte=start_date,
            work_date__lte=end_date,
        )

        normal_minutes = int(monthly_timesheets.aggregate(v=Sum('normal_overtime_minutes'))['v'] or 0)
        weekend_minutes = int(monthly_timesheets.aggregate(v=Sum('weekend_overtime_minutes'))['v'] or 0)
        holiday_minutes = int(monthly_timesheets.aggregate(v=Sum('holiday_overtime_minutes'))['v'] or 0)
        total_minutes = normal_minutes + weekend_minutes + holiday_minutes

        total_pay = Decimal('0.000')
        for ts in monthly_timesheets:
            total_pay += cls.apply_daily_overtime_pay(ts)

        entry, _ = PayrollOvertimeEntry.objects.update_or_create(
            tenant=tenant,
            employee=employee,
            period_year=year,
            period_month=month,
            defaults={
                'total_overtime_minutes': int(total_minutes),
                'total_overtime_pay': total_pay.quantize(Decimal('0.001'), rounding=ROUND_HALF_UP),
                'breakdown': {
                    'normal_minutes': normal_minutes,
                    'weekend_minutes': weekend_minutes,
                    'holiday_minutes': holiday_minutes,
                },
                'generated_at': timezone.now(),
            },
        )
        return entry


class LeaveManagementService:
    DEFAULT_WEEKEND_DAYS = {4, 5}  # Friday, Saturday

    @classmethod
    def _iter_days(cls, start_date: datetime.date, end_date: datetime.date):
        current = start_date
        while current <= end_date:
            yield current
            current += datetime.timedelta(days=1)

    @classmethod
    def _country_rule_hook(cls, tenant: Company, leave_type: LeaveType, requested_days: Decimal) -> Decimal:
        if tenant.country == Company.Country.OMAN and leave_type.leave_category == LeaveType.LeaveCategory.HAJ:
            return min(requested_days, Decimal('15.00'))
        # Iran and other countries can be customized in future policy engines.
        return requested_days

    @classmethod
    def calculate_leave_days(
        cls,
        tenant: Company,
        start_date: datetime.date,
        end_date: datetime.date,
        exclude_weekends: bool = True,
        exclude_holidays: bool = True,
    ) -> Decimal:
        if end_date < start_date:
            raise ValueError('end_date cannot be earlier than start_date')

        total = Decimal('0.00')
        calendar_days = {
            item.date: item
            for item in WorkCalendar.objects.filter(tenant=tenant, date__gte=start_date, date__lte=end_date)
        }
        for day in cls._iter_days(start_date, end_date):
            item = calendar_days.get(day)
            if exclude_holidays and item and item.day_type == WorkCalendar.DayType.PUBLIC_HOLIDAY:
                continue
            if exclude_weekends:
                if item and item.day_type == WorkCalendar.DayType.WEEKEND:
                    continue
                if not item and day.weekday() in cls.DEFAULT_WEEKEND_DAYS:
                    continue
            total += Decimal('1.00')
        return total

    @classmethod
    def validate_no_overlap(cls, tenant: Company, employee: Employee, start_date: datetime.date, end_date: datetime.date, exclude_request_id=None):
        overlap_qs = LeaveRequest.objects.filter(
            tenant=tenant,
            employee=employee,
            status__in=[LeaveRequest.Status.PENDING, LeaveRequest.Status.APPROVED],
            start_date__lte=end_date,
            end_date__gte=start_date,
        )
        if exclude_request_id:
            overlap_qs = overlap_qs.exclude(id=exclude_request_id)
        if overlap_qs.exists():
            raise ValueError('Leave request overlaps with existing pending/approved request.')

    @classmethod
    def validate_balance(cls, tenant: Company, employee: Employee, leave_type: LeaveType, requested_days: Decimal):
        if leave_type.leave_category == LeaveType.LeaveCategory.UNPAID:
            return
        balance = LeaveBalance.objects.filter(tenant=tenant, employee=employee, leave_type=leave_type).first()
        available = balance.balance_days if balance else Decimal('0.00')
        if available < requested_days:
            raise ValueError('Insufficient leave balance.')

    @classmethod
    @transaction.atomic
    def submit_request(
        cls,
        tenant: Company,
        employee: Employee,
        leave_type: LeaveType,
        start_date: datetime.date,
        end_date: datetime.date,
        reason: str = '',
        attachment=None,
    ) -> LeaveRequest:
        cls.validate_no_overlap(tenant, employee, start_date, end_date)
        total_days = cls.calculate_leave_days(tenant, start_date, end_date)
        total_days = cls._country_rule_hook(tenant, leave_type, total_days)
        if total_days <= 0:
            raise ValueError('Leave request has zero payable/requestable days.')

        if leave_type.requires_attachment and not attachment:
            raise ValueError('Attachment is required for this leave type.')

        if not leave_type.requires_approval:
            cls.validate_balance(tenant, employee, leave_type, total_days)

        request = LeaveRequest.objects.create(
            tenant=tenant,
            employee=employee,
            leave_type=leave_type,
            start_date=start_date,
            end_date=end_date,
            total_days=total_days,
            reason=reason,
            attachment=attachment,
            status=LeaveRequest.Status.PENDING if leave_type.requires_approval else LeaveRequest.Status.APPROVED,
            approved_at=None if leave_type.requires_approval else timezone.now(),
        )
        if request.status == LeaveRequest.Status.APPROVED:
            cls._deduct_balance(request)
        return request

    @classmethod
    @transaction.atomic
    def approve_request(cls, leave_request: LeaveRequest, approver=None) -> LeaveRequest:
        if leave_request.status != LeaveRequest.Status.PENDING:
            raise ValueError('Only pending requests can be approved.')
        cls.validate_balance(leave_request.tenant, leave_request.employee, leave_request.leave_type, leave_request.total_days)
        leave_request.status = LeaveRequest.Status.APPROVED
        leave_request.approved_by = approver
        leave_request.approved_at = timezone.now()
        leave_request.save(update_fields=['status', 'approved_by', 'approved_at'])
        cls._deduct_balance(leave_request)
        return leave_request

    @classmethod
    @transaction.atomic
    def cancel_request(cls, leave_request: LeaveRequest) -> LeaveRequest:
        if leave_request.status == LeaveRequest.Status.CANCELLED:
            return leave_request
        previously_approved = leave_request.status == LeaveRequest.Status.APPROVED
        leave_request.status = LeaveRequest.Status.CANCELLED
        leave_request.save(update_fields=['status'])
        if previously_approved:
            cls._restore_balance(leave_request)
        return leave_request

    @classmethod
    def _deduct_balance(cls, leave_request: LeaveRequest):
        if leave_request.leave_type.leave_category == LeaveType.LeaveCategory.UNPAID:
            return
        balance, _ = LeaveBalance.objects.get_or_create(
            tenant=leave_request.tenant,
            employee=leave_request.employee,
            leave_type=leave_request.leave_type,
            defaults={'balance_days': Decimal('0.00')},
        )
        if balance.balance_days < leave_request.total_days:
            raise ValueError('Insufficient leave balance during deduction.')
        balance.balance_days = (balance.balance_days - leave_request.total_days).quantize(Decimal('0.01'))
        balance.save(update_fields=['balance_days'])

    @classmethod
    def _restore_balance(cls, leave_request: LeaveRequest):
        if leave_request.leave_type.leave_category == LeaveType.LeaveCategory.UNPAID:
            return
        balance, _ = LeaveBalance.objects.get_or_create(
            tenant=leave_request.tenant,
            employee=leave_request.employee,
            leave_type=leave_request.leave_type,
            defaults={'balance_days': Decimal('0.00')},
        )
        balance.balance_days = (balance.balance_days + leave_request.total_days).quantize(Decimal('0.01'))
        balance.save(update_fields=['balance_days'])


class PayrollEngineService:
    DEFAULT_MONTHLY_WORK_DAYS = Decimal('30.0')

    @classmethod
    def _effective_salary_structure(cls, tenant: Company, employee: Employee, on_date: datetime.date) -> SalaryStructure | None:
        return (
            SalaryStructure.objects.filter(
                tenant=tenant,
                employee=employee,
                effective_from__lte=on_date,
            )
            .filter(models.Q(effective_to__isnull=True) | models.Q(effective_to__gte=on_date))
            .order_by('-effective_from')
            .first()
        )

    @classmethod
    def _country_payroll_hook(cls, tenant: Company, gross: Decimal, net: Decimal) -> tuple[Decimal, Decimal]:
        if tenant.country == Company.Country.IRAN:
            # Placeholder for future tax engine integration.
            return gross, net
        return gross, net

    @classmethod
    def _leave_deduction(cls, tenant: Company, employee: Employee, period: PayrollPeriod, base_salary: Decimal) -> Decimal:
        unpaid_days = (
            LeaveRequest.objects.filter(
                tenant=tenant,
                employee=employee,
                status=LeaveRequest.Status.APPROVED,
                leave_type__leave_category=LeaveType.LeaveCategory.UNPAID,
                start_date__lte=period.end_date,
                end_date__gte=period.start_date,
            ).aggregate(total=Sum('total_days'))['total']
            or Decimal('0.00')
        )
        daily_rate = (base_salary / cls.DEFAULT_MONTHLY_WORK_DAYS) if cls.DEFAULT_MONTHLY_WORK_DAYS > 0 else Decimal('0.00')
        return (daily_rate * unpaid_days).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)

    @classmethod
    @transaction.atomic
    def generate_payroll_for_period(cls, tenant: Company, period: PayrollPeriod) -> int:
        period.status = PayrollPeriod.Status.PROCESSING
        period.save(update_fields=['status'])

        processed = 0
        employees = Employee.objects.filter(tenant=tenant, is_active=True)
        for employee in employees:
            processed += 1
            salary = cls._effective_salary_structure(tenant, employee, period.end_date)
            base_salary = salary.basic_salary if salary else (employee.basic_salary or Decimal('0.000'))
            housing = salary.housing_allowance if salary else Decimal('0.000')
            transport = salary.transport_allowance if salary else Decimal('0.000')
            other_allowances = salary.other_allowances if salary else Decimal('0.000')
            total_allowances = (housing + transport + other_allowances).quantize(Decimal('0.001'))

            overtime_entry = OvertimePayService.generate_monthly_entry(
                tenant,
                employee,
                period.start_date.year,
                period.start_date.month,
            )
            overtime_pay = overtime_entry.total_overtime_pay
            leave_deduction = cls._leave_deduction(tenant, employee, period, base_salary)
            other_deductions = Decimal('0.000')

            gross_salary = (base_salary + total_allowances + overtime_pay).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)
            net_salary = (gross_salary - leave_deduction - other_deductions).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)
            gross_salary, net_salary = cls._country_payroll_hook(tenant, gross_salary, net_salary)

            PayrollResult.objects.update_or_create(
                tenant=tenant,
                employee=employee,
                period=period,
                defaults={
                    'basic_salary': base_salary,
                    'total_allowances': total_allowances,
                    'overtime_pay': overtime_pay,
                    'leave_deduction': leave_deduction,
                    'other_deductions': other_deductions,
                    'gross_salary': gross_salary,
                    'net_salary': max(net_salary, Decimal('0.000')),
                    'currency': tenant.default_currency,
                    'wps_ready': bool(tenant.wps_enabled and tenant.country == Company.Country.OMAN),
                },
            )

        period.status = PayrollPeriod.Status.CLOSED
        period.save(update_fields=['status'])
        return processed
