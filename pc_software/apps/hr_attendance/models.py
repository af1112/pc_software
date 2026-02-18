from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

class Attendance(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='attendances', verbose_name=_("User"))
    date = models.DateField(_("Date"), default=timezone.now)
    clock_in = models.DateTimeField(_("Clock In"), null=True, blank=True)
    clock_out = models.DateTimeField(_("Clock Out"), null=True, blank=True)
    clock_in_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='attendance_clockins_recorded',
        verbose_name=_("Clock-in By"),
        db_constraint=False
    )
    clock_out_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='attendance_clockouts_recorded',
        verbose_name=_("Clock-out By"),
        db_constraint=False
    )
    
    # Location tracking
    latitude = models.DecimalField(_("Latitude"), max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(_("Longitude"), max_digits=9, decimal_places=6, null=True, blank=True)
    clock_in_latitude = models.DecimalField(_("Clock-in Latitude"), max_digits=9, decimal_places=6, null=True, blank=True)
    clock_in_longitude = models.DecimalField(_("Clock-in Longitude"), max_digits=9, decimal_places=6, null=True, blank=True)
    clock_out_latitude = models.DecimalField(_("Clock-out Latitude"), max_digits=9, decimal_places=6, null=True, blank=True)
    clock_out_longitude = models.DecimalField(_("Clock-out Longitude"), max_digits=9, decimal_places=6, null=True, blank=True)
    
    # Photo proof (Stored as LongText for large Base64 strings)
    photo_in = models.TextField(_("Photo In"), null=True, blank=True)
    photo_out = models.TextField(_("Photo Out"), null=True, blank=True)
    
    ip_address = models.GenericIPAddressField(_("IP Address"), null=True, blank=True)
    note = models.TextField(_("Note"), null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Attendance")
        verbose_name_plural = _("Attendances")
        ordering = ['-date', '-clock_in']
        unique_together = ['user', 'date']

    def __str__(self):
        return f"{self.user.username} - {self.date}"

    @property
    def duration(self):
        if self.clock_in and self.clock_out:
            diff = self.clock_out - self.clock_in
            hours, remainder = divmod(diff.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            return f"{hours:02}:{minutes:02}:{seconds:02}"
        return None

    @property
    def clock_in_location_text(self):
        lat = self.clock_in_latitude if self.clock_in_latitude is not None else self.latitude
        lng = self.clock_in_longitude if self.clock_in_longitude is not None else self.longitude
        if lat is None or lng is None:
            return None
        return f"{lat}, {lng}"

    @property
    def clock_out_location_text(self):
        lat = self.clock_out_latitude
        lng = self.clock_out_longitude
        if lat is None or lng is None:
            return None
        return f"{lat}, {lng}"
