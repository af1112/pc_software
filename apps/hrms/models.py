import datetime
import uuid
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Company(models.Model):
    class Country(models.TextChoices):
        OMAN = 'OM', 'Oman'
        IRAN = 'IR', 'Iran'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.OneToOneField(
        'organizations.Organization',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='hrms_company',
    )
    name = models.CharField(max_length=255)
    country = models.CharField(max_length=2, choices=Country.choices)
    timezone = models.CharField(max_length=64, default='UTC')
    default_currency = models.CharField(max_length=8, default='OMR')
    wps_enabled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['country']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return self.name


class Employee(models.Model):
    class EmploymentType(models.TextChoices):
        FULL_TIME = 'full_time', 'Full Time'
        PART_TIME = 'part_time', 'Part Time'
        CONTRACT = 'contract', 'Contract'
        INTERN = 'intern', 'Intern'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='employees')
    personnel_employee = models.OneToOneField(
        'hr_personnel.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='hrms_employee_profile',
    )
    user = models.OneToOneField(User, on_delete=models.SET_NULL, related_name='hrms_employee', null=True, blank=True)
    employee_code = models.CharField(max_length=64)
    first_name = models.CharField(max_length=128)
    last_name = models.CharField(max_length=128)
    nationality = models.CharField(max_length=64, blank=True, null=True)
    hire_date = models.DateField()
    employment_type = models.CharField(max_length=20, choices=EmploymentType.choices, default=EmploymentType.FULL_TIME)
    basic_salary = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0.000'))
    ai_risk_score = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    ai_attrition_risk_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'employee_code'], name='uq_hrms_employee_tenant_code'),
        ]
        indexes = [
            models.Index(fields=['tenant', 'employee_code']),
            models.Index(fields=['tenant', 'is_active']),
        ]

    def __str__(self):
        return f'{self.employee_code} - {self.first_name} {self.last_name}'


class WorkCalendar(models.Model):
    class DayType(models.TextChoices):
        WORKING = 'working', 'Working Day'
        WEEKEND = 'weekend', 'Weekend'
        PUBLIC_HOLIDAY = 'public_holiday', 'Public Holiday'
        SPECIAL = 'special', 'Special'

    tenant = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='work_calendar_days')
    date = models.DateField(db_index=True)
    day_type = models.CharField(max_length=20, choices=DayType.choices, default=DayType.WORKING)
    holiday_name = models.CharField(max_length=255, blank=True, null=True)
    is_ramadan = models.BooleanField(default=False)
    is_summer_schedule = models.BooleanField(default=False)
    standard_work_minutes = models.PositiveIntegerField(default=480)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'date'], name='uq_hrms_workcalendar_tenant_date'),
        ]
        indexes = [
            models.Index(fields=['tenant', 'date']),
            models.Index(fields=['tenant', 'day_type']),
        ]

    def __str__(self):
        return f'{self.tenant.name} - {self.date}'


class ShiftTemplate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='shift_templates')
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'name'], name='uq_hrms_shifttemplate_tenant_name'),
        ]

    def __str__(self):
        return self.name


class ShiftVersion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='shift_versions')
    shift = models.ForeignKey(ShiftTemplate, on_delete=models.CASCADE, related_name='versions')
    valid_from = models.DateField(db_index=True)
    valid_to = models.DateField(db_index=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    break_minutes = models.PositiveIntegerField(default=0)
    required_work_minutes = models.PositiveIntegerField(default=480)
    grace_in_minutes = models.PositiveIntegerField(default=0)
    grace_out_minutes = models.PositiveIntegerField(default=0)
    is_ramadan_shift = models.BooleanField(default=False)
    is_summer_shift = models.BooleanField(default=False)
    overtime_after_minutes = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(valid_to__gte=models.F('valid_from')), name='ck_hrms_shiftversion_valid_range'),
        ]
        indexes = [
            models.Index(fields=['tenant', 'shift', 'valid_from']),
            models.Index(fields=['tenant', 'shift', 'valid_to']),
        ]

    def clean(self):
        if self.valid_to < self.valid_from:
            raise ValidationError('valid_to cannot be earlier than valid_from.')

        overlap_qs = ShiftVersion.objects.filter(
            tenant=self.tenant,
            shift=self.shift,
            valid_from__lte=self.valid_to,
            valid_to__gte=self.valid_from,
        )
        if self.pk:
            overlap_qs = overlap_qs.exclude(pk=self.pk)
        if overlap_qs.exists():
            raise ValidationError('Shift version date range overlaps with an existing version for this shift.')

    def __str__(self):
        return f'{self.shift.name} [{self.valid_from} - {self.valid_to}]'


