from django import forms
from django.contrib.auth import get_user_model
from django.utils.translation import get_language
from django.core.exceptions import ValidationError

from .models import BankAccount, Employee, PayrollItem, PayrollSlip, SalaryComponent, SalaryStructure


User = get_user_model()


class EmployeeForm(forms.ModelForm):
    CURRENCY_CHOICES = [
        ('OMR', 'OMR - Omani Rial'),
        ('USD', 'USD - US Dollar'),
        ('EUR', 'EUR - Euro'),
        ('AED', 'AED - UAE Dirham'),
        ('SAR', 'SAR - Saudi Riyal'),
        ('INR', 'INR - Indian Rupee'),
        ('IRR', 'IRR - Iranian Rial'),
    ]

    def __init__(self, *args, **kwargs):
        organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)

        required_fields = [
            'first_name',
            'last_name',
            'employee_id',
            'employment_type',
            'hire_date',
            'payment_method',
            'currency',
        ]
        for field_name in required_fields:
            if field_name in self.fields:
                self.fields[field_name].required = True

        if 'currency' in self.fields:
            self.fields['currency'].widget = forms.Select(attrs={'class': 'form-select'})

            currency_choices = list(self.CURRENCY_CHOICES)
            existing_codes = {code for code, _ in currency_choices}

            company_default_currency = None
            if organization is not None:
                hrms_company = getattr(organization, 'hrms_company', None)
                company_default_currency = getattr(hrms_company, 'default_currency', None)
                if company_default_currency:
                    company_default_currency = str(company_default_currency).upper()

            profile_currency = None
            if hasattr(self, 'instance') and getattr(self.instance, 'pk', None):
                profile_currency = self.instance.currency

            candidate_defaults = [profile_currency, company_default_currency, 'OMR']
            default_currency = next((str(c).upper() for c in candidate_defaults if c), 'OMR')

            if default_currency not in existing_codes:
                currency_choices.append((default_currency, default_currency))
                existing_codes.add(default_currency)

            self.fields['currency'].choices = currency_choices

            if not self.is_bound and not profile_currency:
                self.initial['currency'] = default_currency

        def _localize_choice_labels(field_name, labels_map):
            if field_name not in self.fields:
                return
            self.fields[field_name].choices = [
                (value, labels_map.get(value, label))
                for value, label in self.fields[field_name].choices
            ]

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
            _localize_choice_labels(
                'gender',
                {
                    'male': 'مرد',
                    'female': 'زن',
                    'other': 'سایر',
                },
            )
            _localize_choice_labels(
                'marital_status',
                {
                    'single': 'مجرد',
                    'married': 'متاهل',
                    'divorced': 'مطلقه',
                    'widowed': 'بیوه',
                },
            )
            _localize_choice_labels(
                'payment_method',
                {
                    'bank_transfer': 'انتقال بانکی',
                    'cash': 'نقدی',
                    'wps': 'سامانه WPS',
                },
            )
            _localize_choice_labels(
                'omani_or_expat',
                {
                    'omani': 'عمانی',
                    'expat': 'مهاجر',
                },
            )
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

    def clean(self):
        cleaned_data = super().clean()
        missing_required = []

        for field_name, field in self.fields.items():
            if not field.required or field_name in self.errors:
                continue

            value = cleaned_data.get(field_name)
            if value in (None, ''):
                missing_required.append(field_name)

        if missing_required:
            if str(get_language() or '').lower().startswith('fa'):
                raise ValidationError('تمامی موارد ستاره‌دار باید تکمیل شوند.')
            raise ValidationError('All fields marked with * are required.')

        return cleaned_data

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
            'currency': forms.Select(attrs={'class': 'form-select'}),
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
            self._fixed_currency = getattr(user_profile, 'currency_code', 'OMR')
            self.fields['currency'].initial = self._fixed_currency
            self.fields['currency'].widget.attrs['readonly'] = 'readonly'

        if str(get_language() or '').lower().startswith('fa'):
            self.fields['effective_from'].label = 'تاریخ اعمال'
            self.fields['effective_to'].label = 'تاریخ پایان'
            self.fields['pay_type'].label = 'نوع پرداخت'
            self.fields['currency'].label = 'واحد پول'
            self.fields['notes'].label = 'یادداشت‌ها'

    def clean(self):
        cleaned_data = super().clean()
        effective_from = cleaned_data.get('effective_from')
        effective_to = cleaned_data.get('effective_to')

        if effective_to and effective_from and effective_to < effective_from:
            raise ValidationError('Effective to cannot be earlier than effective from.')

        return cleaned_data

    def clean_currency(self):
        if self._fixed_currency:
            return self._fixed_currency
        return self.cleaned_data.get('currency')

    class Meta:
        model = SalaryStructure
        fields = [
            'effective_from',
            'effective_to',
            'pay_type',
            'currency',
            'notes',
        ]
        widgets = {
            'effective_from': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'effective_to': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'pay_type': forms.Select(attrs={'class': 'form-select'}),
            'currency': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class SalaryComponentForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if str(get_language() or '').lower().startswith('fa'):
            self.fields['component_type'].label = 'نوع'
            self.fields['title'].label = 'عنوان'
            self.fields['calculation_method'].label = 'روش محاسبه'
            self.fields['amount'].label = 'مبلغ'
            self.fields['is_active'].label = 'فعال'

    def clean(self):
        cleaned_data = super().clean()
        amount = cleaned_data.get('amount')

        if amount is None or amount <= 0:
            raise ValidationError('Amount must be positive.')

        return cleaned_data

    class Meta:
        model = SalaryComponent
        fields = [
            'component_type',
            'title',
            'calculation_method',
            'amount',
            'is_active',
        ]
        widgets = {
            'component_type': forms.Select(attrs={'class': 'form-select'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'calculation_method': forms.Select(attrs={'class': 'form-select'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


SalaryComponentFormSet = forms.inlineformset_factory(
    SalaryStructure,
    SalaryComponent,
    form=SalaryComponentForm,
    extra=1,
    can_delete=True,
)


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
        fields = ['period_year', 'period_month', 'payable_days', 'payable_hours', 'salary_profile', 'bank_account']
        widgets = {
            'period_year': forms.NumberInput(attrs={'class': 'form-control', 'min': 2000, 'max': 2100}),
            'period_month': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 12}),
            'payable_days': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': 0}),
            'payable_hours': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': 0}),
            'salary_profile': forms.Select(attrs={'class': 'form-select'}),
            'bank_account': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        employee = kwargs.pop('employee', None)
        super().__init__(*args, **kwargs)
        if employee is not None:
            self.fields['salary_profile'].queryset = employee.salary_structures.filter(is_active=True)
            self.fields['bank_account'].queryset = employee.bank_accounts.all()

        if str(get_language() or '').lower().startswith('fa'):
            self.fields['period_year'].label = 'سال'
            self.fields['period_month'].label = 'ماه'
            self.fields['payable_days'].label = 'روزهای قابل پرداخت'
            self.fields['payable_hours'].label = 'ساعات قابل پرداخت'
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
