from django import forms
from django.utils.translation import gettext_lazy as _
from .models import ExpenseItem, ExpenseReport, Trip, Advance, ExpenseCategory

class TripForm(forms.ModelForm):
    class Meta:
        model = Trip
        fields = ['name', 'travel_type', 'business_purpose']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Trip Name')}),
            'travel_type': forms.RadioSelect(attrs={'class': 'form-check-input'}),
            'business_purpose': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': _('Describe the business purpose...')}),
        }

class ExpenseReportForm(forms.ModelForm):
    class Meta:
        model = ExpenseReport
        fields = ['title', 'business_purpose', 'start_date', 'end_date']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Statement Name')}),
            'business_purpose': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': _('Describe the business purpose...')}),
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }

class AdvanceForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user:
            self.fields['trip'].queryset = Trip.objects.filter(created_by=user).order_by('-created_at')
            self.fields['report'].queryset = ExpenseReport.objects.filter(
                submitted_by=user,
                status='draft',
            ).order_by('-created_at')

    class Meta:
        model = Advance
        fields = ['amount', 'date', 'paid_through', 'reference_number', 'notes', 'trip', 'report']
        widgets = {
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001', 'placeholder': '0.000'}),
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'paid_through': forms.Select(attrs={'class': 'form-select'}),
            'reference_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Tap to Enter')}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'trip': forms.Select(attrs={'class': 'form-select'}),
            'report': forms.Select(attrs={'class': 'form-select'}),
        }

class ExpenseItemForm(forms.ModelForm):
    # Field to trigger file input separately if needed, but standard widget works
    receipt_image_trigger = forms.ImageField(required=False, widget=forms.FileInput(attrs={'style': 'display: none;', 'capture': 'environment', 'accept': 'image/*'}))

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super(ExpenseItemForm, self).__init__(*args, **kwargs)
        
        # Rename Report to Statement
        self.fields['report'].label = _("Statement")
        self.fields['report'].widget.attrs.update({'class': 'form-select'})
        
        # Custom label for the dropdown options
        # Format: Statement Name (Start - End) | Ref: #... | Total: ...
        self.fields['report'].label_from_instance = lambda obj: (
            f"{obj.title} "
            f"({obj.start_date.strftime('%Y-%m-%d') if obj.start_date else '?'}-{obj.end_date.strftime('%Y-%m-%d') if obj.end_date else '?'}) | "
            f"{_('Ref')}: {str(obj.id)[:6].upper()} | "
            f"{_('Total')}: {float(obj.total_amount):.3f} {obj.currency}"
        )

        if user:
            # Filter for open statements (draft) for this user
            self.fields['report'].queryset = ExpenseReport.objects.filter(
                submitted_by=user, 
                status='draft'
            ).order_by('-created_at')

            categories = ExpenseCategory.objects.filter(created_by=user, is_active=True).order_by('name')
            self.fields['category'].widget = forms.Select(
                choices=[('', _('Select category'))] + [(c.name, c.name) for c in categories],
                attrs={'class': 'form-select'},
            )

            merchant_suggestions = ExpenseItem.objects.filter(created_by=user).exclude(
                merchant__isnull=True,
            ).exclude(merchant__exact='').values_list('merchant', flat=True).distinct().order_by('merchant')
            self.merchant_suggestions = list(merchant_suggestions[:30])

            # Set currency and decimal places based on user profile
            if hasattr(user, 'profile'):
                currency_code = user.profile.currency_code
                decimal_places = user.profile.currency_decimal_places

                # Update Amount field widget step
                step_value = '0.' + '0' * (decimal_places - 1) + '1'
                self.fields['amount'].widget.attrs.update({
                    'step': step_value,
                    'placeholder': '0.' + '0' * decimal_places
                })

                # Update Currency field initial value
                self.fields['currency'].initial = currency_code
                self.fields['currency'].widget.attrs.update({'value': currency_code})
        else:
            self.merchant_suggestions = []

    class Meta:
        model = ExpenseItem
        fields = [
            'report', 'date', 'merchant', 'category', 'amount', 'currency', 
            'description', 'claim_reimbursement', 'payment_mode', 'reference_number', 'receipt_image'
        ]
        widgets = {
            'report': forms.Select(attrs={'class': 'form-select'}),
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'merchant': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Tap to select'), 'list': 'merchant-list'}),
            'category': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Tap to select')}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001', 'placeholder': '0.000'}),
            'currency': forms.HiddenInput(),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': _('Description')}),
            'payment_mode': forms.Select(attrs={'class': 'form-select'}),
            'reference_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Tap to Enter')}),
            'receipt_image': forms.ClearableFileInput(attrs={'class': 'd-none', 'accept': 'image/*'}),
            'claim_reimbursement': forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
        }


class ExpenseCategoryForm(forms.ModelForm):
    class Meta:
        model = ExpenseCategory
        fields = ['name', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Category name')}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
