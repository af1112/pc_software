from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from django.utils import timezone


class Shift(models.Model):
    shift_name = models.CharField(_('Shift Name'), max_length=120)
    start_time = models.TimeField(_('Start Time'))
    end_time = models.TimeField(_('End Time'))
    grace_in = models.PositiveIntegerField(_('Grace In (minutes)'), default=0)
    grace_out = models.PositiveIntegerField(_('Grace Out (minutes)'), default=0)
    overtime_policy_id = models.CharField(_('Overtime Policy ID'), max_length=64, blank=True, null=True)
    is_night_shift = models.BooleanField(_('Is Night Shift'), default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Shift')
        verbose_name_plural = _('Shifts')
        ordering = ['shift_name']

    def __str__(self):
        return self.shift_name

class Attendance(models.Model):
    class Source(models.TextChoices):
        DEVICE = 'device', _('Device')
        MOBILE = 'mobile', _('Mobile')
        WEB = 'web', _('Web')
        MANUAL = 'manual', _('Manual')

    class CaptureMode(models.TextChoices):
        BIOMETRIC = 'biometric', _('Biometric')
        MOBILE_GPS = 'mobile_gps', _('Mobile GPS')
        WEB_PUNCH = 'web_punch', _('Web Punch')
        MANUAL = 'manual', _('Manual')
        FACE_RECOGNITION = 'face_recognition', _('Face Recognition')
        GEOFENCING = 'geofencing', _('Geofencing')

    class Status(models.TextChoices):
        PRESENT = 'present', _('Present')
        LATE = 'late', _('Late')
        ABSENT = 'absent', _('Absent')

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='attendances',
        verbose_name=_("User"),
        null=True,
        blank=True,
    )
    employee = models.ForeignKey(
        'hr_personnel.Employee',
        on_delete=models.SET_NULL,
        related_name='attendances',
        verbose_name=_("Employee"),
        null=True,
        blank=True,
        db_constraint=False,
    )
    date = models.DateField(_("Date"), default=timezone.now)
    user_clock_in = models.DateTimeField(_("User Clock In"), null=True, blank=True)
    user_clock_out = models.DateTimeField(_("User Clock Out"), null=True, blank=True)
    user_lunch_out = models.DateTimeField(_("User Lunch Out"), null=True, blank=True)
    user_lunch_in = models.DateTimeField(_("User Lunch In"), null=True, blank=True)
    supervisor_clock_in = models.DateTimeField(_("Supervisor Clock In"), null=True, blank=True)
    supervisor_clock_out = models.DateTimeField(_("Supervisor Clock Out"), null=True, blank=True)
    supervisor_lunch_out = models.DateTimeField(_("Supervisor Lunch Out"), null=True, blank=True)
    supervisor_lunch_in = models.DateTimeField(_("Supervisor Lunch In"), null=True, blank=True)
    clock_in = models.DateTimeField(_("Clock In"), null=True, blank=True)
    lunch_out = models.DateTimeField(_("Lunch Out"), null=True, blank=True)
    lunch_in = models.DateTimeField(_("Lunch In"), null=True, blank=True)
    clock_out = models.DateTimeField(_("Clock Out"), null=True, blank=True)
    source = models.CharField(_("Source"), max_length=20, choices=Source.choices, default=Source.WEB)
    capture_mode = models.CharField(_("Capture Mode"), max_length=30, choices=CaptureMode.choices, default=CaptureMode.WEB_PUNCH)
    device_id = models.CharField(_("Device ID"), max_length=120, blank=True, null=True)
    shift = models.ForeignKey('Shift', on_delete=models.SET_NULL, null=True, blank=True, related_name='attendance_logs', verbose_name=_("Shift"), db_constraint=False)
    status = models.CharField(_("Status"), max_length=10, choices=Status.choices, default=Status.PRESENT)
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
    lunch_out_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='attendance_lunchouts_recorded',
        verbose_name=_("Lunch-out By"),
        db_constraint=False
    )
    lunch_in_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='attendance_lunchins_recorded',
        verbose_name=_("Lunch-in By"),
        db_constraint=False
    )
    
    # Location tracking
    latitude = models.DecimalField(_("Latitude"), max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(_("Longitude"), max_digits=9, decimal_places=6, null=True, blank=True)
    location_lat = models.DecimalField(_("Location Latitude"), max_digits=9, decimal_places=6, null=True, blank=True)
    location_lng = models.DecimalField(_("Location Longitude"), max_digits=9, decimal_places=6, null=True, blank=True)
    clock_in_latitude = models.DecimalField(_("Clock-in Latitude"), max_digits=9, decimal_places=6, null=True, blank=True)
    clock_in_longitude = models.DecimalField(_("Clock-in Longitude"), max_digits=9, decimal_places=6, null=True, blank=True)
    clock_out_latitude = models.DecimalField(_("Clock-out Latitude"), max_digits=9, decimal_places=6, null=True, blank=True)
    clock_out_longitude = models.DecimalField(_("Clock-out Longitude"), max_digits=9, decimal_places=6, null=True, blank=True)
    lunch_out_latitude = models.DecimalField(_("Lunch-out Latitude"), max_digits=9, decimal_places=6, null=True, blank=True)
    lunch_out_longitude = models.DecimalField(_("Lunch-out Longitude"), max_digits=9, decimal_places=6, null=True, blank=True)
    lunch_in_latitude = models.DecimalField(_("Lunch-in Latitude"), max_digits=9, decimal_places=6, null=True, blank=True)
    lunch_in_longitude = models.DecimalField(_("Lunch-in Longitude"), max_digits=9, decimal_places=6, null=True, blank=True)
    
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
        unique_together = [('user', 'date'), ('employee', 'date')]

    def __str__(self):
        if self.employee_id:
            return f"{self.employee} - {self.date}"
        if self.user_id:
            return f"{self.user.username} - {self.date}"
        return f"Attendance - {self.date}"

    @property
    def duration(self):
        end_punch = self.clock_out
        if end_punch is None and self.lunch_out and not self.lunch_in:
            end_punch = self.lunch_out

        if self.clock_in and end_punch:
            total_seconds = (end_punch - self.clock_in).total_seconds()
            if self.clock_out and self.lunch_out and self.lunch_in and self.lunch_in > self.lunch_out:
                total_seconds -= (self.lunch_in - self.lunch_out).total_seconds()
            if total_seconds <= 0:
                return None
            hours, remainder = divmod(int(total_seconds), 3600)
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


class Timesheet(models.Model):
    employee = models.ForeignKey('hr_personnel.Employee', on_delete=models.CASCADE, related_name='timesheets', verbose_name=_('Employee'), db_constraint=False)
    work_date = models.DateField(_('Work Date'))
    worked_hours = models.DecimalField(_('Worked Hours'), max_digits=6, decimal_places=2, default=0)
    overtime_hours = models.DecimalField(_('Overtime Hours'), max_digits=6, decimal_places=2, default=0)
    late_minutes = models.PositiveIntegerField(_('Late Minutes'), default=0)
    early_leave_minutes = models.PositiveIntegerField(_('Early Leave Minutes'), default=0)
    absence_flag = models.BooleanField(_('Absence Flag'), default=False)
    source_attendance = models.ForeignKey('Attendance', on_delete=models.SET_NULL, null=True, blank=True, related_name='generated_timesheets', db_constraint=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Timesheet')
        verbose_name_plural = _('Timesheets')
        ordering = ['-work_date']
        unique_together = ['employee', 'work_date']

    def __str__(self):
        return f"{self.employee} - {self.work_date}"


class AttendanceAIInsight(models.Model):
    class InsightType(models.TextChoices):
        FRAUD_DETECTION = 'fraud_detection', _('Fraud Detection')
        ABSENCE_PREDICTION = 'absence_prediction', _('Absence Prediction')
        SHIFT_OPTIMIZATION = 'shift_optimization', _('Shift Optimization')
        LATE_PATTERN = 'late_pattern', _('Late Pattern Detection')

    employee = models.ForeignKey('hr_personnel.Employee', on_delete=models.CASCADE, related_name='attendance_ai_insights', db_constraint=False)
    insight_type = models.CharField(_('Insight Type'), max_length=40, choices=InsightType.choices)
    score = models.DecimalField(_('Score'), max_digits=5, decimal_places=2, default=0)
    summary = models.TextField(_('Summary'))
    recommendation = models.TextField(_('Recommendation'), blank=True, null=True)
    generated_at = models.DateTimeField(_('Generated At'), auto_now_add=True)

    class Meta:
        verbose_name = _('Attendance AI Insight')
        verbose_name_plural = _('Attendance AI Insights')
        ordering = ['-generated_at']

    def __str__(self):
        return f"{self.employee} - {self.insight_type}"


class AttendanceChangeLog(models.Model):
    class FieldName(models.TextChoices):
        CLOCK_IN = 'clock_in', _('Clock In')
        LUNCH_OUT = 'lunch_out', _('Lunch Out')
        LUNCH_IN = 'lunch_in', _('Lunch In')
        CLOCK_OUT = 'clock_out', _('Clock Out')

    class ActionType(models.TextChoices):
        SET = 'set', _('Set')
        EDIT = 'edit', _('Edit')
        DELETE = 'delete', _('Delete')

    attendance = models.ForeignKey(
        'Attendance',
        on_delete=models.CASCADE,
        related_name='change_logs',
        verbose_name=_('Attendance'),
    )
    field_name = models.CharField(_('Field'), max_length=20, choices=FieldName.choices)
    action_type = models.CharField(_('Action'), max_length=20, choices=ActionType.choices)
    old_value = models.DateTimeField(_('Old Value'), null=True, blank=True)
    new_value = models.DateTimeField(_('New Value'), null=True, blank=True)
    performed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='attendance_change_logs',
        verbose_name=_('Performed By'),
        db_constraint=False,
    )
    note = models.CharField(_('Note'), max_length=255, blank=True)
    performed_at = models.DateTimeField(_('Performed At'), auto_now_add=True)

    class Meta:
        verbose_name = _('Attendance Change Log')
        verbose_name_plural = _('Attendance Change Logs')
        ordering = ['-performed_at']

    def __str__(self):
        return f"{self.attendance_id}:{self.field_name}:{self.action_type}"
