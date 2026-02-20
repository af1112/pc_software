from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
import uuid


User = get_user_model()


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


class SalaryProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='salary_profiles')

    effective_from = models.DateField(_('Effective From'))
    base_salary = models.DecimalField(_('Base Salary'), max_digits=12, decimal_places=3, default=0)
    currency = models.CharField(_('Currency'), max_length=10, default='OMR')
    notes = models.TextField(_('Notes'), blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Salary Profile')
        verbose_name_plural = _('Salary Profiles')
        ordering = ['-effective_from']

    def __str__(self):
        return f"{self.employee} ({self.effective_from})"


class SalaryComponent(models.Model):
    class ComponentType(models.TextChoices):
        ALLOWANCE = 'allowance', _('Allowance')
        DEDUCTION = 'deduction', _('Deduction')
        BENEFIT = 'benefit', _('Benefit')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    salary_profile = models.ForeignKey(SalaryProfile, on_delete=models.CASCADE, related_name='components')

    component_type = models.CharField(_('Type'), max_length=20, choices=ComponentType.choices)
    title = models.CharField(_('Title'), max_length=120)

    is_percentage = models.BooleanField(_('Is Percentage'), default=False)
    percentage = models.DecimalField(_('Percentage'), max_digits=6, decimal_places=3, blank=True, null=True)
    amount = models.DecimalField(_('Amount'), max_digits=12, decimal_places=3, default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Salary Component')
        verbose_name_plural = _('Salary Components')
        ordering = ['component_type', 'title']

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


class PayrollSlip(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft', _('Draft')
        PAID = 'paid', _('Paid')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='payroll_slips')
    salary_profile = models.ForeignKey(SalaryProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='payroll_slips')
    bank_account = models.ForeignKey(BankAccount, on_delete=models.SET_NULL, null=True, blank=True, related_name='payroll_slips')

    period_year = models.IntegerField(_('Year'))
    period_month = models.IntegerField(_('Month'))

    base_salary = models.DecimalField(_('Base Salary'), max_digits=12, decimal_places=3, default=0)
    currency = models.CharField(_('Currency'), max_length=10, default='OMR')

    gross_amount = models.DecimalField(_('Gross Amount'), max_digits=12, decimal_places=3, default=0)
    net_amount = models.DecimalField(_('Net Amount'), max_digits=12, decimal_places=3, default=0)

    status = models.CharField(_('Status'), max_length=10, choices=Status.choices, default=Status.DRAFT)
    paid_at = models.DateTimeField(_('Paid At'), blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Payroll Slip')
        verbose_name_plural = _('Payroll Slips')
        ordering = ['-period_year', '-period_month', '-created_at']
        unique_together = ['employee', 'period_year', 'period_month']

    def __str__(self):
        return f"{self.employee} - {self.period_year}/{self.period_month:02}"


class PayrollItem(models.Model):
    class ItemType(models.TextChoices):
        ALLOWANCE = 'allowance', _('Allowance')
        DEDUCTION = 'deduction', _('Deduction')
        BENEFIT = 'benefit', _('Benefit')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payroll_slip = models.ForeignKey(PayrollSlip, on_delete=models.CASCADE, related_name='items')

    item_type = models.CharField(_('Type'), max_length=20, choices=ItemType.choices)
    title = models.CharField(_('Title'), max_length=120)
    amount = models.DecimalField(_('Amount'), max_digits=12, decimal_places=3, default=0)

    class Meta:
        verbose_name = _('Payroll Item')
        verbose_name_plural = _('Payroll Items')
        ordering = ['item_type', 'title']

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
