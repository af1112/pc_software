from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.db import transaction
from decimal import Decimal, ROUND_HALF_UP
import uuid


User = get_user_model()


class LaborSupplyCompany(models.Model):
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='labor_supply_companies',
        verbose_name=_('Organization'),
    )
    name = models.CharField(_('Company Name'), max_length=150)
    code = models.CharField(_('Company Code'), max_length=50, blank=True, null=True)
    is_active = models.BooleanField(_('Is Active'), default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Labor Supply Company')
        verbose_name_plural = _('Labor Supply Companies')
        ordering = ['name']
        unique_together = [('organization', 'name')]

    def __str__(self):
        return self.name


class WorkUnit(models.Model):
    class UnitType(models.TextChoices):
        PROJECT = 'project', _('Project')
        OFFICE = 'office', _('Office')
        SITE = 'site', _('Site')
        DEPARTMENT = 'department', _('Department')

    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='work_units',
        verbose_name=_('Organization'),
    )
    name = models.CharField(_('Unit Name'), max_length=150)
    code = models.CharField(_('Unit Code'), max_length=50, blank=True, null=True)
    unit_type = models.CharField(_('Unit Type'), max_length=20, choices=UnitType.choices, default=UnitType.PROJECT)
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='children')
    supervisor = models.ForeignKey(
        'Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='supervised_work_units',
        verbose_name=_('Unit Supervisor'),
    )
    is_active = models.BooleanField(_('Is Active'), default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Work Unit')
        verbose_name_plural = _('Work Units')
        ordering = ['name']
        unique_together = [('organization', 'name')]

    def __str__(self):
        return self.name


class Employee(models.Model):
    class Gender(models.TextChoices):
        MALE = 'male', _('Male')
        FEMALE = 'female', _('Female')
        OTHER = 'other', _('Other')

    class MaritalStatus(models.TextChoices):
        SINGLE = 'single', _('Single')
        MARRIED = 'married', _('Married')
        DIVORCED = 'divorced', _('Divorced')
        WIDOWED = 'widowed', _('Widowed')

    class EmploymentType(models.TextChoices):
        FULL_TIME = 'full_time', _('Full-time')
        PART_TIME = 'part_time', _('Part-time')
        CONTRACT = 'contract', _('Contract')

    class PaymentMethod(models.TextChoices):
        BANK_TRANSFER = 'bank_transfer', _('Bank Transfer')
        CASH = 'cash', _('Cash')
        WPS = 'wps', _('WPS')

    class NationalityType(models.TextChoices):
        OMANI = 'omani', _('Omani')
        EXPAT = 'expat', _('Expat')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='employee',
        verbose_name=_('User Account'),
        db_constraint=False,
    )
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='employees',
        verbose_name=_('Organization'),
    )
    supply_company = models.ForeignKey(
        'LaborSupplyCompany',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='employees',
        verbose_name=_('Labor Supply Company'),
        db_constraint=False,
    )
    work_unit = models.ForeignKey(
        'WorkUnit',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='employees',
        verbose_name=_('Work Unit'),
        db_constraint=False,
    )
    employee_id = models.CharField(_('Employee ID'), max_length=50, blank=True, null=True)
    company_id = models.CharField(_('Company ID'), max_length=50, blank=True, null=True)
    branch_id = models.CharField(_('Branch ID'), max_length=50, blank=True, null=True)
    department_id = models.CharField(_('Department ID'), max_length=50, blank=True, null=True)
    position_id = models.CharField(_('Position ID'), max_length=50, blank=True, null=True)

    first_name = models.CharField(_('First Name'), max_length=100)
    last_name = models.CharField(_('Last Name'), max_length=100)
    national_id = models.CharField(_('National ID'), max_length=50, blank=True, null=True)
    passport_no = models.CharField(_('Passport Number'), max_length=50, blank=True, null=True)
    nationality = models.CharField(_('Nationality'), max_length=80, blank=True, null=True)
    gender = models.CharField(_('Gender'), max_length=20, choices=Gender.choices, blank=True, null=True)
    date_of_birth = models.DateField(_('Date of Birth'), blank=True, null=True)
    marital_status = models.CharField(_('Marital Status'), max_length=20, choices=MaritalStatus.choices, blank=True, null=True)
    phone = models.CharField(_('Phone'), max_length=50, blank=True, null=True)
    email = models.EmailField(_('Email'), blank=True, null=True)

    department = models.CharField(_('Department'), max_length=100, blank=True, null=True)
    position_title = models.CharField(_('Position Title'), max_length=120, blank=True, null=True)
    employment_type = models.CharField(_('Employment Type'), max_length=20, choices=EmploymentType.choices, blank=True, null=True)
    hire_date = models.DateField(_('Hire Date'), blank=True, null=True)
    probation_end_date = models.DateField(_('Probation End Date'), blank=True, null=True)
    contract_start = models.DateField(_('Contract Start Date'), blank=True, null=True)
    contract_end = models.DateField(_('Contract End Date'), blank=True, null=True)
    reporting_manager = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='direct_reports',
        verbose_name=_('Reporting Manager'),
        db_constraint=False,
    )

    bank_name = models.CharField(_('Bank Name'), max_length=120, blank=True, null=True)
    iban = models.CharField(_('IBAN'), max_length=64, blank=True, null=True)
    payment_method = models.CharField(_('Payment Method'), max_length=20, choices=PaymentMethod.choices, blank=True, null=True)
    basic_salary = models.DecimalField(_('Basic Salary'), max_digits=12, decimal_places=3, blank=True, null=True)
    currency = models.CharField(_('Currency'), max_length=10, blank=True, null=True)

    omani_or_expat = models.CharField(_('Omani/Expat'), max_length=10, choices=NationalityType.choices, blank=True, null=True)
    pasi_registered = models.BooleanField(_('PASI Registered'), default=False)
    wps_required = models.BooleanField(_('WPS Required'), default=False)

    is_active = models.BooleanField(_('Is Active'), default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Employee')
        verbose_name_plural = _('Employees')
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return f"{self.first_name} {self.last_name}".strip()


class SalaryStructure(models.Model):
    class PayType(models.TextChoices):
        MONTHLY = 'monthly', _('Monthly')
        DAILY = 'daily', _('Daily')
        HOURLY = 'hourly', _('Hourly')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name='salary_structures',
        db_column='employee_ref_id',
    )

    effective_from = models.DateField(_('Effective From'))
    effective_to = models.DateField(_('Effective To'), blank=True, null=True)
    pay_type = models.CharField(
        _('Pay Type'),
        max_length=20,
        choices=PayType.choices,
        default=PayType.MONTHLY,
        db_column='compensation_basis',
    )
    base_salary = models.DecimalField(_('Base Salary'), max_digits=12, decimal_places=3, default=0)
    daily_rate = models.DecimalField(_('Daily Rate'), max_digits=12, decimal_places=3, blank=True, null=True)
    hourly_rate = models.DecimalField(_('Hourly Rate'), max_digits=12, decimal_places=3, blank=True, null=True)
    standard_working_days = models.DecimalField(_('Standard Working Days / Month'), max_digits=6, decimal_places=2, default=30)
    standard_working_hours_per_day = models.DecimalField(_('Standard Working Hours / Day'), max_digits=6, decimal_places=2, default=8)
    currency = models.CharField(_('Currency'), max_length=10, default='OMR')
    food_provided = models.BooleanField(_('Food Provided'), default=False)
    accommodation_provided = models.BooleanField(_('Accommodation Provided'), default=False)
    transport_provided = models.BooleanField(_('Transport Provided'), default=False)
    in_kind_benefits_notes = models.TextField(_('In-kind Benefits Notes'), blank=True, null=True)
    notes = models.TextField(_('Notes'), blank=True, null=True)
    is_active = models.BooleanField(_('Is Active'), default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Salary Structure')
        verbose_name_plural = _('Salary Structures')
        ordering = ['-effective_from']
        db_table = 'hr_personnel_salaryprofile'
        indexes = [
            models.Index(fields=['employee', 'is_active']),
            models.Index(fields=['employee', 'effective_from']),
        ]

    def clean(self):
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValidationError('effective_to cannot be earlier than effective_from.')

    def save(self, *args, **kwargs):
        self.full_clean()
        with transaction.atomic():
            if self.is_active:
                SalaryStructure.objects.filter(employee=self.employee, is_active=True).exclude(pk=self.pk).update(is_active=False)
            super().save(*args, **kwargs)

    def resolve_base_pay(self, payable_days=None, payable_hours=None):
        payable_days = Decimal(str(payable_days if payable_days is not None else self.standard_working_days or 0))
        payable_hours = Decimal(str(payable_hours if payable_hours is not None else 0))
        base_salary = Decimal(str(self.base_salary or 0))
        standard_days = Decimal(str(self.standard_working_days or 0))
        standard_hours_per_day = Decimal(str(self.standard_working_hours_per_day or 0))

        if self.pay_type == self.PayType.MONTHLY:
            return base_salary.quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)

        if self.pay_type == self.PayType.DAILY:
            if self.daily_rate is not None:
                rate = Decimal(str(self.daily_rate))
            elif standard_days > 0:
                rate = base_salary / standard_days
            else:
                rate = Decimal('0.000')
            return (rate * payable_days).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)

        if self.hourly_rate is not None:
            rate = Decimal(str(self.hourly_rate))
        else:
            monthly_hours = standard_days * standard_hours_per_day
            rate = (base_salary / monthly_hours) if monthly_hours > 0 else Decimal('0.000')

        effective_hours = payable_hours
        if effective_hours <= 0 and standard_days > 0 and standard_hours_per_day > 0:
            effective_hours = standard_days * standard_hours_per_day
        return (rate * effective_hours).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)

    def __str__(self):
        return f"{self.employee} ({self.effective_from})"