class EmployeeShiftAssignment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='employee_shift_assignments')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='shift_assignments')
    shift = models.ForeignKey(ShiftTemplate, on_delete=models.CASCADE, related_name='employee_assignments')
    effective_from = models.DateField()
    effective_to = models.DateField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True) | models.Q(effective_to__gte=models.F('effective_from')),
                name='ck_hrms_shift_assignment_effective_range',
            ),
        ]
        indexes = [
            models.Index(fields=['tenant', 'employee', 'effective_from']),
        ]

    def __str__(self):
        return f'{self.employee} -> {self.shift}'


class WorkUnitShiftAssignment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='work_unit_shift_assignments')
    work_unit = models.ForeignKey('hr_personnel.WorkUnit', on_delete=models.CASCADE, related_name='hrms_shift_assignments')
    shift = models.ForeignKey(ShiftTemplate, on_delete=models.CASCADE, related_name='work_unit_assignments')
    effective_from = models.DateField()
    effective_to = models.DateField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True) | models.Q(effective_to__gte=models.F('effective_from')),
                name='ck_hrms_work_unit_shift_assignment_effective_range',
            ),
        ]
        indexes = [
            models.Index(fields=['tenant', 'work_unit', 'effective_from']),
        ]

    def __str__(self):
        return f'{self.work_unit} -> {self.shift}'


class WorkClosure(models.Model):
    class Scope(models.TextChoices):
        COMPANY = 'company', 'Company-wide'
        WORK_UNIT = 'work_unit', 'Work Unit'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='work_closures')
    title = models.CharField(max_length=160)
    scope = models.CharField(max_length=20, choices=Scope.choices, default=Scope.COMPANY)
    work_unit = models.ForeignKey('hr_personnel.WorkUnit', on_delete=models.CASCADE, null=True, blank=True, related_name='work_closures')
    start_date = models.DateField()
    end_date = models.DateField()
    is_paid = models.BooleanField(default=True)
    reason = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_work_closures')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(end_date__gte=models.F('start_date')), name='ck_hrms_work_closure_date_range'),
        ]
        indexes = [
            models.Index(fields=['tenant', 'scope', 'start_date']),
            models.Index(fields=['tenant', 'start_date', 'end_date']),
        ]

    def clean(self):
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValidationError('end_date cannot be earlier than start_date.')
        if self.scope == self.Scope.WORK_UNIT and self.work_unit_id is None:
            raise ValidationError('work_unit is required when scope is work_unit.')
        if self.scope == self.Scope.COMPANY:
            self.work_unit = None

    def __str__(self):
        return f'{self.title} ({self.start_date} - {self.end_date})'


class AttendanceLog(models.Model):
    class Source(models.TextChoices):
        BIOMETRIC = 'biometric', 'Biometric'
        MOBILE = 'mobile', 'Mobile'
        WEB = 'web', 'Web'
        MANUAL = 'manual', 'Manual'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='attendance_logs')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='attendance_logs')
    check_in = models.DateTimeField(db_index=True)
    check_out = models.DateTimeField(blank=True, null=True)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.WEB)
    device_id = models.CharField(max_length=128, blank=True, null=True)
    lat = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    lng = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['tenant', 'employee', 'check_in']),
        ]

    def __str__(self):
        return f'{self.employee} @ {self.check_in}'


class Timesheet(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='timesheets')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='timesheets')
    work_date = models.DateField(db_index=True)
    scheduled_start = models.DateTimeField(blank=True, null=True)
    scheduled_end = models.DateTimeField(blank=True, null=True)
    actual_in = models.DateTimeField(blank=True, null=True)
    actual_out = models.DateTimeField(blank=True, null=True)
    worked_minutes = models.PositiveIntegerField(default=0)
    required_minutes = models.PositiveIntegerField(default=0)
    normal_overtime_minutes = models.PositiveIntegerField(default=0)
    weekend_overtime_minutes = models.PositiveIntegerField(default=0)
    holiday_overtime_minutes = models.PositiveIntegerField(default=0)
    late_minutes = models.PositiveIntegerField(default=0)
    early_leave_minutes = models.PositiveIntegerField(default=0)
    is_absent = models.BooleanField(default=False)
    anomaly_flag = models.BooleanField(default=False)
    overtime_pay_amount = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0.000'))
    ai_features = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'employee', 'work_date'], name='uq_hrms_timesheet_tenant_employee_workdate'),
        ]
        indexes = [
            models.Index(fields=['tenant', 'work_date']),
            models.Index(fields=['tenant', 'employee', 'work_date']),
        ]

    def __str__(self):
        return f'{self.employee} - {self.work_date}'


