from django.db import models
from django.utils.translation import gettext_lazy as _
import uuid


class Employee(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='employees',
        verbose_name=_('Organization'),
    )

    first_name = models.CharField(_('First Name'), max_length=100)
    last_name = models.CharField(_('Last Name'), max_length=100)
    national_id = models.CharField(_('National ID'), max_length=50, blank=True, null=True)
    phone = models.CharField(_('Phone'), max_length=50, blank=True, null=True)
    email = models.EmailField(_('Email'), blank=True, null=True)

    department = models.CharField(_('Department'), max_length=100, blank=True, null=True)
    position_title = models.CharField(_('Position Title'), max_length=120, blank=True, null=True)
    hire_date = models.DateField(_('Hire Date'), blank=True, null=True)
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
