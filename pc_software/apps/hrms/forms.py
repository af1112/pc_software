from django import forms

from apps.hrms.models import (
    Employee,
    EmployeeShiftAssignment,
    OvertimePolicy,
    OvertimeRateRule,
    ShiftTemplate,
    ShiftVersion,
    WorkCalendar,
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

    def __init__(self, *args, **kwargs):
        tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
        if tenant is not None:
            self.fields['shift'].queryset = ShiftTemplate.objects.filter(tenant=tenant).order_by('name')


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
        required=True,
    )
    include_public_holidays = forms.BooleanField(required=False, initial=True)
    overwrite_existing = forms.BooleanField(required=False, initial=False)

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


class OvertimePolicyForm(StyledModelForm):
    class Meta:
        model = OvertimePolicy
        fields = ['name', 'country', 'effective_from', 'effective_to', 'is_active']
        widgets = {
            'effective_from': forms.DateInput(attrs={'type': 'date'}),
            'effective_to': forms.DateInput(attrs={'type': 'date'}),
        }


class OvertimeRateRuleForm(StyledModelForm):
    class Meta:
        model = OvertimeRateRule
        fields = ['day_type', 'overtime_type', 'rate_multiplier', 'min_minutes_threshold', 'max_minutes_per_day']
