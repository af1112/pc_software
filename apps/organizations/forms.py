from django import forms
from django.utils.text import slugify
from zoneinfo import available_timezones, ZoneInfo
from .models import Organization

_all = set(available_timezones())
# Ensure Oman appears even if zone DB is minimal on OS
_all.add('Asia/Muscat')
# Build choices, putting Oman and some regional zones at top
_preferred = [
    ('Asia/Muscat', 'Asia/Muscat (Oman, UTC+4)'),
    ('Asia/Dubai', 'Asia/Dubai (UTC+4)') if 'Asia/Dubai' in _all else None,
    ('Asia/Tehran', 'Asia/Tehran (UTC+3:30/UTC+4:30 DST)') if 'Asia/Tehran' in _all else None,
    ('UTC', 'UTC'),
]
_preferred = [p for p in _preferred if p]
_rest = sorted([(tz, tz) for tz in _all if tz not in {k for k, _ in _preferred}])
TIMEZONE_CHOICES = _preferred + _rest


class OrganizationForm(forms.ModelForm):
    MAX_LOGO_SIZE_BYTES = 2 * 1024 * 1024

    class Meta:
        model = Organization
        fields = [
            'name',
            'slug',
            'logo',
            'representative_name',
            'representative_phone',
            'company_email',
            'timezone',
            'is_active',
            'subscription_end_date',
            'can_use_expenses',
            'can_use_ticketing',
            'can_use_attendance',
            'can_use_personnel',
            'can_use_projects',
            'can_use_dms',
            'can_use_ai',
            'can_use_menu',
            'can_use_club',
        ]
        widgets = {
            'subscription_end_date': forms.DateInput(attrs={'type': 'date'}),
            'timezone': forms.Select(choices=TIMEZONE_CHOICES, attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['logo'].help_text = 'Allowed: JPG, JPEG, PNG, WEBP, SVG | Max size: 2MB | Recommended: 240x80 px'
        self.fields['logo'].widget.attrs.update({'accept': '.jpg,.jpeg,.png,.webp,.svg'})

    def clean(self):
        cleaned = super().clean()
        name = cleaned.get('name') or ''
        slug = cleaned.get('slug') or ''
        # Auto-generate slug from name if empty
        if not slug and name:
            base = slugify(name)
            candidate = base or 'org'
            i = 1
            while Organization.objects.filter(slug=candidate).exists():
                i += 1
                candidate = f"{base}-{i}"
            cleaned['slug'] = candidate
            self.cleaned_data['slug'] = candidate
        return cleaned

    def clean_logo(self):
        logo = self.cleaned_data.get('logo')
        if not logo:
            return logo

        filename = (logo.name or '').lower()
        allowed = ('.jpg', '.jpeg', '.png', '.webp', '.svg')
        if not filename.endswith(allowed):
            raise forms.ValidationError('Logo format must be JPG, JPEG, PNG, WEBP, or SVG.')

        if getattr(logo, 'size', 0) > self.MAX_LOGO_SIZE_BYTES:
            raise forms.ValidationError('Logo file size must be less than 2MB.')

        return logo
