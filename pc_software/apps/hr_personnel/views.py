from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from datetime import date
from calendar import monthrange
from decimal import Decimal
import json

from .forms import (
    BankAccountForm,
    EmployeeForm,
    PayrollItemFormSet,
    PayrollSlipForm,
    SalaryComponentForm,
    SalaryComponentFormSet,
    SalaryProfileForm,
)
from .models import Employee, PayrollItem, PayrollSlip, SalaryComponent, SalaryStructure
from .services import PayrollCalculator


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
def personnel_hub(request):
    is_manager = is_supervisor_or_admin(request.user)
    employee = None
    if not is_manager:
        try:
            employee = request.user.employee
        except Exception:
            employee = None

    return render(
        request,
        'hr_personnel/personnel_hub.html',
        {
            'title': _tr(request, 'Personnel & Payroll', 'پرسنل و حقوق و دستمزد'),
            'is_manager': is_manager,
            'employee': employee,
        },
    )


@login_required
@user_passes_test(is_supervisor_or_admin)
def compensation_hub(request):
    employees = _employee_queryset_for_request(request)
    return render(
        request,
        'hr_personnel/compensation_hub.html',
        {
            'title': _tr(request, 'Salary, Bank & Payroll', 'حقوق، بانک و فیش حقوقی'),
            'employees': employees,
        },
    )


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
        messages.error(request, _tr(request, 'Please complete all required fields marked with *.', 'تمامی موارد ستاره‌دار باید تکمیل شوند.'))
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
        messages.error(request, _tr(request, 'Please complete all required fields marked with *.', 'تمامی موارد ستاره‌دار باید تکمیل شوند.'))
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

    salary_profiles = employee.salary_structures.prefetch_related('components').all()
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
        temp_structure = SalaryStructure(employee=employee)
        formset = SalaryComponentFormSet(request.POST, instance=temp_structure)

        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    profile = form.save(commit=False)
                    profile.employee = employee
                    profile.save()

                    formset.instance = profile
                    formset.save()

                    PayrollCalculator.validate_structure_components(profile)
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                messages.success(request, _tr(request, 'Salary structure created successfully.', 'ساختار حقوق با موفقیت ایجاد شد.'))
                return redirect('hr_personnel:employee_detail', employee_id=employee.id)
    else:
        form = SalaryProfileForm(user_profile=user_profile)
        temp_structure = SalaryStructure(employee=employee)
        formset = SalaryComponentFormSet(instance=temp_structure)

    return render(
        request,
        'hr_personnel/salary_profile_form.html',
        {
            'form': form,
            'formset': formset,
            'employee': employee,
            'title': _tr(request, 'Create Salary Structure', 'ایجاد ساختار حقوق'),
        },
    )


@login_required
@user_passes_test(is_supervisor_or_admin)
def salary_component_create(request, employee_id, profile_id):
    employee = get_object_or_404(_employee_queryset_for_request(request), id=employee_id)
    profile = get_object_or_404(SalaryStructure, id=profile_id, employee=employee)

    if request.method == 'POST':
        form = SalaryComponentForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    component = form.save(commit=False)
                    component.salary_structure = profile
                    component.save()
                    PayrollCalculator.validate_structure_components(profile)
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                messages.success(request, _tr(request, 'Salary component added successfully.', 'مولفه حقوقی با موفقیت اضافه شد.'))
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
    gross = Decimal(str(payroll_slip.base_salary or 0))
    deductions = Decimal('0.000')
    total_earnings = Decimal('0.000')

    for item in payroll_slip.items.all():
        if item.item_type == 'deduction':
            deductions += item.amount
        else:
            total_earnings += item.amount
            gross += item.amount

    payroll_slip.total_allowances = total_earnings
    payroll_slip.total_benefits = Decimal('0.000')
    payroll_slip.total_deductions = deductions
    payroll_slip.gross_amount = gross
    payroll_slip.net_amount = gross - deductions


def _apply_salary_profile_components(payroll_slip):
    profile = payroll_slip.salary_profile
    if not profile:
        return

    existing_items = {
        (item.item_type, item.title.strip().lower())
        for item in payroll_slip.items.all()
    }

    components = profile.components.filter(is_active=True)
    for component in components:
        item_key = (component.component_type, component.title.strip().lower())
        if item_key in existing_items:
            continue

        amount = component.calculate_amount(
            payable_days=payroll_slip.payable_days,
            payable_hours=payroll_slip.payable_hours,
        )

        if amount == Decimal('0.000'):
            continue

        PayrollItem.objects.create(
            payroll_slip=payroll_slip,
            item_type=component.component_type,
            title=component.title,
            amount=amount,
        )
        existing_items.add(item_key)