class OvertimePolicy(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='overtime_policies')
    name = models.CharField(max_length=120)
    country = models.CharField(max_length=2, choices=Company.Country.choices)
    effective_from = models.DateField()
    effective_to = models.DateField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['tenant', 'country', 'effective_from']),
        ]

    def __str__(self):
        return f'{self.name} ({self.country})'

    def is_applicable_on(self, on_date: datetime.date) -> bool:
        if not self.is_active:
            return False
        if on_date < self.effective_from:
            return False
        if self.effective_to and on_date > self.effective_to:
            return False
        return True


class LeaveType(models.Model):
    class LeaveCategory(models.TextChoices):
        ANNUAL = 'annual', 'Annual'
        SICK = 'sick', 'Sick'
        UNPAID = 'unpaid', 'Unpaid'
        EMERGENCY = 'emergency', 'Emergency'
        MATERNITY = 'maternity', 'Maternity'
        HAJ = 'haj', 'Haj'
        OTHER = 'other', 'Other'

    class AccrualMethod(models.TextChoices):
        MONTHLY = 'monthly', 'Monthly'
        YEARLY = 'yearly', 'Yearly'
        NONE = 'none', 'None'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='leave_types')
    name = models.CharField(max_length=120)
    code = models.CharField(max_length=40)
    leave_category = models.CharField(max_length=20, choices=LeaveCategory.choices, default=LeaveCategory.ANNUAL)
    accrual_method = models.CharField(max_length=10, choices=AccrualMethod.choices, default=AccrualMethod.NONE)
    accrual_rate_per_month = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0.00'))
    max_balance = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    carry_forward_allowed = models.BooleanField(default=False)
    max_carry_forward = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    encashable = models.BooleanField(default=False)
    requires_attachment = models.BooleanField(default=False)
    requires_approval = models.BooleanField(default=True)
    deduct_from_payroll = models.BooleanField(default=False)
    deduction_rate_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'code'], name='uq_hrms_leavetype_tenant_code'),
        ]
        indexes = [
            models.Index(fields=['tenant', 'is_active']),
            models.Index(fields=['tenant', 'leave_category']),
        ]


class LeaveBalance(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='leave_balances')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='leave_balances')
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE, related_name='balances')
    balance_days = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    last_accrual_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'employee', 'leave_type'], name='uq_hrms_leavebalance_tenant_employee_type'),
        ]
        indexes = [
            models.Index(fields=['tenant', 'employee']),
        ]


class LeaveRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'
        CANCELLED = 'cancelled', 'Cancelled'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='leave_requests')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='leave_requests')
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE, related_name='leave_requests')
    start_date = models.DateField()
    end_date = models.DateField()
    total_days = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0.00'))
    reason = models.TextField(blank=True, null=True)
    attachment = models.FileField(upload_to='hrms/leave_attachments/%Y/%m/', blank=True, null=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='hrms_approved_leave_requests')
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['tenant', 'employee', 'status']),
            models.Index(fields=['tenant', 'start_date', 'end_date']),
        ]


class PayrollPeriod(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        PROCESSING = 'processing', 'Processing'
        CLOSED = 'closed', 'Closed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='payroll_periods')
    name = models.CharField(max_length=120)
    start_date = models.DateField()
    end_date = models.DateField()
    pay_date = models.DateField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(end_date__gte=models.F('start_date')), name='ck_hrms_payroll_period_date_range'),
            models.UniqueConstraint(fields=['tenant', 'name'], name='uq_hrms_payroll_period_tenant_name'),
        ]
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['tenant', 'start_date', 'end_date']),
        ]


