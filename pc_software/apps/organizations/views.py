from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils.translation import gettext as _
from .forms import OrganizationForm
from .models import Organization


def is_superadmin(user):
    return user.is_superuser


@login_required
@user_passes_test(is_superadmin)
def organization_create(request):
    if request.method == 'POST':
        form = OrganizationForm(request.POST, request.FILES)
        if form.is_valid():
            organization = form.save()
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
            form.save()
            messages.success(request, _('Organization updated successfully.'))
            return redirect('organizations:list')
    else:
        form = OrganizationForm(instance=organization)
    return render(request, 'organizations/organization_form.html', {'form': form, 'organization': organization})
