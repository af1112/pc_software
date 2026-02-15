from django import forms
from django.contrib.auth import get_user_model

from .models import BankAccount, Employee, PayrollItem, PayrollSlip, SalaryComponent, SalaryProfile


User = get_user_model()


class EmployeeForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)

        if 'user' in self.fields:
            qs = User.objects.all().order_by('username')
            if organization is not None:
                qs = qs.filter(profile__organization=organization)

            # prevent linking a user to multiple employees
            assigned_user_ids = Employee.objects.exclude(user__isnull=True).values_list('user_id', flat=True)
            qs = qs.exclude(id__in=assigned_user_ids)
            if self.instance and self.instance.user_id:
                qs = User.objects.filter(id=self.instance.user_id).union(qs).order_by('username')

            self.fields['user'].queryset = qs
            self.fields['user'].widget.attrs.update({'class': 'form-select'})

    class Meta:
        model = Employee
        fields = [
            'user',
            'first_name',
            'last_name',
            'national_id',
            'phone',
            'email',
            'department',
            'position_title',
            'hire_date',
            'is_active',
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'national_id': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'department': forms.TextInput(attrs={'class': 'form-control'}),
            'position_title': forms.TextInput(attrs={'class': 'form-control'}),
            'hire_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class SalaryProfileForm(forms.ModelForm):
    class Meta:
        model = SalaryProfile
        fields = ['effective_from', 'base_salary', 'currency', 'notes']
        widgets = {
            'effective_from': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'base_salary': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'}),
            'currency': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class SalaryComponentForm(forms.ModelForm):
    class Meta:
        model = SalaryComponent
        fields = ['component_type', 'title', 'is_percentage', 'percentage', 'amount']
        widgets = {
            'component_type': forms.Select(attrs={'class': 'form-select'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'is_percentage': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'percentage': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'}),
        }


class BankAccountForm(forms.ModelForm):
    class Meta:
        model = BankAccount
        fields = ['bank_name', 'account_holder', 'account_number', 'iban', 'is_primary']
        widgets = {
            'bank_name': forms.TextInput(attrs={'class': 'form-control'}),
            'account_holder': forms.TextInput(attrs={'class': 'form-control'}),
            'account_number': forms.TextInput(attrs={'class': 'form-control'}),
            'iban': forms.TextInput(attrs={'class': 'form-control'}),
            'is_primary': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class PayrollSlipForm(forms.ModelForm):
    class Meta:
        model = PayrollSlip
        fields = ['period_year', 'period_month', 'salary_profile', 'bank_account']
        widgets = {
            'period_year': forms.NumberInput(attrs={'class': 'form-control', 'min': 2000, 'max': 2100}),
            'period_month': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 12}),
            'salary_profile': forms.Select(attrs={'class': 'form-select'}),
            'bank_account': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        employee = kwargs.pop('employee', None)
        super().__init__(*args, **kwargs)
        if employee is not None:
            self.fields['salary_profile'].queryset = employee.salary_profiles.all()
            self.fields['bank_account'].queryset = employee.bank_accounts.all()


class PayrollItemForm(forms.ModelForm):
    class Meta:
        model = PayrollItem
        fields = ['item_type', 'title', 'amount']
        widgets = {
            'item_type': forms.Select(attrs={'class': 'form-select'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'}),
        }


PayrollItemFormSet = forms.inlineformset_factory(
    PayrollSlip,
    PayrollItem,
    form=PayrollItemForm,
    extra=3,
    can_delete=True,
)