# Backward-compatible alias for legacy imports.
SalaryProfile = SalaryStructure


class SalaryComponent(models.Model):
    class ComponentType(models.TextChoices):
        EARNING = 'earning', _('Earning')
        DEDUCTION = 'deduction', _('Deduction')

    class CalculationMethod(models.TextChoices):
        FIXED_MONTHLY = 'fixed_monthly', _('Fixed Monthly')
        PER_DAY = 'per_day', _('Per Day')
        PER_HOUR = 'per_hour', _('Per Hour')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    salary_structure = models.ForeignKey(
        SalaryStructure,
        on_delete=models.CASCADE,
        related_name='components',
        db_column='salary_profile_id',
    )

    component_type = models.CharField(_('Type'), max_length=20, choices=ComponentType.choices)
    title = models.CharField(_('Title'), max_length=120)
    # Legacy schema compatibility (existing DB column is still NOT NULL in some environments).
    is_percentage = models.BooleanField(_('Is Percentage'), default=False)
    percentage = models.DecimalField(_('Percentage'), max_digits=6, decimal_places=3, blank=True, null=True)
    calculation_method = models.CharField(
        _('Calculation Method'),
        max_length=20,
        choices=CalculationMethod.choices,
        db_column='calculation_frequency',
    )
    amount = models.DecimalField(_('Amount'), max_digits=12, decimal_places=3, default=0)
    taxable = models.BooleanField(_('Taxable'), default=True)
    affects_net_pay = models.BooleanField(_('Affects Net Pay'), default=True)
    is_active = models.BooleanField(_('Is Active'), default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Salary Component')
        verbose_name_plural = _('Salary Components')
        ordering = ['component_type', 'title']
        db_table = 'hr_personnel_salarycomponent'
        indexes = [
            models.Index(fields=['salary_structure', 'is_active']),
            models.Index(fields=['component_type', 'calculation_method']),
        ]

    def clean(self):
        if self.amount is None or self.amount <= 0:
            raise ValidationError('amount must be positive.')

    def calculate_amount(self, payable_days=None, payable_hours=None):
        payable_days = Decimal(str(payable_days or 0))
        payable_hours = Decimal(str(payable_hours or 0))

        raw = Decimal(str(self.amount or 0))

        if self.calculation_method == self.CalculationMethod.PER_DAY:
            raw *= payable_days
        elif self.calculation_method == self.CalculationMethod.PER_HOUR:
            raw *= payable_hours

        return raw.quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)

    def __str__(self):
        return f"{self.title} ({self.component_type})"


