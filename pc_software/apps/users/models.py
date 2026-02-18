from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
# from apps.organizations.models import Organization

class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('supervisor', 'Supervisor'),
        ('user', 'User'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    organization = models.ForeignKey('organizations.Organization', on_delete=models.SET_NULL, null=True, blank=True, related_name='members')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='user')
    supervisor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='supervised_users',
        db_constraint=False,
    )
    preferred_language = models.CharField(
        max_length=10,
        choices=settings.LANGUAGES,
        default='en'
    )
    # Currency Settings
    currency_code = models.CharField(max_length=10, default='OMR', help_text="ISO 4217 Currency Code (e.g. OMR, USD)")
    currency_symbol = models.CharField(max_length=10, default='ر.ع.', help_text="Currency Symbol (e.g. $, €)")
    currency_decimal_places = models.IntegerField(default=3, help_text="Number of decimal places (e.g. 3 for OMR, 2 for USD)")
    timezone = models.CharField(max_length=64, default='Asia/Tehran', help_text="IANA timezone (e.g. Asia/Tehran)")

    # Attendance Settings
    require_photo = models.BooleanField(default=True, help_text="Require a photo for attendance clock-in/out")

    def __str__(self):
        return f"{self.user.username} Profile"

    class Meta:
        permissions = [
            ("can_access_expenses", "Can access Expense Manager"),
            ("can_access_ticketing", "Can access Ticketing System"),
            ("can_access_attendance", "Can access Presence & Attendance"),
            ("can_access_personnel", "Can access Personnel & Payroll"),
            ("can_access_projects", "Can access Project Control"),
            ("can_access_dms", "Can access Document DMS"),
            ("can_access_ai", "Can access AI Engine"),
            ("can_access_menu", "Can access Digital Menu"),
            ("can_access_club", "Can access Customer Club"),
        ]

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    try:
        instance.profile.save()
    except UserProfile.DoesNotExist:
        UserProfile.objects.create(user=instance)
