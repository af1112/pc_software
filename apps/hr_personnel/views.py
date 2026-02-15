from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from .forms import (
    BankAccountForm,
    EmployeeForm,
    PayrollItemFormSet,
    PayrollSlipForm,
    SalaryComponentForm,
    SalaryProfileForm,
)
from .models import Employee, PayrollSlip, SalaryProfile


def _employee_queryset_for_request(request):
    qs = Employee.objects.all()
    org = getattr(request, 'organization', None)
    if org:
        qs = qs.filter(organization=org)
    return qs


@login_required
def employee_list(request):
    employees = _employee_queryset_for_request(request)
    return render(request, 'hr_personnel/employee_list.html', {'employees': employees})


@login_required
def employee_create(request):
    if request.method == 'POST':
        form = EmployeeForm(request.POST)
        if form.is_valid():
            employee = form.save(commit=False)
            employee.organization = getattr(request, 'organization', None)
            employee.save()
            messages.success(request, _('Employee created successfully.'))
            return redirect('hr_personnel:employee_detail', employee_id=employee.id)
    else:
        form = EmployeeForm()

    return render(request, 'hr_personnel/employee_form.html', {'form': form, 'title': _('Create Employee')})


@login_required
def employee_edit(request, employee_id):
    employee = get_object_or_404(_employee_queryset_for_request(request), id=employee_id)

    if request.method == 'POST':
        form = EmployeeForm(request.POST, instance=employee)
        if form.is_valid():
            form.save()
            messages.success(request, _('Employee updated successfully.'))
            return redirect('hr_personnel:employee_detail', employee_id=employee.id)
    else:
        form = EmployeeForm(instance=employee)

    return render(request, 'hr_personnel/employee_form.html', {'form': form, 'title': _('Edit Employee')})


@login_required
def employee_delete(request, employee_id):
    employee = get_object_or_404(_employee_queryset_for_request(request), id=employee_id)
    if request.method == 'POST':
        employee.delete()
        messages.success(request, _('Employee deleted successfully.'))
        return redirect('hr_personnel:employee_list')

    return render(request, 'hr_personnel/employee_delete.html', {'employee': employee})


@login_required
def employee_detail(request, employee_id):
    employee = get_object_or_404(_employee_queryset_for_request(request), id=employee_id)

    salary_profiles = employee.salary_profiles.prefetch_related('components').all()
    bank_accounts = employee.bank_accounts.all()
    payroll_slips = employee.payroll_slips.prefetch_related('items').all()

    return render(
        request,
        'hr_personnel/employee_detail.html',
        {
            'employee': employee,
            'salary_profiles': salary_profiles,
            'bank_accounts': bank_accounts,
            'payroll_slips': payroll_slips,
        },
    )


@login_required
def salary_profile_create(request, employee_id):
    employee = get_object_or_404(_employee_queryset_for_request(request), id=employee_id)

    if request.method == 'POST':
        form = SalaryProfileForm(request.POST)
        if form.is_valid():
            profile = form.save(commit=False)
            profile.employee = employee
            profile.save()
            messages.success(request, _('Salary profile created successfully.'))
            return redirect('hr_personnel:employee_detail', employee_id=employee.id)
    else:
        form = SalaryProfileForm()

    return render(
        request,
        'hr_personnel/salary_profile_form.html',
        {'form': form, 'employee': employee, 'title': _('Create Salary Profile')},
    )


@login_required
def salary_component_create(request, employee_id, profile_id):
    employee = get_object_or_404(_employee_queryset_for_request(request), id=employee_id)
    profile = get_object_or_404(SalaryProfile, id=profile_id, employee=employee)

    if request.method == 'POST':
        form = SalaryComponentForm(request.POST)
        if form.is_valid():
            component = form.save(commit=False)
            component.salary_profile = profile
            component.save()
            messages.success(request, _('Salary component added successfully.'))
            return redirect('hr_personnel:employee_detail', employee_id=employee.id)
    else:
        form = SalaryComponentForm()

    return render(
        request,
        'hr_personnel/salary_component_form.html',
        {'form': form, 'employee': employee, 'profile': profile, 'title': _('Add Salary Component')},
    )


@login_required
def bank_account_create(request, employee_id):
    employee = get_object_or_404(_employee_queryset_for_request(request), id=employee_id)

    if request.method == 'POST':
        form = BankAccountForm(request.POST)
        if form.is_valid():
            account = form.save(commit=False)
            account.employee = employee
            if account.is_primary:
                employee.bank_accounts.update(is_primary=False)
            account.save()
            messages.success(request, _('Bank account created successfully.'))
            return redirect('hr_personnel:employee_detail', employee_id=employee.id)
    else:
        form = BankAccountForm()

    return render(
        request,
        'hr_personnel/bank_account_form.html',
        {'form': form, 'employee': employee, 'title': _('Add Bank Account')},
    )


def _calculate_payroll_totals(payroll_slip):
    gross = payroll_slip.base_salary
    deductions = 0

    for item in payroll_slip.items.all():
        if item.item_type == 'deduction':
            deductions += item.amount
        else:
            gross += item.amount

    payroll_slip.gross_amount = gross
    payroll_slip.net_amount = gross - deductions


@login_required
def payroll_create(request, employee_id):
    employee = get_object_or_404(_employee_queryset_for_request(request), id=employee_id)

    if request.method == 'POST':
        form = PayrollSlipForm(request.POST, employee=employee)
        payroll = PayrollSlip(employee=employee)
        formset = PayrollItemFormSet(request.POST, instance=payroll)

        if form.is_valid() and formset.is_valid():
            payroll = form.save(commit=False)
            payroll.employee = employee

            if payroll.salary_profile:
                payroll.base_salary = payroll.salary_profile.base_salary
                payroll.currency = payroll.salary_profile.currency
            payroll.save()

            formset.instance = payroll
            formset.save()

            _calculate_payroll_totals(payroll)
            payroll.save()

            messages.success(request, _('Payroll slip created successfully.'))
            return redirect('hr_personnel:employee_detail', employee_id=employee.id)
    else:
        form = PayrollSlipForm(employee=employee)
        payroll = PayrollSlip(employee=employee)
        formset = PayrollItemFormSet(instance=payroll)

    return render(
        request,
        'hr_personnel/payroll_form.html',
        {
            'form': form,
            'formset': formset,
            'employee': employee,
            'title': _('Create Payroll Slip'),
        },
    )