def _period_range(year, month):
    start = date(int(year), int(month), 1)
    end = date(int(year), int(month), monthrange(int(year), int(month))[1])
    return start, end


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
                period_start, period_end = _period_range(payroll.period_year, payroll.period_month)
                calc = PayrollCalculator.calculate(
                    employee=employee,
                    period_start=period_start,
                    period_end=period_end,
                    worked_days=payroll.payable_days,
                    worked_hours=payroll.payable_hours,
                    overtime_hours=Decimal('0.00'),
                )
                payroll.base_salary = calc['base_pay']
                payroll.currency = calc['salary_structure'].currency
            payroll.save()

            formset.instance = payroll
            formset.save()
            _apply_salary_profile_components(payroll)

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


@login_required
@user_passes_test(is_supervisor_or_admin)
def salary_structure_api_create(request):
    if request.method != 'POST':
        return JsonResponse({'detail': 'Method not allowed.'}, status=405)

    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'detail': 'Invalid JSON payload.'}, status=400)

    employee_id = payload.get('employee_id')
    employee = get_object_or_404(_employee_queryset_for_request(request), id=employee_id)
    components_payload = payload.get('components') or []

    form = SalaryProfileForm(payload, user_profile=getattr(request.user, 'profile', None))
    if not form.is_valid():
        return JsonResponse({'errors': {'structure': form.errors}}, status=400)

    if not isinstance(components_payload, list) or not components_payload:
        return JsonResponse({'errors': {'components': ['At least one component is required.']}}, status=400)

    component_errors = []
    for index, component_data in enumerate(components_payload):
        component_form = SalaryComponentForm(component_data)
        if not component_form.is_valid():
            component_errors.append({'index': index, 'errors': component_form.errors})

    if component_errors:
        return JsonResponse({'errors': {'components': component_errors}}, status=400)

    try:
        with transaction.atomic():
            structure = form.save(commit=False)
            structure.employee = employee
            structure.save()

            for component_data in components_payload:
                component_form = SalaryComponentForm(component_data)
                component = component_form.save(commit=False)
                component.salary_structure = structure
                component.save()

            PayrollCalculator.validate_structure_components(structure)
    except ValidationError as exc:
        return JsonResponse({'errors': {'non_field_errors': exc.messages}}, status=400)

    return JsonResponse({'id': str(structure.id), 'message': 'Salary structure created successfully.'}, status=201)


@login_required
def salary_structure_api_get(request, employee_id):
    employee = get_object_or_404(_employee_queryset_for_request(request), id=employee_id)
    is_manager = is_supervisor_or_admin(request.user)
    if not is_manager and employee.user_id != request.user.id:
        return JsonResponse({'detail': 'Forbidden.'}, status=403)

    structures = employee.salary_structures.prefetch_related('components').order_by('-effective_from')
    data = []
    for structure in structures:
        data.append(
            {
                'id': str(structure.id),
                'pay_type': structure.pay_type,
                'effective_from': structure.effective_from.isoformat(),
                'effective_to': structure.effective_to.isoformat() if structure.effective_to else None,
                'currency': structure.currency,
                'is_active': structure.is_active,
                'components': [
                    {
                        'id': str(component.id),
                        'title': component.title,
                        'component_type': component.component_type,
                        'calculation_method': component.calculation_method,
                        'amount': str(component.amount),
                        'is_active': component.is_active,
                    }
                    for component in structure.components.filter(is_active=True)
                ],
            }
        )
    return JsonResponse({'employee_id': str(employee.id), 'items': data})


@login_required
@user_passes_test(is_supervisor_or_admin)
def salary_component_api_create(request):
    if request.method != 'POST':
        return JsonResponse({'detail': 'Method not allowed.'}, status=405)

    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'detail': 'Invalid JSON payload.'}, status=400)

    structure_id = payload.get('salary_structure_id')
    structure = get_object_or_404(
        SalaryStructure,
        id=structure_id,
        employee__in=_employee_queryset_for_request(request),
    )

    form = SalaryComponentForm(payload)
    if not form.is_valid():
        return JsonResponse({'errors': form.errors}, status=400)

    try:
        with transaction.atomic():
            component = form.save(commit=False)
            component.salary_structure = structure
            component.save()
            PayrollCalculator.validate_structure_components(structure)
    except ValidationError as exc:
        return JsonResponse({'errors': {'non_field_errors': exc.messages}}, status=400)

    return JsonResponse({'id': str(component.id), 'message': 'Salary component created successfully.'}, status=201)


@login_required
@user_passes_test(is_supervisor_or_admin)
def salary_component_api_delete(request, component_id):
    if request.method != 'DELETE':
        return JsonResponse({'detail': 'Method not allowed.'}, status=405)

    component = get_object_or_404(
        SalaryComponent,
        id=component_id,
        salary_structure__employee__in=_employee_queryset_for_request(request),
    )
    structure = component.salary_structure
    try:
        with transaction.atomic():
            component.delete()
            PayrollCalculator.validate_structure_components(structure)
    except ValidationError as exc:
        return JsonResponse({'errors': {'non_field_errors': exc.messages}}, status=400)

    return JsonResponse({'message': 'Salary component deleted successfully.'}, status=200)
