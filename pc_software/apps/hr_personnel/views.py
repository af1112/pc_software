from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
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


def _tr(request, en_text, fa_text):
    lang = str(getattr(request, 'LANGUAGE_CODE', '')).lower()
    if lang.startswith('fa'):
        return fa_text
    return _(en_text)


def is_supervisor_or_admin(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    try:
        return getattr(user.profile, 'role', 'user') in ['admin', 'supervisor']
    except Exception:
        return False


def _employee_queryset_for_request(request):
    qs = Employee.objects.all()
    org = getattr(request, 'organization', None)
    if org:
        qs = qs.filter(organization=org)
    return qs


@login_required
def employee_me(request):
    try:
        employee = request.user.employee
    except Exception:
        messages.error(request, _tr(request, 'No personnel profile is linked to your account.', 'پروفایل پرسنلی به حساب شما متصل نیست.'))
        return redirect('main_dashboard')

    return redirect('hr_personnel:employee_detail', employee_id=employee.id)


@login_required
def employee_list(request):
    if not is_supervisor_or_admin(request.user):
        return redirect('hr_personnel:employee_me')

    employees = _employee_queryset_for_request(request)
    return render(request, 'hr_personnel/employee_list.html', {'employees': employees, 'is_manager': True})


@login_required
@user_passes_test(is_supervisor_or_admin)
def employee_create(request):
    if request.method == 'POST':
        form = EmployeeForm(request.POST, organization=getattr(request, 'organization', None))
        if form.is_valid():
            employee = form.save(commit=False)
            employee.organization = getattr(request, 'organization', None)
            employee.save()
            messages.success(request, _tr(request, 'Employee created successfully.', 'پرسنل با موفقیت ایجاد شد.'))
            return redirect('hr_personnel:employee_detail', employee_id=employee.id)
    else:
        form = EmployeeForm(organization=getattr(request, 'organization', None))

    return render(request, 'hr_personnel/employee_form.html', {'form': form, 'title': _tr(request, 'Create Employee', 'ایجاد پرسنل')})


@login_required
@user_passes_test(is_supervisor_or_admin)
def employee_edit(request, employee_id):
    employee = get_object_or_404(_employee_queryset_for_request(request), id=employee_id)

    if request.method == 'POST':
        form = EmployeeForm(request.POST, instance=employee, organization=getattr(request, 'organization', None))
        if form.is_valid():
            form.save()
            messages.success(request, _tr(request, 'Employee updated successfully.', 'اطلاعات پرسنل با موفقیت بروزرسانی شد.'))
            return redirect('hr_personnel:employee_detail', employee_id=employee.id)
    else:
        form = EmployeeForm(instance=employee, organization=getattr(request, 'organization', None))

    return render(request, 'hr_personnel/employee_form.html', {'form': form, 'title': _tr(request, 'Edit Employee', 'ویرایش پرسنل')})


@login_required
@user_passes_test(is_supervisor_or_admin)
def employee_delete(request, employee_id):
    employee = get_object_or_404(_employee_queryset_for_request(request), id=employee_id)
    if request.method == 'POST':
        employee.delete()
        messages.success(request, _tr(request, 'Employee deleted successfully.', 'پرسنل با موفقیت حذف شد.'))
        return redirect('hr_personnel:employee_list')

    return render(request, 'hr_personnel/employee_delete.html', {'employee': employee})


@login_required
def employee_detail(request, employee_id):
    employee = get_object_or_404(_employee_queryset_for_request(request), id=employee_id)

    is_manager = is_supervisor_or_admin(request.user)
    if not is_manager and employee.user_id != request.user.id:
        messages.error(request, _tr(request, 'You do not have access to this personnel profile.', 'شما دسترسی مشاهده این پروفایل پرسنلی را ندارید.'))
        return redirect('hr_personnel:employee_me')

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
            'is_manager': is_manager,
        },
    )


@login_required
@user_passes_test(is_supervisor_or_admin)
def salary_profile_create(request, employee_id):
    employee = get_object_or_404(_employee_queryset_for_request(request), id=employee_id)
    user_profile = getattr(request.user, 'profile', None)

    if request.method == 'POST':
        form = SalaryProfileForm(request.POST, user_profile=user_profile)
        if form.is_valid():
            profile = form.save(commit=False)
            profile.employee = employee
            profile.save()
            messages.success(request, _tr(request, 'Salary profile created successfully.', 'پروفایل حقوق با موفقیت ایجاد شد.'))
            return redirect('hr_personnel:employee_detail', employee_id=employee.id)
    else:
        form = SalaryProfileForm(user_profile=user_profile)

    return render(
        request,
        'hr_personnel/salary_profile_form.html',
        {'form': form, 'employee': employee, 'title': _tr(request, 'Create Salary Profile', 'ایجاد پروفایل حقوق')},
    )


@login_required
@user_passes_test(is_supervisor_or_admin)
def salary_component_create(request, employee_id, profile_id):
    employee = get_object_or_404(_employee_queryset_for_request(request), id=employee_id)
    profile = get_object_or_404(SalaryProfile, id=profile_id, employee=employee)

    if request.method == 'POST':
        form = SalaryComponentForm(request.POST)
        if form.is_valid():
            component = form.save(commit=False)
            component.salary_profile = profile
            component.save()
            messages.success(request, _tr(request, 'Salary component added successfully.', 'آیتم حقوقی با موفقیت اضافه شد.'))
            return redirect('hr_personnel:employee_detail', employee_id=employee.id)
    else:
        form = SalaryComponentForm()

    return render(
        request,
        'hr_personnel/salary_component_form.html',
        {'form': form, 'employee': employee, 'profile': profile, 'title': _tr(request, 'Add Salary Component', 'افزودن آیتم حقوقی')},
    )


@login_required
@user_passes_test(is_supervisor_or_admin)
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
            messages.success(request, _tr(request, 'Bank account created successfully.', 'حساب بانکی با موفقیت ایجاد شد.'))
            return redirect('hr_personnel:employee_detail', employee_id=employee.id)
    else:
        form = BankAccountForm()

    return render(
        request,
        'hr_personnel/bank_account_form.html',
        {'form': form, 'employee': employee, 'title': _tr(request, 'Add Bank Account', 'افزودن حساب بانکی')},
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
@user_passes_test(is_supervisor_or_admin)
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

            messages.success(request, _tr(request, 'Payroll slip created successfully.', 'فیش حقوقی با موفقیت ایجاد شد.'))
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
            'title': _tr(request, 'Create Payroll Slip', 'ایجاد فیش حقوقی'),
        },
    )