class SalaryStructure(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='salary_structures')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='salary_structures')
    basic_salary = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0.000'))
    housing_allowance = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0.000'))
    transport_allowance = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0.000'))
    other_allowances = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0.000'))
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True) | models.Q(effective_to__gte=models.F('effective_from')),
                name='ck_hrms_salary_structure_effective_range',
            ),
        ]
        indexes = [
            models.Index(fields=['tenant', 'employee', 'effective_from']),
        ]


class PayrollResult(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='payroll_results')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='payroll_results')
    period = models.ForeignKey(PayrollPeriod, on_delete=models.CASCADE, related_name='results')
    basic_salary = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0.000'))
    total_allowances = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0.000'))
    overtime_pay = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0.000'))
    leave_deduction = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0.000'))
    other_deductions = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0.000'))
    gross_salary = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0.000'))
    net_salary = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0.000'))
    currency = models.CharField(max_length=8, default='OMR')
    wps_ready = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'employee', 'period'], name='uq_hrms_payroll_result_tenant_employee_period'),
        ]
        indexes = [
            models.Index(fields=['tenant', 'period']),
        ]


class OvertimeRateRule(models.Model):
    class DayType(models.TextChoices):
        WORKING_DAY = 'working_day', 'Working Day'
        WEEKEND = 'weekend', 'Weekend'
        PUBLIC_HOLIDAY = 'public_holiday', 'Public Holiday'
        RAMADAN_SPECIAL = 'ramadan_special', 'Ramadan Special'

    class OvertimeType(models.TextChoices):
        NORMAL = 'normal', 'Normal'
        NIGHT = 'night', 'Night'
        HOLIDAY = 'holiday', 'Holiday'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    policy = models.ForeignKey(OvertimePolicy, on_delete=models.CASCADE, related_name='rate_rules')
    day_type = models.CharField(max_length=20, choices=DayType.choices)
    overtime_type = models.CharField(max_length=20, choices=OvertimeType.choices, default=OvertimeType.NORMAL)
    rate_multiplier = models.DecimalField(max_digits=6, decimal_places=3, default=Decimal('1.000'))
    min_minutes_threshold = models.PositiveIntegerField(default=0)
    max_minutes_per_day = models.PositiveIntegerField(default=600)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['policy', 'day_type', 'overtime_type']),
        ]

    def __str__(self):
        return f'{self.policy.name} - {self.day_type} - {self.overtime_type}'


class OvertimePrediction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='overtime_predictions')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='overtime_predictions')
    prediction_date = models.DateField(null=True, blank=True)
    predicted_overtime_minutes = models.PositiveIntegerField(default=0)
    model_version = models.CharField(max_length=64, default='v1')
    target_month = models.DateField()
    predicted_minutes = models.PositiveIntegerField(default=0)
    confidence_score = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    model_meta = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['tenant', 'target_month']),
            models.Index(fields=['tenant', 'prediction_date']),
        ]


class PayrollOvertimeEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='payroll_overtime_entries')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='payroll_overtime_entries')
    period_year = models.PositiveSmallIntegerField()
    period_month = models.PositiveSmallIntegerField()
    total_overtime_minutes = models.PositiveIntegerField(default=0)
    total_overtime_pay = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0.000'))
    breakdown = models.JSONField(default=dict, blank=True)
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'employee', 'period_year', 'period_month'],
                name='uq_hrms_payroll_ot_tenant_employee_period',
            ),
            models.CheckConstraint(
                condition=models.Q(period_month__gte=1) & models.Q(period_month__lte=12),
                name='ck_hrms_payroll_ot_month_range',
            ),
        ]
        indexes = [
            models.Index(fields=['tenant', 'period_year', 'period_month']),
        ]


class AuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Company, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='hrms_audit_logs')
    method = models.CharField(max_length=10)
    path = models.CharField(max_length=500)
    status_code = models.PositiveIntegerField(default=0)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['tenant', 'created_at']),
            models.Index(fields=['user', 'created_at']),
        ]


def resolve_shift_window(shift_version: ShiftVersion, work_date: datetime.date, tz) -> tuple[datetime.datetime, datetime.datetime]:
    start_naive = datetime.datetime.combine(work_date, shift_version.start_time)
    end_naive = datetime.datetime.combine(work_date, shift_version.end_time)

    start_dt = timezone.make_aware(start_naive, tz)
    end_dt = timezone.make_aware(end_naive, tz)
    if end_dt <= start_dt:
        end_dt = end_dt + datetime.timedelta(days=1)
    return start_dt, end_dt
