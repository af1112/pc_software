from django import forms
from .models import UserProfile
from django.conf import settings
from django.contrib.auth.models import User, Permission
from django.contrib.contenttypes.models import ContentType

TIMEZONE_CHOICES = [
    ('UTC', 'UTC'),
    ('Asia/Tehran', 'Asia/Tehran'),
    ('Asia/Muscat', 'Asia/Muscat'),
    ('Asia/Dubai', 'Asia/Dubai'),
    ('Europe/London', 'Europe/London'),
    ('Europe/Berlin', 'Europe/Berlin'),
    ('America/New_York', 'America/New_York'),
    ('America/Los_Angeles', 'America/Los_Angeles'),
]


class LanguageSettingsForm(forms.ModelForm):
    preferred_language = forms.ChoiceField(
        choices=settings.LANGUAGES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Preferred Language / زبان ترجیحی'
    )
    
    currency_code = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'OMR'}),
        label='Currency Code (e.g. OMR)'
    )
    
    currency_symbol = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ر.ع.'}),
        label='Currency Symbol (e.g. $)'
    )
    
    currency_decimal_places = forms.IntegerField(
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 4}),
        label='Decimal Places (e.g. 3)'
    )

    timezone = forms.ChoiceField(
        choices=TIMEZONE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Time Zone / منطقه زمانی'
    )

    class Meta:
        model = UserProfile
        fields = ['preferred_language', 'currency_code', 'currency_symbol', 'currency_decimal_places', 'timezone']

class UserCreateForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}), 
        label="Password"
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}), 
        label="Confirm Password"
    )
    preferred_language = forms.ChoiceField(
        choices=settings.LANGUAGES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Default Language",
        initial='en'
    )
    role = forms.ChoiceField(
        choices=UserProfile.ROLE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="User Role",
        initial='user'
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'off'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'off'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'off'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'autocomplete': 'off'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")
        if password != confirm_password:
            raise forms.ValidationError("Passwords do not match")
        return cleaned_data

class UserPermissionsForm(forms.Form):
    # Dynamic list of modules based on your requirement
    CAN_ACCESS_EXPENSES = forms.BooleanField(required=False, label="Access Expense Manager")
    CAN_ACCESS_TICKETING = forms.BooleanField(required=False, label="Access Ticketing System")
    CAN_ACCESS_ATTENDANCE = forms.BooleanField(required=False, label="Access Presence & Attendance")
    CAN_ACCESS_PERSONNEL = forms.BooleanField(required=False, label="Access Personnel & Payroll")
    CAN_ACCESS_PROJECTS = forms.BooleanField(required=False, label="Access Project Control")
    CAN_ACCESS_DMS = forms.BooleanField(required=False, label="Access Document DMS")
    CAN_ACCESS_AI = forms.BooleanField(required=False, label="Access AI Engine")
    CAN_ACCESS_MENU = forms.BooleanField(required=False, label="Access Digital Menu")
    CAN_ACCESS_CLUB = forms.BooleanField(required=False, label="Access Customer Club")
    
    REQUIRE_PHOTO = forms.BooleanField(required=False, label="Require Photo for Attendance")

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            # Get all codenames of permissions assigned directly to this user
            user_perms = set(user.user_permissions.values_list('codename', flat=True))
            for field_name in self.fields:
                if field_name == 'REQUIRE_PHOTO':
                    try:
                        self.initial[field_name] = user.profile.require_photo
                    except:
                        self.initial[field_name] = True
                    continue
                
                perm_codename = field_name.lower()
                if perm_codename in user_perms:
                    self.initial[field_name] = True
