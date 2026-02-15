from django.db import models
from django.utils.translation import gettext_lazy as _

class Organization(models.Model):
    name = models.CharField(_("Organization Name"), max_length=255)
    slug = models.SlugField(_("Subdomain/Slug"), unique=True, help_text=_("Used for URL routing (e.g., company-name)"))
    logo = models.FileField(_("Logo"), upload_to='org_logos/', blank=True, null=True)
    representative_name = models.CharField(_("Representative Name"), max_length=255, blank=True, null=True)
    representative_phone = models.CharField(_("Representative Phone"), max_length=50, blank=True, null=True)
    company_email = models.EmailField(_("Company Email"), blank=True, null=True)
    timezone = models.CharField(_("Time Zone"), max_length=64, default="UTC", help_text=_("e.g., Asia/Tehran, Europe/London"))
    
    # Subscription & Modules
    is_active = models.BooleanField(_("Is Active Subscription"), default=True)
    subscription_end_date = models.DateField(_("Subscription End Date"), null=True, blank=True)
    
    # Active Modules (Flags) - Only manageable by Software Support (Superuser)
    can_use_expenses = models.BooleanField(_("Enable Expense Manager"), default=False)
    can_use_ticketing = models.BooleanField(_("Enable Ticketing System"), default=False)
    can_use_attendance = models.BooleanField(_("Enable Attendance System"), default=True)
    can_use_projects = models.BooleanField(_("Enable Project Control"), default=False)
    can_use_dms = models.BooleanField(_("Enable Document DMS"), default=False)
    can_use_ai = models.BooleanField(_("Enable AI Engine"), default=False)
    can_use_menu = models.BooleanField(_("Enable Digital Menu"), default=False)
    can_use_club = models.BooleanField(_("Enable Customer Club"), default=False)
    can_use_personnel = models.BooleanField(_("Enable Personnel & Payroll"), default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _("Organization")
        verbose_name_plural = _("Organizations")
