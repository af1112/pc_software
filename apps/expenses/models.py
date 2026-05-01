from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
import uuid

User = get_user_model()


class ExpenseCategory(models.Model):
    name = models.CharField(_("Category Name"), max_length=100)
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='expense_categories',
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(_("Is Active"), default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Expense Category")
        verbose_name_plural = _("Expense Categories")
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['created_by', 'name'], name='uniq_expense_category_per_user')
        ]

    def __str__(self):
        return self.name

class Trip(models.Model):
    TRAVEL_TYPES = [
        ('domestic', _('Domestic')),
        ('international', _('International')),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_("Trip Name"), max_length=200)
    travel_type = models.CharField(_("Travel Type"), max_length=20, choices=TRAVEL_TYPES, default='domestic')
    business_purpose = models.TextField(_("Business Purpose"), blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='trips')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class ExpenseReport(models.Model):
    STATUS_CHOICES = [
        ('draft', _('Draft')),
        ('submitted', _('Submitted')),
        ('approved', _('Approved')),
        ('rejected', _('Rejected')),
    ]

    class Meta:
        verbose_name = _("Statement")
        verbose_name_plural = _("Statements")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(_("Report Title"), max_length=200, help_text=_("e.g. Site Visit Expenses 2026-02-07"))
    business_purpose = models.TextField(_("Business Purpose"), blank=True, null=True)
    start_date = models.DateField(_("Duration From"), blank=True, null=True)
    end_date = models.DateField(_("Duration To"), blank=True, null=True)
    
    trip = models.ForeignKey(Trip, on_delete=models.SET_NULL, null=True, blank=True, related_name='reports')
    
    submitted_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='expense_reports')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    total_amount = models.DecimalField(max_digits=12, decimal_places=3, default=0.000)
    currency = models.CharField(max_length=10, default='OMR')
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.title} - {self.submitted_by.username}"

    def update_total(self):
        self.total_amount = sum(item.amount for item in self.items.all())
        self.save()

class Advance(models.Model):
    PAYMENT_MODES = [
        ('cash', _('Cash')),
        ('bank_transfer', _('Bank Transfer')),
        ('check', _('Check')),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='advances')
    amount = models.DecimalField(_("Amount"), max_digits=12, decimal_places=3)
    currency = models.CharField(_("Currency"), max_length=10, default='OMR')
    date = models.DateField(_("Date"))
    paid_through = models.CharField(_("Paid Through"), max_length=50, choices=PAYMENT_MODES, blank=True, null=True)
    reference_number = models.CharField(_("Reference #"), max_length=50, blank=True, null=True)
    notes = models.TextField(_("Notes"), blank=True, null=True)
    
    trip = models.ForeignKey(Trip, on_delete=models.SET_NULL, null=True, blank=True, related_name='advances')
    report = models.ForeignKey(ExpenseReport, on_delete=models.SET_NULL, null=True, blank=True, related_name='advances')
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Advance {self.amount} {self.currency} for {self.user.username}"

class ExpenseItem(models.Model):
    PAYMENT_MODES = [
        ('petty_cash', _('Petty Cash')),
        ('undeposited_funds', _('Undeposited Funds')),
        ('personal_card', _('Personal Card')),
        ('company_card', _('Company Card')),
    ]

    # Report is optional now to allow "Unreported Expenses"
    report = models.ForeignKey(ExpenseReport, related_name='items', on_delete=models.SET_NULL, null=True, blank=True)
    
    date = models.DateField(_("Expense Date"))
    merchant = models.CharField(_("Merchant"), max_length=100, blank=True, null=True, help_text=_("e.g. Shell, Starbucks"))
    category = models.CharField(_("Category"), max_length=100, help_text=_("e.g. Food, Transport, Material"))
    description = models.CharField(_("Description"), max_length=255, blank=True, null=True)
    reference_number = models.CharField(_("Reference #"), max_length=50, blank=True, null=True)
    
    amount = models.DecimalField(_("Amount"), max_digits=10, decimal_places=3)
    currency = models.CharField(_("Currency"), max_length=10, default='OMR')
    
    claim_reimbursement = models.BooleanField(_("Claim Reimbursement"), default=True)
    payment_mode = models.CharField(_("Payment Mode"), max_length=50, choices=PAYMENT_MODES, blank=True, null=True, help_text=_("Required if Reimbursement is OFF"))

    receipt_image = models.FileField(_("Receipt File"), upload_to='receipts/%Y/%m/', blank=True, null=True)
    
    # AI Fields
    is_ai_scanned = models.BooleanField(default=False)
    ai_confidence = models.FloatField(default=0.0, help_text="AI Confidence Score (0-1)")
    raw_ocr_text = models.TextField(blank=True, null=True, help_text="Raw text extracted from receipt")

    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='expenses')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.date} - {self.description} ({self.amount})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.report:
            self.report.update_total()
