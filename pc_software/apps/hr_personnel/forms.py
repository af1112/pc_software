from django import forms
from django.contrib.auth import get_user_model
from django.utils.translation import get_language

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

        if 'reporting_manager' in self.fields:
            managers = Employee.objects.all().order_by('first_name', 'last_name')
            if organization is not None:
                managers = managers.filter(organization=organization)
            if self.instance and self.instance.pk:
                managers = managers.exclude(pk=self.instance.pk)
            self.fields['reporting_manager'].queryset = managers
            self.fields['reporting_manager'].widget.attrs.update({'class': 'form-select'})

        if str(get_language() or '').lower().startswith('fa'):
            self.fields['user'].label = 'حساب کاربری'
            self.fields['employee_id'].label = 'کد پرسنلی'
            self.fields['company_id'].label = 'کد شرکت'
            self.fields['branch_id'].label = 'کد شعبه'
            self.fields['department_id'].label = 'کد دپارتمان'
            self.fields['position_id'].label = 'کد سمت'
            self.fields['first_name'].label = 'نام'
            self.fields['last_name'].label = 'نام خانوادگی'
            self.fields['national_id'].label = 'کد ملی'
            self.fields['passport_no'].label = 'شماره پاسپورت'
            self.fields['nationality'].label = 'ملیت'
            self.fields['gender'].label = 'جنسیت'
            self.fields['date_of_birth'].label = 'تاریخ تولد'
            self.fields['marital_status'].label = 'وضعیت تاهل'
            self.fields['phone'].label = 'تلفن'
            self.fields['email'].label = 'ایمیل'
            self.fields['department'].label = 'دپارتمان'
            self.fields['position_title'].label = 'عنوان شغلی'
            self.fields['employment_type'].label = 'نوع استخدام'
            self.fields['hire_date'].label = 'تاریخ استخدام'
            self.fields['probation_end_date'].label = 'پایان دوره آزمایشی'
            self.fields['contract_start'].label = 'شروع قرارداد'
            self.fields['contract_end'].label = 'پایان قرارداد'
            self.fields['reporting_manager'].label = 'مدیر مستقیم'
            self.fields['bank_name'].label = 'نام بانک'
            self.fields['iban'].label = 'شماره شبا'
            self.fields['payment_method'].label = 'روش پرداخت'
            self.fields['basic_salary'].label = 'حقوق پایه'
            self.fields['currency'].label = 'واحد پول'
            self.fields['omani_or_expat'].label = 'وضعیت عمانی/مهاجر'
            self.fields['pasi_registered'].label = 'ثبت‌نام در PASI'
            self.fields['wps_required'].label = 'نیازمند WPS'
            self.fields['is_active'].label = 'فعال'

    class Meta:
        model = Employee
        fields = [
            'user',
            'employee_id',
            'company_id',
            'branch_id',
            'department_id',
            'position_id',
            'first_name',
            'last_name',
            'national_id',
            'passport_no',
            'nationality',
            'gender',
            'date_of_birth',
            'marital_status',
            'phone',
            'email',
            'department',
            'position_title',
            'employment_type',
            'hire_date',
            'probation_end_date',
            'contract_start',
            'contract_end',
            'reporting_manager',
            'bank_name',
            'iban',
            'payment_method',
            'basic_salary',
            'currency',
            'omani_or_expat',
            'pasi_registered',
            'wps_required',
            'is_active',
        ]
        widgets = {
            'user': forms.Select(attrs={'class': 'form-select'}),
            'employee_id': forms.TextInput(attrs={'class': 'form-control'}),
            'company_id': forms.TextInput(attrs={'class': 'form-control'}),
            'branch_id': forms.TextInput(attrs={'class': 'form-control'}),
            'department_id': forms.TextInput(attrs={'class': 'form-control'}),
            'position_id': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'national_id': forms.TextInput(attrs={'class': 'form-control'}),
            'passport_no': forms.TextInput(attrs={'class': 'form-control'}),
            'nationality': forms.TextInput(attrs={'class': 'form-control'}),
            'gender': forms.Select(attrs={'class': 'form-select'}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'marital_status': forms.Select(attrs={'class': 'form-select'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'department': forms.TextInput(attrs={'class': 'form-control'}),
            'position_title': forms.TextInput(attrs={'class': 'form-control'}),
            'employment_type': forms.Select(attrs={'class': 'form-select'}),
            'hire_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'probation_end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'contract_start': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'contract_end': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'reporting_manager': forms.Select(attrs={'class': 'form-select'}),
            'bank_name': forms.TextInput(attrs={'class': 'form-control'}),
            'iban': forms.TextInput(attrs={'class': 'form-control'}),
            'payment_method': forms.Select(attrs={'class': 'form-select'}),
            'basic_salary': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'}),
            'currency': forms.TextInput(attrs={'class': 'form-control'}),
            'omani_or_expat': forms.Select(attrs={'class': 'form-select'}),
            'pasi_registered': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'wps_required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class SalaryProfileForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        user_profile = kwargs.pop('user_profile', None)
        super().__init__(*args, **kwargs)
        self._fixed_currency = None

        if user_profile is not None:
            decimal_places = max(int(getattr(user_profile, 'currency_decimal_places', 3) or 0), 0)
            step = '1' if decimal_places == 0 else f"{1 / (10 ** decimal_places):.{decimal_places}f}"
            self.fields['base_salary'].widget.attrs['step'] = step
            self._fixed_currency = getattr(user_profile, 'currency_code', 'OMR')
            self.fields['currency'].initial = self._fixed_currency
            self.fields['currency'].widget.attrs['readonly'] = 'readonly'

        if str(get_language() or '').lower().startswith('fa'):
            self.fields['effective_from'].label = 'تاریخ اعمال'
            self.fields['base_salary'].label = 'حقوق پایه'
            self.fields['currency'].label = 'واحد پول'
            self.fields['notes'].label = 'یادداشت‌ها'

    def clean_currency(self):
        if self._fixed_currency:
            return self._fixed_currency
        return self.cleaned_data.get('currency')

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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if str(get_language() or '').lower().startswith('fa'):
            self.fields['component_type'].label = 'نوع'
            self.fields['title'].label = 'عنوان'
            self.fields['is_percentage'].label = 'درصدی'
            self.fields['percentage'].label = 'درصد'
            self.fields['amount'].label = 'مبلغ'

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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if str(get_language() or '').lower().startswith('fa'):
            self.fields['bank_name'].label = 'نام بانک'
            self.fields['account_holder'].label = 'صاحب حساب'
            self.fields['account_number'].label = 'شماره حساب'
            self.fields['iban'].label = 'شماره شبا'
            self.fields['is_primary'].label = 'حساب اصلی'

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

        if str(get_language() or '').lower().startswith('fa'):
            self.fields['period_year'].label = 'سال'
            self.fields['period_month'].label = 'ماه'
            self.fields['salary_profile'].label = 'پروفایل حقوق'
            self.fields['bank_account'].label = 'حساب بانکی'


class PayrollItemForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if str(get_language() or '').lower().startswith('fa'):
            self.fields['item_type'].label = 'نوع آیتم'
            self.fields['title'].label = 'عنوان'
            self.fields['amount'].label = 'مبلغ'

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
