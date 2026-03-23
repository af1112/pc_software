import datetime

from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q

from apps.hrms.models import (
    Employee,
    EmployeeShiftAssignment,
    OvertimePolicy,
    OvertimeRateRule,
    ShiftTemplate,
    ShiftVersion,
    WorkClosure,
    WorkCalendar,
    WorkUnitShiftAssignment,
)


class StyledModelForm(forms.ModelForm):
    def _apply_widgets(self):
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault('class', 'form-check-input')
            elif isinstance(widget, (forms.Select, forms.SelectMultiple, forms.DateInput, forms.DateTimeInput, forms.TimeInput)):
                widget.attrs.setdefault('class', 'form-select' if isinstance(widget, (forms.Select, forms.SelectMultiple)) else 'form-control')
            else:
                widget.attrs.setdefault('class', 'form-control')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_widgets()


class ShiftTemplateForm(StyledModelForm):
    class Meta:
        model = ShiftTemplate
        fields = ['name', 'description']


class ShiftVersionForm(StyledModelForm):
    class Meta:
        model = ShiftVersion
        fields = [
            'shift',
            'valid_from',
            'valid_to',
            'start_time',
            'end_time',
            'break_minutes',
            'required_work_minutes',
            'grace_in_minutes',
            'grace_out_minutes',
            'is_ramadan_shift',
            'is_summer_shift',
            'overtime_after_minutes',
        ]
        widgets = {
            'valid_from': forms.DateInput(attrs={'type': 'date'}),
            'valid_to': forms.DateInput(attrs={'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
        }
        help_texts = {
            'required_work_minutes': 'If left empty, it will be calculated from start/end minus break.',
            'break_minutes': 'Unpaid break minutes inside the shift (example: 75).',
            'overtime_after_minutes': 'Start overtime after this many minutes from shift start. Leave 0 to use required work minutes baseline.',
            'grace_in_minutes': 'Allowed late arrival without late penalty.',
            'grace_out_minutes': 'Allowed early leave without penalty.',
        }

    def __init__(self, *args, **kwargs):
        tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
        self.fields['required_work_minutes'].required = False
        if tenant is not None:
            self.fields['shift'].queryset = ShiftTemplate.objects.filter(tenant=tenant).order_by('name')

    def clean(self):
        cleaned = super().clean()
        start_time = cleaned.get('start_time')
        end_time = cleaned.get('end_time')
        break_minutes = int(cleaned.get('break_minutes') or 0)
        required_minutes = cleaned.get('required_work_minutes')

        if break_minutes < 0:
            raise ValidationError('Break minutes cannot be negative.')

        if start_time and end_time and required_minutes in (None, ''):
            today = datetime.date.today()
            start_dt = datetime.datetime.combine(today, start_time)
            end_dt = datetime.datetime.combine(today, end_time)
            if end_dt <= start_dt:
                end_dt = end_dt + datetime.timedelta(days=1)
            span_minutes = int((end_dt - start_dt).total_seconds() // 60)
            cleaned['required_work_minutes'] = max(span_minutes - break_minutes, 0)

        final_required = int(cleaned.get('required_work_minutes') or 0)
        if final_required <= 0:
            raise ValidationError('Required work minutes must be greater than zero.')

        overtime_after = int(cleaned.get('overtime_after_minutes') or 0)
        if overtime_after < 0:
            raise ValidationError('Overtime after minutes cannot be negative.')

        return cleaned


class EmployeeShiftAssignmentForm(StyledModelForm):
    class Meta:
        model = EmployeeShiftAssignment
        fields = ['employee', 'shift', 'effective_from', 'effective_to', 'is_active']
        widgets = {
            'effective_from': forms.DateInput(attrs={'type': 'date'}),
            'effective_to': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
        if tenant is not None:
            self.fields['employee'].queryset = Employee.objects.filter(tenant=tenant, is_active=True).order_by('first_name', 'last_name')
            self.fields['shift'].queryset = ShiftTemplate.objects.filter(tenant=tenant).order_by('name')


class WorkUnitShiftAssignmentForm(StyledModelForm):
    class Meta:
        model = WorkUnitShiftAssignment
        fields = ['work_unit', 'shift', 'effective_from', 'effective_to', 'is_active']
        widgets = {
            'effective_from': forms.DateInput(attrs={'type': 'date'}),
            'effective_to': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
        if tenant is not None:
            self.fields['shift'].queryset = ShiftTemplate.objects.filter(tenant=tenant).order_by('name')
            org = getattr(tenant, 'organization', None)
            if org is not None:
                from apps.hr_personnel.models import WorkUnit
                self.fields['work_unit'].queryset = WorkUnit.objects.filter(organization=org, is_active=True).order_by('name')
            else:
                self.fields['work_unit'].queryset = self.fields['work_unit'].queryset.none()


class WorkClosureForm(StyledModelForm):
    class Meta:
        model = WorkClosure
        fields = ['title', 'scope', 'work_unit', 'start_date', 'end_date', 'is_paid', 'reason']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'reason': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
        if tenant is not None:
            org = getattr(tenant, 'organization', None)
            if org is not None:
                from apps.hr_personnel.models import WorkUnit
                self.fields['work_unit'].queryset = WorkUnit.objects.filter(organization=org, is_active=True).order_by('name')
            else:
                self.fields['work_unit'].queryset = self.fields['work_unit'].queryset.none()

    def clean(self):
        cleaned = super().clean()
        scope = cleaned.get('scope')
        if scope == WorkClosure.Scope.WORK_UNIT and not cleaned.get('work_unit'):
            raise ValidationError('Please select a work unit for work-unit scope closure.')
        if scope == WorkClosure.Scope.COMPANY:
            cleaned['work_unit'] = None
        return cleaned


class WorkCalendarForm(StyledModelForm):
    class Meta:
        model = WorkCalendar
        fields = ['date', 'day_type', 'holiday_name', 'is_ramadan', 'is_summer_schedule', 'standard_work_minutes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
        }


class WorkCalendarBulkGenerateForm(forms.Form):
    WEEKDAY_CHOICES = [
        ('0', 'Monday'),
        ('1', 'Tuesday'),
        ('2', 'Wednesday'),
        ('3', 'Thursday'),
        ('4', 'Friday'),
        ('5', 'Saturday'),
        ('6', 'Sunday'),
    ]

    year = forms.IntegerField(min_value=2000, max_value=2100)
    default_work_minutes = forms.IntegerField(min_value=1, max_value=1440, initial=480)
    weekend_days = forms.MultipleChoiceField(
        choices=WEEKDAY_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )
    include_public_holidays = forms.BooleanField(required=False, initial=True)
    overwrite_existing = forms.BooleanField(required=False, initial=False)
    custom_weekday_minutes = forms.MultipleChoiceField(
        choices=WEEKDAY_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )
    custom_work_minutes = forms.IntegerField(min_value=1, max_value=1440, required=False)

    def __init__(self, *args, **kwargs):
        country = kwargs.pop('country', None)
        super().__init__(*args, **kwargs)
        if country == 'IR':
            self.fields['weekend_days'].initial = ['4']
        elif country == 'OM':
            self.fields['weekend_days'].initial = ['4', '5']
        else:
            self.fields['weekend_days'].initial = ['5', '6']

        self.fields['year'].widget.attrs.setdefault('class', 'form-control')
        self.fields['default_work_minutes'].widget.attrs.setdefault('class', 'form-control')
        self.fields['weekend_days'].help_text = 'Choose non-working weekdays.'
        self.fields['custom_work_minutes'].widget.attrs.setdefault('class', 'form-control')
        self.fields['custom_weekday_minutes'].help_text = 'Optional: choose weekdays that should use custom work minutes (e.g., half-day Fridays).'

    def clean(self):
        cleaned = super().clean()
        custom_days = cleaned.get('custom_weekday_minutes') or []
        custom_minutes = cleaned.get('custom_work_minutes')
        weekend_days = set(cleaned.get('weekend_days') or [])

        if custom_days and custom_minutes is None:
            raise ValidationError('Please set custom work minutes when selecting custom weekdays.')

        if custom_minutes is not None and not custom_days:
            raise ValidationError('Please select at least one weekday for custom work minutes.')

        overlap_days = weekend_days.intersection(set(custom_days))
        if overlap_days:
            raise ValidationError('A day cannot be both weekend and custom-working at the same time.')

        return cleaned


class OvertimePolicyForm(StyledModelForm):
    class Meta:
        model = OvertimePolicy
        fields = ['name', 'country', 'effective_from', 'effective_to', 'is_active']
        widgets = {
            'effective_from': forms.DateInput(attrs={'type': 'date'}),
            'effective_to': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        effective_from = cleaned.get('effective_from')
        effective_to = cleaned.get('effective_to')
        is_active = bool(cleaned.get('is_active'))
        country = cleaned.get('country')

        if effective_from and effective_to and effective_to < effective_from:
            raise ValidationError('Effective to cannot be earlier than effective from.')

        if self.tenant is not None and is_active and country and effective_from:
            overlap_qs = OvertimePolicy.objects.filter(
                tenant=self.tenant,
                country=country,
                is_active=True,
                effective_from__lte=effective_to or datetime.date.max,
            ).filter(
                Q(effective_to__isnull=True) | Q(effective_to__gte=effective_from)
            )
            if self.instance.pk:
                overlap_qs = overlap_qs.exclude(pk=self.instance.pk)
            if overlap_qs.exists():
                raise ValidationError('Another active overtime policy overlaps with this date range. Please edit the existing one or make this policy inactive.')

        return cleaned


class OvertimeRateRuleForm(StyledModelForm):
    class Meta:
        model = OvertimeRateRule
        fields = ['day_type', 'overtime_type', 'rate_multiplier', 'min_minutes_threshold', 'max_minutes_per_day']