class BankAccount(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='bank_accounts')

    bank_name = models.CharField(_('Bank Name'), max_length=120)
    account_holder = models.CharField(_('Account Holder'), max_length=120, blank=True, null=True)
    account_number = models.CharField(_('Account Number'), max_length=100, blank=True, null=True)
    iban = models.CharField(_('IBAN'), max_length=64, blank=True, null=True)
    is_primary = models.BooleanField(_('Is Primary'), default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Bank Account')
        verbose_name_plural = _('Bank Accounts')
        ordering = ['-is_primary', '-created_at']

    def __str__(self):
        return f"{self.bank_name} - {self.iban or self.account_number or ''}".strip()


class PayrollPeriod(models.Model):
    class Status(models.TextChoices):
        OPEN = 'open', _('Open')
        PROCESSING = 'processing', _('Processing')
        REVIEW = 'review', _('Review')
        FINALIZED = 'finalized', _('Finalized')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='payroll_periods',
        verbose_name=_('Organization'),
        null=True,
        blank=True,
    )
    name = models.CharField(_('Period Name'), max_length=120)
    start_date = models.DateField(_('Start Date'))
    end_date = models.DateField(_('End Date'))
    status = models.CharField(_('Status'), max_length=20, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Payroll Period')
        verbose_name_plural = _('Payroll Periods')
        ordering = ['-start_date', '-created_at']

    @property
    def code(self):
        return self.name

    def clean(self):
        if self.end_date < self.start_date:
            raise ValidationError(_('End date cannot be earlier than start date.'))
        open_qs = PayrollPeriod.objects.filter(status=self.Status.OPEN)
        if self.organization_id:
            open_qs = open_qs.filter(organization_id=self.organization_id)
        if self.pk:
            open_qs = open_qs.exclude(pk=self.pk)
        if open_qs.exists() and self.status == self.Status.OPEN:
            raise ValidationError(_('Only one OPEN payroll period is allowed.'))

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class PayrollRun(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft', _('Draft')
        COMPLETED = 'completed', _('Completed')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    period = models.ForeignKey(PayrollPeriod, on_delete=models.CASCADE, related_name='runs')
    run_date = models.DateTimeField(_('Run Date'), auto_now_add=True)
    status = models.CharField(_('Status'), max_length=20, choices=Status.choices, default=Status.DRAFT)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_payroll_runs',
        db_constraint=False,
        verbose_name=_('Created By'),
    )
    execution_ms = models.PositiveIntegerField(_('Execution Time (ms)'), default=0)

    class Meta:
        verbose_name = _('Payroll Run')
        verbose_name_plural = _('Payroll Runs')
        ordering = ['-run_date']

    def __str__(self):
        return f"{self.period} - {self.run_date:%Y-%m-%d %H:%M}"


class PayrollSlip(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft', _('Draft')
        APPROVED = 'approved', _('Approved')
        PAID = 'paid', _('Paid')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='payroll_slips')
    period = models.ForeignKey(PayrollPeriod, on_delete=models.SET_NULL, null=True, blank=True, related_name='slips')
    salary_profile = models.ForeignKey(SalaryStructure, on_delete=models.SET_NULL, null=True, blank=True, related_name='payroll_slips')
    bank_account = models.ForeignKey(BankAccount, on_delete=models.SET_NULL, null=True, blank=True, related_name='payroll_slips')

    period_year = models.IntegerField(_('Year'))
    period_month = models.IntegerField(_('Month'))
    payable_days = models.DecimalField(_('Payable Days'), max_digits=6, decimal_places=2, default=30)
    payable_hours = models.DecimalField(_('Payable Hours'), max_digits=8, decimal_places=2, default=0)

    base_salary = models.DecimalField(_('Base Salary'), max_digits=12, decimal_places=3, default=0)
    currency = models.CharField(_('Currency'), max_length=10, default='OMR')
    total_allowances = models.DecimalField(_('Total Allowances'), max_digits=12, decimal_places=3, default=0)
    total_deductions = models.DecimalField(_('Total Deductions'), max_digits=12, decimal_places=3, default=0)
    total_benefits = models.DecimalField(_('Total Benefits'), max_digits=12, decimal_places=3, default=0)
    overtime_amount = models.DecimalField(_('Overtime Amount'), max_digits=12, decimal_places=3, default=0)

    gross_amount = models.DecimalField(_('Gross Amount'), max_digits=12, decimal_places=3, default=0)
    net_amount = models.DecimalField(_('Net Amount'), max_digits=12, decimal_places=3, default=0)
    gross_salary = models.DecimalField(_('Gross Salary'), max_digits=12, decimal_places=3, default=0)
    net_salary = models.DecimalField(_('Net Salary'), max_digits=12, decimal_places=3, default=0)

    status = models.CharField(_('Status'), max_length=10, choices=Status.choices, default=Status.DRAFT)
    paid_at = models.DateTimeField(_('Paid At'), blank=True, null=True)
    generated_at = models.DateTimeField(_('Generated At'), auto_now_add=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Payroll Slip')
        verbose_name_plural = _('Payroll Slips')
        ordering = ['-period_year', '-period_month', '-created_at']
        unique_together = ['employee', 'period_year', 'period_month']

    def clean(self):
        if self.period and self.period.status == PayrollPeriod.Status.FINALIZED and self.pk:
            raise ValidationError(_('Finalized payroll slips are locked and cannot be edited.'))

    def save(self, *args, **kwargs):
        self.gross_amount = Decimal(str(self.gross_amount or self.gross_salary or 0))
        self.net_amount = Decimal(str(self.net_amount or self.net_salary or 0))
        self.gross_salary = Decimal(str(self.gross_salary or self.gross_amount or 0))
        self.net_salary = Decimal(str(self.net_salary or self.net_amount or 0))
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.employee} - {self.period_year}/{self.period_month:02}"


class PayrollItem(models.Model):
    class ItemType(models.TextChoices):
        EARNING = 'earning', _('Earning')
        DEDUCTION = 'deduction', _('Deduction')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payroll_slip = models.ForeignKey(PayrollSlip, on_delete=models.CASCADE, related_name='items')

    item_type = models.CharField(_('Type'), max_length=20, choices=ItemType.choices)
    component_type = models.CharField(_('Component Type'), max_length=20, blank=True, default='')
    title = models.CharField(_('Title'), max_length=120)
    component_name = models.CharField(_('Component Name'), max_length=120, blank=True, default='')
    amount = models.DecimalField(_('Amount'), max_digits=12, decimal_places=3, default=0)

    class Meta:
        verbose_name = _('Payroll Item')
        verbose_name_plural = _('Payroll Items')
        ordering = ['item_type', 'title']

    def save(self, *args, **kwargs):
        if not self.component_name:
            self.component_name = self.title
        if not self.component_type:
            self.component_type = 'earning' if self.item_type == self.ItemType.EARNING else 'deduction'
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class LeavePolicy(models.Model):
    class LeaveType(models.TextChoices):
        ANNUAL = 'annual', _('Annual')
        SICK = 'sick', _('Sick')
        UNPAID = 'unpaid', _('Unpaid')
        EMERGENCY = 'emergency', _('Emergency')
        MATERNITY = 'maternity', _('Maternity')
        HAJ = 'haj', _('Haj')

    class AccrualMethod(models.TextChoices):
        MONTHLY = 'monthly', _('Monthly')
        YEARLY = 'yearly', _('Yearly')

    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='leave_policies',
        verbose_name=_('Organization'),
    )
    leave_type = models.CharField(_('Leave Type'), max_length=20, choices=LeaveType.choices)
    accrual_method = models.CharField(_('Accrual Method'), max_length=10, choices=AccrualMethod.choices)
    accrual_rate = models.DecimalField(_('Accrual Rate'), max_digits=8, decimal_places=2, default=0)
    carry_forward_allowed = models.BooleanField(_('Carry Forward Allowed'), default=False)
    max_carry_forward = models.DecimalField(_('Max Carry Forward'), max_digits=8, decimal_places=2, default=0)
    encashable = models.BooleanField(_('Encashable'), default=False)
    requires_approval = models.BooleanField(_('Requires Approval'), default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Leave Policy')
        verbose_name_plural = _('Leave Policies')
        unique_together = ['organization', 'leave_type']

    def __str__(self):
        return f"{self.organization} - {self.leave_type}"


class LeaveRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', _('Pending')
        APPROVED = 'approved', _('Approved')
        REJECTED = 'rejected', _('Rejected')
        CANCELLED = 'cancelled', _('Cancelled')

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='leave_requests')
    leave_type = models.CharField(_('Leave Type'), max_length=20, choices=LeavePolicy.LeaveType.choices)
    from_date = models.DateField(_('From Date'))
    to_date = models.DateField(_('To Date'))
    total_days = models.DecimalField(_('Total Days'), max_digits=6, decimal_places=2)
    reason = models.TextField(_('Reason'), blank=True, null=True)
    attachment = models.FileField(_('Attachment'), upload_to='leave_attachments/%Y/%m/', blank=True, null=True)
    status = models.CharField(_('Status'), max_length=10, choices=Status.choices, default=Status.PENDING)
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_leave_requests',
        db_constraint=False,
        verbose_name=_('Approved By'),
    )
    approved_at = models.DateTimeField(_('Approved At'), blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Leave Request')
        verbose_name_plural = _('Leave Requests')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.employee} - {self.leave_type} ({self.from_date} to {self.to_date})"


class LeaveAIInsight(models.Model):
    class InsightType(models.TextChoices):
        AUTO_APPROVAL = 'auto_approval', _('Auto Approval Suggestion')
        ABUSE_DETECTION = 'abuse_detection', _('Abuse Detection')
        STAFF_SHORTAGE = 'staff_shortage', _('Staff Shortage Prediction')

    leave_request = models.ForeignKey(LeaveRequest, on_delete=models.CASCADE, related_name='ai_insights')
    insight_type = models.CharField(_('Insight Type'), max_length=30, choices=InsightType.choices)
    score = models.DecimalField(_('Score'), max_digits=5, decimal_places=2, default=0)
    recommendation = models.CharField(_('Recommendation'), max_length=255)
    rationale = models.TextField(_('Rationale'), blank=True, null=True)
    generated_at = models.DateTimeField(_('Generated At'), auto_now_add=True)

    class Meta:
        verbose_name = _('Leave AI Insight')
        verbose_name_plural = _('Leave AI Insights')
        ordering = ['-generated_at']

    def __str__(self):
        return f"{self.leave_request_id} - {self.insight_type}"
