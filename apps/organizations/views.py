from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils.translation import gettext as _
from apps.hrms.models import Company
from .forms import OrganizationForm
from .models import Organization


def is_superadmin(user):
    return user.is_superuser


def _default_country_for_org(organization):
    tz = (organization.timezone or '').lower()
    if 'tehran' in tz or tz.endswith('/iran'):
        return Company.Country.IRAN
    return Company.Country.OMAN


def _ensure_hrms_company(organization):
    country = _default_country_for_org(organization)
    Company.objects.get_or_create(
        organization=organization,
        defaults={
            'name': organization.name,
            'country': country,
            'timezone': organization.timezone or 'UTC',
            'default_currency': 'IRR' if country == Company.Country.IRAN else 'OMR',
            'wps_enabled': country == Company.Country.OMAN,
        },
    )


@login_required
@user_passes_test(is_superadmin)
def organization_create(request):
    if request.method == 'POST':
        form = OrganizationForm(request.POST, request.FILES)
        if form.is_valid():
            organization = form.save()
            _ensure_hrms_company(organization)
            try:
                settings_key = f'user_settings_{request.user.id}'
                if settings_key in request.session:
                    del request.session[settings_key]
            except Exception:
                pass
            messages.success(request, _('Organization created successfully.'))
            return redirect('main_dashboard')
    else:
        form = OrganizationForm()

    return render(request, 'organizations/organization_form.html', {'form': form})

@login_required
@user_passes_test(is_superadmin)
def organization_list(request):
    organizations = Organization.objects.order_by('-created_at')
    return render(request, 'organizations/organization_list.html', {'organizations': organizations})

@login_required
@user_passes_test(is_superadmin)
def organization_edit(request, pk):
    organization = Organization.objects.get(pk=pk)
    if request.method == 'POST':
        form = OrganizationForm(request.POST, request.FILES, instance=organization)
        if form.is_valid():
            updated_org = form.save()
            _ensure_hrms_company(updated_org)
            try:
                profile = getattr(request.user, 'profile', None)
                if profile and profile.organization_id == updated_org.id:
                    settings_key = f'user_settings_{request.user.id}'
                    if settings_key in request.session:
                        del request.session[settings_key]
            except Exception:
                pass
            messages.success(request, _('Organization updated successfully.'))
            return redirect('organizations:list')
    else:
        form = OrganizationForm(instance=organization)
    return render(request, 'organizations/organization_form.html', {'form': form, 'organization': organization})
