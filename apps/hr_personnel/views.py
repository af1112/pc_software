from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import ValidationError
from django.db import transaction, OperationalError, ProgrammingError
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from datetime import date, datetime, time as time_cls, timedelta
from calendar import monthrange
from decimal import Decimal
from django.utils import timezone
import json

from .forms import (
    LaborSupplyCompanyForm,
    BankAccountForm,
    EmployeeForm,
    PayrollItemFormSet,
    PayrollPeriodForm,
    PayrollSlipForm,
    SalaryComponentForm,
    SalaryComponentFormSet,
    SalaryProfileForm,
    WorkUnitForm,
)
from .models import Employee, LaborSupplyCompany, LeavePolicy, LeaveRequest, PayrollItem, PayrollPeriod, PayrollRun, PayrollSlip, SalaryComponent, SalaryStructure, WorkUnit
from .services import (
    PayrollCalculator,
    PayrollProcessingService,
    render_bank_payroll_csv_response,
    render_payslip_pdf_response,
    render_payroll_summary_pdf_response,
)


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


def _employee_queryset_for_request(request, apply_supervisor_scope=False):
    qs = Employee.objects.all()
    org = getattr(request, 'organization', None)
    if org:
        qs = qs.filter(organization=org)

    if apply_supervisor_scope and not request.user.is_superuser:
        try:
            role = getattr(request.user.profile, 'role', 'user')
        except Exception:
            role = 'user'

        if role == 'supervisor':
            try:
                current_employee = getattr(request.user, 'employee', None)
            except Exception:
                current_employee = None

            scope = (
                (Q(user__isnull=False) & Q(user__profile__supervisor=request.user))
                | (Q(user__isnull=True) & Q(supervisor=request.user))
            )
            if current_employee is not None:
                scope |= Q(reporting_manager=current_employee)
                scope |= Q(work_unit__supervisor=current_employee)
            qs = qs.filter(scope).distinct()

    return qs


def _safe_reverse(name, **kwargs):
    try:
        return reverse(name, kwargs=kwargs or None)
    except Exception:
        return '#'


def _payroll_tab_url(tab_name):
    return f"{reverse('hr_personnel:payroll_hub')}?tab={tab_name}"


def _payroll_current_period_context(request):
    context = {
        'current_period': None,
        'current_period_badge': _('Not Implemented'),
        'current_period_badge_class': 'bg-secondary',
    }
    try:
        today = date.today()
        qs = PayrollPeriod.objects.all()
        org = getattr(request, 'organization', None)
        if org is not None:
            qs = qs.filter(organization=org)
        current_period = qs.filter(start_date__lte=today, end_date__gte=today).order_by('-start_date').first()
        if current_period is None:
            current_period = qs.order_by('-start_date').first()
        if current_period is None:
            return context

        context['current_period'] = current_period
        if current_period.status == PayrollPeriod.Status.FINALIZED:
            context['current_period_badge'] = _('Locked')
            context['current_period_badge_class'] = 'bg-danger'
        elif current_period.status == PayrollPeriod.Status.REVIEW:
            context['current_period_badge'] = _('In Review')
            context['current_period_badge_class'] = 'bg-warning text-dark'
        else:
            context['current_period_badge'] = _('Active')
            context['current_period_badge_class'] = 'bg-success'
        return context
    except (OperationalError, ProgrammingError, Exception):
        return context


def _payroll_open_period_for_request(request):
    try:
        qs = PayrollPeriod.objects.filter(status=PayrollPeriod.Status.OPEN)
        org = getattr(request, 'organization', None)
        if org is not None:
            qs = qs.filter(organization=org)
        return qs.order_by('-start_date').first()
    except (OperationalError, ProgrammingError, Exception):
        return None


def _payroll_nav_sections(request, is_manager):
    placeholder = lambda section, module: _safe_reverse(
        'hr_personnel:payroll_module_placeholder', section=section, module=module
    )

    if not is_manager:
        return {
            'setup': [],
            'compensation': [],
            'processing': [],
            'reports': [
                {
                    'group': _('Operational'),
                    'items': [
                        {
                            'key': 'my-payslip',
                            'title': _('My Payslip'),
                            'url': _safe_reverse('hr_personnel:employee_me'),
                            'implemented': True,
                            'status': _('Active'),
                            'status_class': 'bg-success',
                        },
                    ],
                },
            ],
        }

    return {
        'setup': [
            {
                'key': 'salary-components',
                'title': _('Salary Components (Wage Types)'),
                'url': _payroll_tab_url('compensation'),
                'status': _('Active'),
                'status_class': 'bg-success',
                'implemented': True,
            },
            {
                'key': 'overtime-policies',
                'title': _('Overtime Policies'),
                'url': _safe_reverse('hrms:overtime_policy_list'),
                'status': _('Active'),
                'status_class': 'bg-success',
                'implemented': True,
            },
            {
                'key': 'salary-grades',
                'title': _('Salary Grades'),
                'url': placeholder('setup', 'salary-grades'),
                'status': _('Not Implemented'),
                'status_class': 'bg-secondary',
                'implemented': False,
            },
            {
                'key': 'payroll-settings',
                'title': _('Payroll Settings'),
                'url': placeholder('setup', 'payroll-settings'),
                'status': _('Not Implemented'),
                'status_class': 'bg-secondary',
                'implemented': False,
            },
            {
                'key': 'cost-centers',
                'title': _('Cost Centers'),
                'url': placeholder('setup', 'cost-centers'),
                'status': _('Not Implemented'),
                'status_class': 'bg-secondary',
                'implemented': False,
            },
            {
                'key': 'labor-supply-companies',
                'title': _('Labor Supply Companies'),
                'url': _safe_reverse('hr_personnel:labor_supply_company_manage'),
                'status': _('Active'),
                'status_class': 'bg-success',
                'implemented': True,
            },
            {
                'key': 'work-units',
                'title': _('Work Units'),
                'url': _safe_reverse('hr_personnel:work_unit_manage'),
                'status': _('Active'),
                'status_class': 'bg-success',
                'implemented': True,
            },
            {
                'key': 'eosb-settings',
                'title': _('EOSB Settings'),
                'url': placeholder('setup', 'eosb-settings'),
                'status': _('Not Implemented'),
                'status_class': 'bg-secondary',
                'implemented': False,
            },
        ],
        'compensation': [
            {
                'key': 'salary-structures',
                'title': _('Salary Structures'),
                'url': _payroll_tab_url('compensation'),
                'status': _('Active'),
                'status_class': 'bg-success',
                'implemented': True,
            },
            {
                'key': 'allowances-deductions',
                'title': _('Allowances & Deductions'),
                'url': _payroll_tab_url('compensation'),
                'status': _('Active'),
                'status_class': 'bg-success',
                'implemented': True,
            },
            {
                'key': 'one-time-adjustments',
                'title': _('One-Time Adjustments'),
                'url': placeholder('compensation', 'one-time-adjustments'),
                'status': _('Not Implemented'),
                'status_class': 'bg-secondary',
                'implemented': False,
            },
            {
                'key': 'salary-history',
                'title': _('Salary History'),
                'url': _safe_reverse('hr_personnel:employee_list'),
                'status': _('Active'),
                'status_class': 'bg-success',
                'implemented': True,
            },
        ],
        'processing': [
            {
                'key': 'payroll-periods',
                'title': _('Payroll Periods'),
                'url': _safe_reverse('hr_personnel:payroll_periods'),
                'status': _('Active'),
                'status_class': 'bg-success',
                'implemented': True,
            },
            {
                'key': 'run-payroll',
                'title': _('Run Payroll'),
                'url': _safe_reverse('hr_personnel:payroll_periods'),
                'status': _('Active'),
                'status_class': 'bg-success',
                'implemented': True,
            },
            {
                'key': 'generate-slips',
                'title': _('Generate Slips'),
                'url': _safe_reverse('hr_personnel:payroll_periods'),
                'status': _('Active'),
                'status_class': 'bg-success',
                'implemented': True,
            },
            {
                'key': 'review-payroll',
                'title': _('Review Payroll'),
                'url': _safe_reverse('hr_personnel:employee_list'),
                'status': _('Active'),
                'status_class': 'bg-success',
                'implemented': True,
            },
            {
                'key': 'lock-finalize',
                'title': _('Lock / Finalize Payroll'),
                'url': _safe_reverse('hr_personnel:payroll_periods'),
                'status': _('Active'),
                'status_class': 'bg-success',
                'implemented': True,
            },
        ],
        'reports': [
            {
                'group': _('Operational'),
                'items': [
                    {'key': 'payslip', 'title': _('Payslip'), 'url': _safe_reverse('hr_personnel:payroll_summary_report'), 'implemented': True, 'status': _('Active'), 'status_class': 'bg-success'},
                    {'key': 'payroll-summary', 'title': _('Payroll Summary'), 'url': _safe_reverse('hr_personnel:payroll_summary_report'), 'implemented': True, 'status': _('Active'), 'status_class': 'bg-success'},
                    {'key': 'bank-transfer-sheet', 'title': _('Bank Transfer Sheet'), 'url': f"{_safe_reverse('hr_personnel:payroll_summary_report')}?bank_export=bank_muscat", 'implemented': True, 'status': _('Active'), 'status_class': 'bg-success'},
                ],
            },
            {
                'group': _('Analytical'),
                'items': [
                    {'key': 'salary-breakdown', 'title': _('Salary Breakdown'), 'url': _safe_reverse('hr_personnel:payroll_summary_report'), 'implemented': True, 'status': _('Active'), 'status_class': 'bg-success'},
                    {'key': 'cost-by-department', 'title': _('Cost by Department'), 'url': _safe_reverse('hr_personnel:payroll_summary_report'), 'implemented': True, 'status': _('Active'), 'status_class': 'bg-success'},
                    {'key': 'overtime-report', 'title': _('Overtime Report'), 'url': f"{_safe_reverse('hr_personnel:payroll_summary_report')}?report_type=overtime", 'implemented': True, 'status': _('Active'), 'status_class': 'bg-success'},
                    {'key': 'deduction-analysis', 'title': _('Deduction Analysis'), 'url': f"{_safe_reverse('hr_personnel:payroll_summary_report')}?report_type=deduction", 'implemented': True, 'status': _('Active'), 'status_class': 'bg-success'},
                ],
            },
            {
                'group': _('Compliance'),
                'items': [
                    {'key': 'eosb-report', 'title': _('EOSB Report'), 'url': placeholder('reports', 'eosb-report'), 'implemented': False, 'status': _('Not Implemented'), 'status_class': 'bg-secondary'},
                    {'key': 'insurance-report', 'title': _('Insurance Report'), 'url': placeholder('reports', 'insurance-report'), 'implemented': False, 'status': _('Not Implemented'), 'status_class': 'bg-secondary'},
                    {'key': 'tax-report', 'title': _('Tax Report'), 'url': placeholder('reports', 'tax-report'), 'implemented': False, 'status': _('Not Implemented'), 'status_class': 'bg-secondary'},
                ],
            },
        ],
    }


@login_required
def payroll_hub(request):
    is_manager = is_supervisor_or_admin(request.user)
    active_tab = str(request.GET.get('tab') or 'setup').strip().lower()
    if active_tab not in {'setup', 'compensation', 'processing', 'reports'}:
        active_tab = 'setup'

    if not is_manager and active_tab != 'reports':
        return redirect(_payroll_tab_url('reports'))

    employees_for_compensation = []
    compensation_rows = []
    latest_salary_structure_by_employee = {}
    compensation_schema_error = False
    if is_manager and active_tab == 'compensation':
        employees_for_compensation = list(_employee_queryset_for_request(request))
        try:
            employee_ids = [employee.id for employee in employees_for_compensation]
            structure_pairs = SalaryStructure.objects.filter(
                employee_id__in=employee_ids
            ).order_by('employee_id', '-effective_from').values_list('employee_id', 'id')
            for employee_id, structure_id in structure_pairs:
                latest_salary_structure_by_employee.setdefault(str(employee_id), str(structure_id))
        except (OperationalError, ProgrammingError, Exception):
            compensation_schema_error = True
            messages.warning(
                request,
                _tr(
                    request,
                    'Salary structure schema is not fully migrated yet. Please run hr_personnel migrations.',
                    'ساختار دیتابیس حقوق هنوز کامل مهاجرت نشده است. لطفاً مایگریشن‌های hr_personnel را اجرا کنید.',
                ),
            )
        compensation_rows = [
            {
                'employee': employee,
                'latest_structure_id': latest_salary_structure_by_employee.get(str(employee.id)),
            }
            for employee in employees_for_compensation
        ]

    context = {
        'title': _tr(request, 'Payroll Flow', 'جریان کاری حقوق و دستمزد'),
        'active_tab': active_tab,
        'sections': _payroll_nav_sections(request, is_manager),
        'employees_for_compensation': employees_for_compensation,
        'compensation_rows': compensation_rows,
        'latest_salary_structure_by_employee': latest_salary_structure_by_employee,
        'compensation_schema_error': compensation_schema_error,
        'is_manager': is_manager,
        **_payroll_current_period_context(request),
    }
    return render(request, 'hr_personnel/payroll_hub.html', context)


@login_required
@user_passes_test(is_supervisor_or_admin)
def payroll_periods(request):
    rows = []
    payroll_schema_error = False
    organization = getattr(request, 'organization', None)
    employees_for_run = []
    supply_companies = []
    try:
        rows_qs = PayrollPeriod.objects.all()
        if organization is not None:
            rows_qs = rows_qs.filter(organization=organization)
        rows = list(rows_qs.order_by('-start_date', '-created_at')[:36])
        employees_for_run = list(
            _employee_queryset_for_request(request)
            .filter(is_active=True)
            .order_by('first_name', 'last_name')
        )
        supply_companies = list(
            LaborSupplyCompany.objects.filter(is_active=True, organization=organization).order_by('name')
            if organization is not None
            else LaborSupplyCompany.objects.filter(is_active=True).order_by('name')
        )
    except (OperationalError, ProgrammingError, Exception):
        payroll_schema_error = True
        messages.error(
            request,
            _tr(
                request,
                'Payroll period table is not ready yet. Please run hr_personnel migrations.',
                'جدول دوره حقوق آماده نیست. لطفاً مایگریشن‌های hr_personnel را اجرا کنید.',
            ),
        )

    if request.method == 'POST' and not payroll_schema_error:
        form = PayrollPeriodForm(request.POST)
        if form.is_valid():
            period = form.save(commit=False)
            period.organization = organization
            period.status = PayrollPeriod.Status.OPEN
            try:
                period.save()
            except ValidationError as exc:
                form.add_error(None, exc)
                form.add_error(
                    None,
                    _tr(
                        request,
                        'If an existing period is wrong, invalidate that period first, then create and rerun this date range again.',
                        'اگر دوره قبلی اشتباه است، ابتدا همان دوره را باطل کنید و سپس همین بازه را دوباره ایجاد و پردازش کنید.',
                    ),
                )
            else:
                messages.success(request, _tr(request, 'Payroll period created.', 'دوره حقوق و دستمزد ایجاد شد.'))
                return redirect('hr_personnel:payroll_periods')
    else:
        form = PayrollPeriodForm()

    return render(
        request,
        'hr_personnel/payroll_periods.html',
        {
            'title': _tr(request, 'Payroll Periods', 'دوره‌های حقوق و دستمزد'),
            'rows': rows,
            'form': form,
            'employees_for_run': employees_for_run,
            'supply_companies': supply_companies,
            'payroll_schema_error': payroll_schema_error,
            **_payroll_current_period_context(request),
        },
    )


@login_required
@user_passes_test(is_supervisor_or_admin)
def payroll_run_period(request, period_id):
    if request.method != 'POST':
        return redirect('hr_personnel:payroll_periods')

    try:
        period = get_object_or_404(PayrollPeriod, id=period_id)
    except (OperationalError, ProgrammingError, Exception):
        messages.error(request, _tr(request, 'Payroll schema is not ready. Run migrations first.', 'ساختار حقوق آماده نیست. ابتدا مایگریشن را اجرا کنید.'))
        return redirect('hr_personnel:payroll_periods')
    organization = getattr(request, 'organization', None)
    if organization is not None and period.organization_id != organization.id:
        messages.error(request, _tr(request, 'You cannot run payroll for this period.', 'شما دسترسی اجرای این دوره را ندارید.'))
        return redirect('hr_personnel:payroll_periods')
    if period.status == PayrollPeriod.Status.CANCELED:
        messages.error(request, _tr(request, 'Canceled periods cannot be processed.', 'دوره‌های باطل‌شده قابل پردازش نیستند.'))
        return redirect('hr_personnel:payroll_periods')

    selected_employee_id = str(request.POST.get('employee_id') or '').strip()
    selected_supply_company_id = str(request.POST.get('supply_company_id') or '').strip()

    employees = _employee_queryset_for_request(request).filter(is_active=True)
    if selected_supply_company_id:
        employees = employees.filter(supply_company_id=selected_supply_company_id)
    if selected_employee_id:
        employees = employees.filter(id=selected_employee_id)
    employees = employees.order_by('first_name', 'last_name')

    if not employees.exists():
        messages.warning(request, _tr(request, 'No active employees found for payroll run.', 'کارمند فعالی برای پردازش حقوق یافت نشد.'))
        return redirect('hr_personnel:payroll_periods')

    eligible_employee_ids = []
    skipped_names = []
    for employee in employees:
        has_active_structure = employee.salary_structures.filter(
            is_active=True,
            effective_from__lte=period.end_date,
        ).filter(
            Q(effective_to__isnull=True) | Q(effective_to__gte=period.start_date)
        ).exists()
        if has_active_structure:
            eligible_employee_ids.append(employee.id)
        else:
            skipped_names.append(f"{employee.first_name} {employee.last_name}".strip())

    employees = employees.filter(id__in=eligible_employee_ids)
    if not employees.exists():
        messages.warning(
            request,
            _tr(
                request,
                'No selected personnel has an active salary structure for this period.',
                'هیچ‌یک از پرسنل انتخاب‌شده در این بازه استراکچر حقوق فعال ندارند.',
            ),
        )
        return redirect('hr_personnel:payroll_periods')

    if skipped_names:
        messages.warning(
            request,
            _tr(
                request,
                f"{len(skipped_names)} employee(s) skipped because salary structure is missing.",
                f"{len(skipped_names)} پرسنل به دلیل نداشتن استراکچر حقوق فعال رد شدند.",
            ),
        )

    try:
        with transaction.atomic():
            period.status = PayrollPeriod.Status.PROCESSING
            period.save(update_fields=['status'])
            payroll_run, slips = PayrollProcessingService.run_period(period=period, employees_qs=employees, created_by=request.user)
            period.status = PayrollPeriod.Status.REVIEW
            period.save(update_fields=['status'])
    except ValidationError as exc:
        period.status = PayrollPeriod.Status.OPEN
        period.save(update_fields=['status'])
        messages.error(request, ', '.join(exc.messages) if getattr(exc, 'messages', None) else _tr(request, 'Payroll run failed.', 'پردازش حقوق با خطا مواجه شد.'))
        return redirect('hr_personnel:payroll_periods')

    messages.success(
        request,
        _tr(
            request,
            f'Payroll run completed for {len(slips)} employees in {payroll_run.execution_ms} ms.',
            f'پردازش حقوق برای {len(slips)} پرسنل در {payroll_run.execution_ms} میلی‌ثانیه انجام شد.',
        ),
    )
    return redirect('hr_personnel:payroll_periods')


@login_required
@user_passes_test(is_supervisor_or_admin)
def payroll_finalize_period(request, period_id):
    if request.method != 'POST':
        return redirect('hr_personnel:payroll_periods')

    try:
        period = get_object_or_404(PayrollPeriod, id=period_id)
    except (OperationalError, ProgrammingError, Exception):
        messages.error(request, _tr(request, 'Payroll schema is not ready. Run migrations first.', 'ساختار حقوق آماده نیست. ابتدا مایگریشن را اجرا کنید.'))
        return redirect('hr_personnel:payroll_periods')
    organization = getattr(request, 'organization', None)
    if organization is not None and period.organization_id != organization.id:
        messages.error(request, _tr(request, 'You cannot finalize this period.', 'شما دسترسی نهایی‌سازی این دوره را ندارید.'))
        return redirect('hr_personnel:payroll_periods')
    if period.status == PayrollPeriod.Status.CANCELED:
        messages.error(request, _tr(request, 'Canceled periods cannot be finalized.', 'دوره‌های باطل‌شده قابل نهایی‌سازی نیستند.'))
        return redirect('hr_personnel:payroll_periods')

    with transaction.atomic():
        period.slips.filter(status=PayrollSlip.Status.DRAFT).update(status=PayrollSlip.Status.APPROVED)
        period.status = PayrollPeriod.Status.FINALIZED
        period.save(update_fields=['status'])

    messages.success(request, _tr(request, 'Payroll period finalized and locked.', 'دوره حقوق و دستمزد نهایی و قفل شد.'))
    return redirect('hr_personnel:payroll_periods')


@login_required
@user_passes_test(is_supervisor_or_admin)
def payroll_delete_period(request, period_id):
    if request.method != 'POST':
        return redirect('hr_personnel:payroll_periods')

    try:
        period = get_object_or_404(PayrollPeriod, id=period_id)
    except (OperationalError, ProgrammingError, Exception):
        messages.error(request, _tr(request, 'Payroll schema is not ready. Run migrations first.', 'ساختار حقوق آماده نیست. ابتدا مایگریشن را اجرا کنید.'))
        return redirect('hr_personnel:payroll_periods')

    organization = getattr(request, 'organization', None)
    if organization is not None and period.organization_id != organization.id:
        messages.error(request, _tr(request, 'You cannot delete this period.', 'شما دسترسی حذف این دوره را ندارید.'))
        return redirect('hr_personnel:payroll_periods')

    if period.status == PayrollPeriod.Status.FINALIZED and period.slips.filter(status=PayrollSlip.Status.PAID).exists():
        messages.error(
            request,
            _tr(
                request,
                'Finalized periods with PAID slips cannot be invalidated. Create an adjustment run instead.',
                'دوره نهایی‌شده‌ای که فیش پرداخت‌شده دارد قابل ابطال نیست. برای اصلاح، دوره تعدیل ایجاد کنید.',
            ),
        )
        return redirect('hr_personnel:payroll_periods')

    if period.status == PayrollPeriod.Status.CANCELED:
        messages.info(request, _tr(request, 'This payroll period is already canceled.', 'این دوره قبلاً باطل شده است.'))
        return redirect('hr_personnel:payroll_periods')

    period.status = PayrollPeriod.Status.CANCELED
    period.save(update_fields=['status'])
    messages.success(
        request,
        _tr(
            request,
            'Payroll period invalidated and kept for audit history. You can now recreate and rerun this date range.',
            'دوره حقوق باطل شد و برای سوابق نگهداری می‌شود. اکنون می‌توانید همین بازه را دوباره ایجاد و پردازش کنید.',
        ),
    )
    return redirect('hr_personnel:payroll_periods')


@login_required
def payroll_payslip_pdf(request, slip_id):
    slip = get_object_or_404(PayrollSlip.objects.select_related('employee'), id=slip_id)
    is_manager = is_supervisor_or_admin(request.user)
    if not is_manager and slip.employee.user_id != request.user.id:
        messages.error(request, _tr(request, 'You do not have access to this payslip.', 'شما دسترسی مشاهده این فیش حقوقی را ندارید.'))
        return redirect('hr_personnel:employee_me')
    return render_payslip_pdf_response(slip=slip, request=request)


@login_required
@user_passes_test(is_supervisor_or_admin)
def payroll_summary_report(request):
    selected_period = None
    periods = []
    rows = []
    total_gross = Decimal('0.000')
    total_net = Decimal('0.000')
    supplier_total_net = Decimal('0.000')
    supplier_breakdown = []
    department_breakdown = []
    selected_supply_company_id = str(request.GET.get('supply_company_id') or '').strip()
    selected_period_id = str(request.GET.get('period_id') or '').strip()
    selected_report_type = str(request.GET.get('report_type') or 'summary').strip().lower()
    selected_bank_export = str(request.GET.get('bank_export') or '').strip().lower()
    export_format = str(request.GET.get('export') or '').strip().lower()
    if selected_report_type not in {'summary', 'overtime', 'deduction'}:
        selected_report_type = 'summary'
    supply_companies = []
    payroll_schema_error = False
    selected_period_badge = _('Not Selected')
    selected_period_badge_class = 'bg-secondary'
    overtime_total = Decimal('0.000')
    overtime_rows = []
    overtime_department_breakdown = []
    deduction_total = Decimal('0.000')
    deduction_breakdown = []

    def _period_badge(status):
        if status == PayrollPeriod.Status.FINALIZED:
            return _('Locked'), 'bg-danger'
        if status == PayrollPeriod.Status.REVIEW:
            return _('In Review'), 'bg-warning text-dark'
        if status == PayrollPeriod.Status.PROCESSING:
            return _('Processing'), 'bg-info text-dark'
        if status == PayrollPeriod.Status.CANCELED:
            return _('Canceled'), 'bg-secondary'
        return _('Active'), 'bg-success'

    try:
        organization = getattr(request, 'organization', None)
        periods_qs = PayrollPeriod.objects.all()
        if organization is not None:
            periods_qs = periods_qs.filter(organization=organization)
        periods = list(periods_qs.order_by('-start_date', '-created_at')[:60])

        if selected_period_id:
            selected_period = next((item for item in periods if str(item.id) == selected_period_id), None)
        if selected_period is None:
            selected_period = _payroll_open_period_for_request(request) or (periods[0] if periods else None)

        if selected_period is not None:
            selected_period_badge, selected_period_badge_class = _period_badge(selected_period.status)

        supply_companies_qs = LaborSupplyCompany.objects.filter(is_active=True)
        if organization is not None:
            supply_companies_qs = supply_companies_qs.filter(organization=organization)
        supply_companies = list(supply_companies_qs.order_by('name'))

        slips_qs = PayrollSlip.objects.select_related('employee', 'period').prefetch_related('items').all()
        if organization is not None:
            slips_qs = slips_qs.filter(employee__organization=organization)
        if selected_period is not None:
            slips_qs = slips_qs.filter(period=selected_period)
        if selected_supply_company_id:
            slips_qs = slips_qs.filter(employee__supply_company_id=selected_supply_company_id)

        company_buckets = {}
        department_buckets = {}
        overtime_employee_buckets = {}
        overtime_department_buckets = {}
        deduction_buckets = {}
        for slip in slips_qs:
            gross_amount = Decimal(str(slip.gross_amount or 0))
            net_amount = Decimal(str(slip.net_amount or 0))
            total_gross += gross_amount
            total_net += net_amount

            company_id = str(slip.employee.supply_company_id or '')
            company_name = getattr(getattr(slip.employee, 'supply_company', None), 'name', '') or _('Unassigned')
            bucket = company_buckets.setdefault(
                company_id,
                {
                    'company_id': company_id,
                    'company_name': company_name,
                    'employees': set(),
                    'gross_total': Decimal('0.000'),
                    'net_total': Decimal('0.000'),
                },
            )
            bucket['employees'].add(slip.employee_id)
            bucket['gross_total'] += gross_amount
            bucket['net_total'] += net_amount

            dept_name = (getattr(slip.employee, 'department', '') or '').strip() or _('Unassigned')
            dept_bucket = department_buckets.setdefault(
                dept_name,
                {
                    'department_name': dept_name,
                    'employees': set(),
                    'gross_total': Decimal('0.000'),
                    'net_total': Decimal('0.000'),
                },
            )
            dept_bucket['employees'].add(slip.employee_id)
            dept_bucket['gross_total'] += gross_amount
            dept_bucket['net_total'] += net_amount

            overtime_amount = Decimal(str(slip.overtime_amount or 0)).quantize(Decimal('0.001'))
            if overtime_amount > 0:
                overtime_total += overtime_amount
                employee_name = f"{slip.employee.first_name or ''} {slip.employee.last_name or ''}".strip()
                overtime_emp_bucket = overtime_employee_buckets.setdefault(
                    str(slip.employee_id),
                    {
                        'employee_name': employee_name,
                        'employee_code': slip.employee.employee_id or '',
                        'department_name': dept_name,
                        'currency': slip.currency or '',
                        'overtime_total': Decimal('0.000'),
                    },
                )
                overtime_emp_bucket['overtime_total'] += overtime_amount

                overtime_dept_bucket = overtime_department_buckets.setdefault(
                    dept_name,
                    {
                        'department_name': dept_name,
                        'employee_count': set(),
                        'overtime_total': Decimal('0.000'),
                    },
                )
                overtime_dept_bucket['employee_count'].add(slip.employee_id)
                overtime_dept_bucket['overtime_total'] += overtime_amount

            for payroll_item in slip.items.all():
                if payroll_item.item_type != PayrollItem.ItemType.DEDUCTION:
                    continue
                item_amount = Decimal(str(payroll_item.amount or 0)).quantize(Decimal('0.001'))
                if item_amount <= 0:
                    continue
                deduction_total += item_amount
                deduction_title = str(payroll_item.title or _('Deduction')).strip() or _('Deduction')
                deduction_bucket = deduction_buckets.setdefault(
                    deduction_title,
                    {
                        'title': deduction_title,
                        'employee_count': set(),
                        'amount_total': Decimal('0.000'),
                    },
                )
                deduction_bucket['employee_count'].add(slip.employee_id)
                deduction_bucket['amount_total'] += item_amount

        supplier_breakdown = sorted(
            [
                {
                    'company_id': item['company_id'],
                    'company_name': item['company_name'],
                    'employee_count': len(item['employees']),
                    'gross_total': item['gross_total'],
                    'net_total': item['net_total'],
                }
                for item in company_buckets.values()
            ],
            key=lambda row: row['company_name'],
        )

        department_breakdown = sorted(
            [
                {
                    'department_name': item['department_name'],
                    'employee_count': len(item['employees']),
                    'gross_total': item['gross_total'],
                    'net_total': item['net_total'],
                }
                for item in department_buckets.values()
            ],
            key=lambda row: row['department_name'],
        )

        overtime_rows = sorted(
            [
                {
                    'employee_name': item['employee_name'],
                    'employee_code': item['employee_code'],
                    'department_name': item['department_name'],
                    'currency': item['currency'],
                    'overtime_total': item['overtime_total'],
                }
                for item in overtime_employee_buckets.values()
            ],
            key=lambda row: row['employee_name'],
        )

        overtime_department_breakdown = sorted(
            [
                {
                    'department_name': item['department_name'],
                    'employee_count': len(item['employee_count']),
                    'overtime_total': item['overtime_total'],
                }
                for item in overtime_department_buckets.values()
            ],
            key=lambda row: row['department_name'],
        )

        deduction_breakdown = sorted(
            [
                {
                    'title': item['title'],
                    'employee_count': len(item['employee_count']),
                    'amount_total': item['amount_total'],
                }
                for item in deduction_buckets.values()
            ],
            key=lambda row: row['title'],
        )

        if selected_supply_company_id:
            supplier_total_net = total_net
        rows = list(slips_qs.order_by('employee__first_name', 'employee__last_name')[:200])
    except (OperationalError, ProgrammingError, Exception):
        payroll_schema_error = True
        messages.error(
            request,
            _tr(
                request,
                'Payroll report tables are not ready yet. Please run hr_personnel migrations.',
                'جداول گزارش حقوق آماده نیستند. لطفاً مایگریشن‌های hr_personnel را اجرا کنید.',
            ),
        )

    if export_format == 'pdf' and not payroll_schema_error:
        period_label = '-'
        if selected_period is not None:
            period_label = f"{selected_period.name} ({selected_period.start_date} - {selected_period.end_date})"
        summary_context = {
            'title': _tr(request, 'Payroll Summary', 'خلاصه حقوق و دستمزد'),
            'period_label': period_label,
            'selected_supply_company_name': next((c.name for c in supply_companies if str(c.id) == selected_supply_company_id), _('All Companies')),
            'total_gross': total_gross,
            'total_net': total_net,
            'supplier_total_net': supplier_total_net,
            'supplier_breakdown': supplier_breakdown,
            'department_breakdown': department_breakdown,
            'rows': rows,
        }
        return render_payroll_summary_pdf_response(context=summary_context)

    if export_format == 'excel' and not payroll_schema_error:
        if not selected_bank_export:
            messages.warning(
                request,
                _tr(
                    request,
                    'Select a bank export template first.',
                    'ابتدا قالب خروجی بانک را انتخاب کنید.',
                ),
            )
            return redirect('hr_personnel:payroll_summary_report')
        return render_bank_payroll_csv_response(
            rows=rows,
            selected_period=selected_period,
            bank_code=selected_bank_export,
        )

    return render(
        request,
        'hr_personnel/payroll_report_summary.html',
        {
            'title': _tr(request, 'Payroll Summary', 'خلاصه حقوق و دستمزد'),
            'rows': rows,
            'periods': periods,
            'selected_period': selected_period,
            'selected_period_id': selected_period_id,
            'selected_report_type': selected_report_type,
            'selected_period_badge': selected_period_badge,
            'selected_period_badge_class': selected_period_badge_class,
            'total_gross': total_gross,
            'total_net': total_net,
            'supplier_total_net': supplier_total_net,
            'supplier_breakdown': supplier_breakdown,
            'department_breakdown': department_breakdown,
            'overtime_total': overtime_total,
            'overtime_rows': overtime_rows,
            'overtime_department_breakdown': overtime_department_breakdown,
            'deduction_total': deduction_total,
            'deduction_breakdown': deduction_breakdown,
            'supply_companies': supply_companies,
            'selected_supply_company_id': selected_supply_company_id,
            'selected_bank_export': selected_bank_export,
            'payroll_schema_error': payroll_schema_error,
            **_payroll_current_period_context(request),
        },
    )


@login_required
@user_passes_test(is_supervisor_or_admin)
def labor_supply_company_manage(request):
    organization = getattr(request, 'organization', None)
    queryset = LaborSupplyCompany.objects.order_by('name')
    if organization is not None:
        queryset = queryset.filter(organization=organization)

    if request.method == 'POST':
        form = LaborSupplyCompanyForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.organization = organization
            item.save()
            messages.success(request, _tr(request, 'Labor supply company saved.', 'شرکت تامین نیرو با موفقیت ذخیره شد.'))
            return redirect('hr_personnel:labor_supply_company_manage')
    else:
        form = LaborSupplyCompanyForm()

    return render(
        request,
        'hr_personnel/labor_supply_company_manage.html',
        {
            'title': _tr(request, 'Labor Supply Companies', 'شرکت‌های تامین نیرو'),
            'form': form,
            'rows': queryset,
        },
    )


@login_required
@user_passes_test(is_supervisor_or_admin)
def work_unit_manage(request):
    organization = getattr(request, 'organization', None)
    queryset = WorkUnit.objects.select_related('parent', 'supervisor').order_by('name')
    if organization is not None:
        queryset = queryset.filter(organization=organization)

    if request.method == 'POST':
        form = WorkUnitForm(request.POST, organization=organization)
        if form.is_valid():
            item = form.save(commit=False)
            item.organization = organization
            item.save()
            messages.success(request, _tr(request, 'Work unit saved.', 'واحد کاری با موفقیت ذخیره شد.'))
            return redirect('hr_personnel:work_unit_manage')
    else:
        form = WorkUnitForm(organization=organization)

    return render(
        request,
        'hr_personnel/work_unit_manage.html',
        {
            'title': _tr(request, 'Work Units', 'واحدهای کاری'),
            'form': form,
            'rows': queryset,
        },
    )


@login_required
@user_passes_test(is_supervisor_or_admin)
def payroll_module_placeholder(request, section, module):
    section_labels = {
        'setup': _('Setup'),
        'compensation': _('Compensation'),
        'processing': _('Processing'),
        'reports': _('Reports'),
    }
    module_title = str(module or '').replace('-', ' ').strip().title()
    context = {
        'title': module_title,
        'section_key': section,
        'section_label': section_labels.get(section, _('Payroll')),
        'module_title': module_title,
        'placeholder_message': _('This module is not implemented yet.'),
        **_payroll_current_period_context(request),
    }
    return render(request, 'hr_personnel/payroll_placeholder.html', context)


@login_required
def reports_hub(request):
    return redirect(_payroll_tab_url('reports'))


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
            'title': _tr(request, 'Employees', 'کارکنان'),
            'is_manager': is_manager,
            'employee': employee,
        },
    )


@login_required
@user_passes_test(is_supervisor_or_admin)
def compensation_hub(request):
    return redirect(_payroll_tab_url('compensation'))


@login_required
def employee_list(request):
    if not is_supervisor_or_admin(request.user):
        return redirect('hr_personnel:employee_me')

    employees = _employee_queryset_for_request(request, apply_supervisor_scope=True)
    selected_supply_company = str(request.GET.get('supply_company') or '').strip()
    selected_work_unit = str(request.GET.get('work_unit') or '').strip()

    if selected_supply_company:
        employees = employees.filter(supply_company_id=selected_supply_company)
    if selected_work_unit:
        employees = employees.filter(work_unit_id=selected_work_unit)

    organization = getattr(request, 'organization', None)
    supply_companies = LaborSupplyCompany.objects.filter(is_active=True).order_by('name')
    work_units = WorkUnit.objects.filter(is_active=True).order_by('name')
    if organization is not None:
        supply_companies = supply_companies.filter(organization=organization)
        work_units = work_units.filter(organization=organization)

    return render(
        request,
        'hr_personnel/employee_list.html',
        {
            'employees': employees,
            'is_manager': True,
            'supply_companies': supply_companies,
            'work_units': work_units,
            'selected_supply_company': selected_supply_company,
            'selected_work_unit': selected_work_unit,
        },
    )


@login_required
@user_passes_test(is_supervisor_or_admin)
def employee_create(request):
    user_profile = getattr(request.user, 'profile', None)
    if request.method == 'POST':
        form = EmployeeForm(
            request.POST,
            organization=getattr(request, 'organization', None),
            user_profile=user_profile,
            is_superuser=request.user.is_superuser,
        )
        if form.is_valid():
            employee = form.save(commit=False)
            # Use form-selected org for superusers, otherwise middleware org
            if request.user.is_superuser and 'organization' in form.fields:
                employee.organization = form.cleaned_data.get('organization')
            else:
                employee.organization = getattr(request, 'organization', None)
            employee.save()
            messages.success(request, _tr(request, 'Employee created successfully.', 'پرسنل با موفقیت ایجاد شد.'))
            return redirect('hr_personnel:employee_detail', employee_id=employee.id)
        if form.non_field_errors():
            messages.error(request, _tr(request, 'Please review the form and fix the highlighted errors.', 'لطفاً فرم را بررسی کرده و خطاهای مشخص‌شده را اصلاح کنید.'))
    else:
        form = EmployeeForm(
            organization=getattr(request, 'organization', None),
            user_profile=user_profile,
            is_superuser=request.user.is_superuser,
        )

    return render(request, 'hr_personnel/employee_form.html', {'form': form, 'title': _tr(request, 'Create Employee', 'ایجاد پرسنل')})


@login_required
@user_passes_test(is_supervisor_or_admin)
def employee_edit(request, employee_id):
    employee = get_object_or_404(_employee_queryset_for_request(request, apply_supervisor_scope=True), id=employee_id)
    user_profile = getattr(request.user, 'profile', None)

    if request.method == 'POST':
        form = EmployeeForm(
            request.POST,
            instance=employee,
            organization=getattr(request, 'organization', None),
            user_profile=user_profile,
            is_superuser=request.user.is_superuser,
        )
        if form.is_valid():
            emp = form.save(commit=False)
            if request.user.is_superuser and 'organization' in form.fields:
                emp.organization = form.cleaned_data.get('organization')
            emp.save()
            messages.success(request, _tr(request, 'Employee updated successfully.', 'اطلاعات پرسنل با موفقیت بروزرسانی شد.'))
            return redirect('hr_personnel:employee_detail', employee_id=employee.id)
        if form.non_field_errors():
            messages.error(request, _tr(request, 'Please review the form and fix the highlighted errors.', 'لطفاً فرم را بررسی کرده و خطاهای مشخص‌شده را اصلاح کنید.'))
    else:
        form = EmployeeForm(
            instance=employee,
            organization=getattr(request, 'organization', None),
            user_profile=user_profile,
            is_superuser=request.user.is_superuser,
        )

    return render(request, 'hr_personnel/employee_form.html', {'form': form, 'title': _tr(request, 'Edit Employee', 'ویرایش پرسنل')})


@login_required
@user_passes_test(is_supervisor_or_admin)
def employee_delete(request, employee_id):
    employee = get_object_or_404(_employee_queryset_for_request(request, apply_supervisor_scope=True), id=employee_id)
    if request.method == 'POST':
        employee.delete()
        messages.success(request, _tr(request, 'Employee deleted successfully.', 'پرسنل با موفقیت حذف شد.'))
        return redirect('hr_personnel:employee_list')

    return render(request, 'hr_personnel/employee_delete.html', {'employee': employee})


@login_required
def employee_detail(request, employee_id):
    employee = get_object_or_404(_employee_queryset_for_request(request, apply_supervisor_scope=True), id=employee_id)

    is_manager = is_supervisor_or_admin(request.user)
    if not is_manager and employee.user_id != request.user.id:
        messages.error(request, _tr(request, 'You do not have access to this personnel profile.', 'شما دسترسی مشاهده این پروفایل پرسنلی را ندارید.'))
        return redirect('hr_personnel:employee_me')

    try:
        salary_profiles = list(employee.salary_structures.prefetch_related('components').all())
    except (OperationalError, ProgrammingError):
        salary_profiles = []

    bank_accounts = employee.bank_accounts.all()

    try:
        payroll_slips = list(employee.payroll_slips.prefetch_related('items').all())
    except (OperationalError, ProgrammingError):
        payroll_slips = []

    schema_ok = bool(salary_profiles is not None)
    if not salary_profiles and not payroll_slips:
        try:
            employee.salary_structures.values_list('id', flat=True)[:1]
        except (OperationalError, ProgrammingError):
            schema_ok = False

    return render(
        request,
        'hr_personnel/employee_detail.html',
        {
            'employee': employee,
            'salary_profiles': salary_profiles,
            'bank_accounts': bank_accounts,
            'payroll_slips': payroll_slips,
            'is_manager': is_manager,
            'schema_ok': schema_ok,
        },
    )


@login_required
@user_passes_test(is_supervisor_or_admin)
def salary_profile_create(request, employee_id):
    employee = get_object_or_404(_employee_queryset_for_request(request, apply_supervisor_scope=True), id=employee_id)
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
def salary_profile_edit(request, employee_id, profile_id):
    employee = get_object_or_404(_employee_queryset_for_request(request, apply_supervisor_scope=True), id=employee_id)
    profile = get_object_or_404(SalaryStructure, id=profile_id, employee=employee)
    user_profile = getattr(request.user, 'profile', None)

    if request.method == 'POST':
        form = SalaryProfileForm(request.POST, instance=profile, user_profile=user_profile)
        formset = SalaryComponentFormSet(request.POST, instance=profile)

        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    updated_profile = form.save()
                    formset.instance = updated_profile
                    formset.save()
                    PayrollCalculator.validate_structure_components(updated_profile)
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                messages.success(request, _tr(request, 'Salary structure updated successfully.', 'ساختار حقوق با موفقیت بروزرسانی شد.'))
                return redirect('hr_personnel:employee_detail', employee_id=employee.id)
    else:
        form = SalaryProfileForm(instance=profile, user_profile=user_profile)
        formset = SalaryComponentFormSet(instance=profile)

    return render(
        request,
        'hr_personnel/salary_profile_form.html',
        {
            'form': form,
            'formset': formset,
            'employee': employee,
            'title': _tr(request, 'Edit Salary Structure', 'ویرایش ساختار حقوق'),
            'is_edit': True,
        },
    )


@login_required
@user_passes_test(is_supervisor_or_admin)
def salary_profile_delete(request, employee_id, profile_id):
    employee = get_object_or_404(_employee_queryset_for_request(request, apply_supervisor_scope=True), id=employee_id)
    profile = get_object_or_404(SalaryStructure, id=profile_id, employee=employee)

    if request.method == 'POST':
        profile.delete()
        messages.success(request, _tr(request, 'Salary structure deleted successfully.', 'ساختار حقوق با موفقیت حذف شد.'))
    return redirect('hr_personnel:employee_detail', employee_id=employee.id)


@login_required
@user_passes_test(is_supervisor_or_admin)
def salary_component_create(request, employee_id, profile_id):
    employee = get_object_or_404(_employee_queryset_for_request(request, apply_supervisor_scope=True), id=employee_id)
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
    employee = get_object_or_404(_employee_queryset_for_request(request, apply_supervisor_scope=True), id=employee_id)

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
    messages.info(
        request,
        _tr(
            request,
            'Payroll creation is available only from Payroll > Processing workflow.',
            'ایجاد فیش حقوقی فقط از مسیر حقوق و دستمزد > پردازش قابل انجام است.',
        ),
    )
    return redirect(_payroll_tab_url('processing'))


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
    employee = get_object_or_404(_employee_queryset_for_request(request, apply_supervisor_scope=True), id=employee_id)
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
    employee = get_object_or_404(_employee_queryset_for_request(request, apply_supervisor_scope=True), id=employee_id)
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


# ─────────────────────────────────────────────────────────────────────────────
# Leave Request Workflow
# ─────────────────────────────────────────────────────────────────────────────

def _current_employee(request):
    """Return the hr_personnel Employee bound to request.user (if any)."""
    try:
        return getattr(request.user, 'employee', None)
    except Exception:
        return None


def _can_manage_leave(request, leave_request):
    """True if request.user may approve/reject leave_request."""
    if request.user.is_superuser:
        return True
    try:
        role = getattr(request.user.profile, 'role', 'user')
    except Exception:
        role = 'user'
    if role == 'admin':
        return True
    if role != 'supervisor':
        return False

    emp = leave_request.employee
    if emp is None:
        return False

    # Linked user → check profile.supervisor
    if emp.user_id and getattr(getattr(emp.user, 'profile', None), 'supervisor_id', None) == request.user.id:
        return True
    # Unlinked (or explicit) → Employee.supervisor FK
    if getattr(emp, 'supervisor_id', None) == request.user.id:
        return True
    # Legacy fallbacks via current supervisor's employee record
    me = _current_employee(request)
    if me is not None:
        if getattr(emp, 'reporting_manager_id', None) == me.id:
            return True
        if getattr(getattr(emp, 'work_unit', None), 'supervisor_id', None) == me.id:
            return True
    return False


def _leave_requests_for_request(request):
    """All leave requests the current user is allowed to see."""
    qs = LeaveRequest.objects.select_related('employee', 'employee__user', 'employee__work_unit', 'approved_by').all()
    org = getattr(request, 'organization', None)
    if org:
        qs = qs.filter(employee__organization=org)
    if request.user.is_superuser:
        return qs
    try:
        role = getattr(request.user.profile, 'role', 'user')
    except Exception:
        role = 'user'
    if role == 'admin':
        return qs

    me = _current_employee(request)
    own = Q(employee__user=request.user)
    if me is not None:
        own |= Q(employee=me)

    if role == 'supervisor':
        managed_emps = _employee_queryset_for_request(request, apply_supervisor_scope=True)
        return qs.filter(own | Q(employee__in=managed_emps)).distinct()
    return qs.filter(own).distinct()


def _calc_leave_totals(is_hourly, from_date, to_date, start_time, end_time):
    """Compute total_days / total_hours for a leave request."""
    if is_hourly:
        if not (start_time and end_time):
            raise ValidationError(_('Start time and end time are required for hourly leave.'))
        if from_date != to_date:
            raise ValidationError(_('Hourly leave must be for a single day.'))
        start_dt = datetime.combine(from_date, start_time)
        end_dt = datetime.combine(from_date, end_time)
        if end_dt <= start_dt:
            raise ValidationError(_('End time must be after start time.'))
        hours = Decimal((end_dt - start_dt).total_seconds()) / Decimal('3600')
        hours = hours.quantize(Decimal('0.01'))
        # Treat 8h workday as 1 day (0.125 per hour); clamp 0..1
        days = (hours / Decimal('8')).quantize(Decimal('0.01'))
        if days > Decimal('1.00'):
            days = Decimal('1.00')
        return days, hours
    if to_date < from_date:
        raise ValidationError(_('End date cannot be before start date.'))
    days = Decimal((to_date - from_date).days + 1)
    hours = (days * Decimal('8')).quantize(Decimal('0.01'))
    return days.quantize(Decimal('0.01')), hours


@login_required
def leave_request_list(request):
    qs = _leave_requests_for_request(request).order_by('-created_at')

    status_filter = (request.GET.get('status') or '').strip()
    if status_filter:
        qs = qs.filter(status=status_filter)

    mine_only = request.GET.get('mine') == '1'
    if mine_only:
        me = _current_employee(request)
        own = Q(employee__user=request.user)
        if me is not None:
            own |= Q(employee=me)
        qs = qs.filter(own)

    try:
        role = getattr(request.user.profile, 'role', 'user')
    except Exception:
        role = 'user'
    can_manage = request.user.is_superuser or role in ('admin', 'supervisor')

    pending_count = qs.filter(status=LeaveRequest.Status.PENDING).count()

    return render(request, 'hr_personnel/leave_request_list.html', {
        'leave_requests': qs[:500],
        'status_filter': status_filter,
        'mine_only': mine_only,
        'can_manage': can_manage,
        'pending_count': pending_count,
        'status_choices': LeaveRequest.Status.choices,
    })


@login_required
def leave_request_create(request):
    org = getattr(request, 'organization', None)
    me = _current_employee(request)

    try:
        role = getattr(request.user.profile, 'role', 'user')
    except Exception:
        role = 'user'
    can_pick_employee = request.user.is_superuser or role in ('admin', 'supervisor')

    # Employees list for supervisor/admin selection
    if can_pick_employee:
        employees_qs = _employee_queryset_for_request(request, apply_supervisor_scope=True).order_by('first_name', 'last_name')
    else:
        employees_qs = Employee.objects.filter(id=me.id) if me else Employee.objects.none()

    leave_types = LeaveRequest._meta.get_field('leave_type').choices

    if request.method == 'POST':
        target_employee = me
        if can_pick_employee:
            eid = request.POST.get('employee')
            if eid:
                target_employee = employees_qs.filter(id=eid).first()

        if target_employee is None:
            messages.error(request, _tr(request, 'No employee selected.', 'هیچ پرسنلی انتخاب نشد.'))
            return redirect('hr_personnel:leave_request_create')

        leave_type = (request.POST.get('leave_type') or '').strip()
        is_hourly = request.POST.get('is_hourly') == '1'
        from_date_raw = (request.POST.get('from_date') or '').strip()
        to_date_raw = (request.POST.get('to_date') or '').strip()
        start_time_raw = (request.POST.get('start_time') or '').strip()
        end_time_raw = (request.POST.get('end_time') or '').strip()
        reason = (request.POST.get('reason') or '').strip()
        attachment = request.FILES.get('attachment')

        try:
            from_date = date.fromisoformat(from_date_raw)
            to_date = date.fromisoformat(to_date_raw) if to_date_raw else from_date
            start_time = time_cls.fromisoformat(start_time_raw) if start_time_raw else None
            end_time = time_cls.fromisoformat(end_time_raw) if end_time_raw else None
        except Exception:
            messages.error(request, _tr(request, 'Invalid date or time format.', 'فرمت تاریخ یا ساعت نامعتبر است.'))
            return redirect('hr_personnel:leave_request_create')

        valid_types = {k for k, _v in leave_types}
        if leave_type not in valid_types:
            messages.error(request, _tr(request, 'Invalid leave type.', 'نوع مرخصی نامعتبر است.'))
            return redirect('hr_personnel:leave_request_create')

        try:
            total_days, total_hours = _calc_leave_totals(is_hourly, from_date, to_date, start_time, end_time)
        except ValidationError as exc:
            messages.error(request, '; '.join(exc.messages))
            return redirect('hr_personnel:leave_request_create')

        # Check overlap with pending/approved requests
        overlap = LeaveRequest.objects.filter(
            employee=target_employee,
            status__in=[LeaveRequest.Status.PENDING, LeaveRequest.Status.APPROVED],
            from_date__lte=to_date,
            to_date__gte=from_date,
        ).exists()
        if overlap:
            messages.error(request, _tr(
                request,
                'This employee already has an overlapping pending/approved leave request.',
                'این پرسنل یک درخواست مرخصی در حال بررسی/تأییدشده با بازه تداخل دارد.',
            ))
            return redirect('hr_personnel:leave_request_create')

        LeaveRequest.objects.create(
            employee=target_employee,
            leave_type=leave_type,
            is_hourly=is_hourly,
            from_date=from_date,
            to_date=to_date,
            start_time=start_time,
            end_time=end_time,
            total_days=total_days,
            total_hours=total_hours,
            reason=reason,
            attachment=attachment,
            status=LeaveRequest.Status.PENDING,
        )
        messages.success(request, _tr(request, 'Leave request submitted.', 'درخواست مرخصی ثبت شد.'))
        return redirect('hr_personnel:leave_request_list')

    today_iso = timezone.localdate().isoformat()
    return render(request, 'hr_personnel/leave_request_form.html', {
        'employees': employees_qs,
        'can_pick_employee': can_pick_employee,
        'leave_types': leave_types,
        'today_iso': today_iso,
        'current_employee': me,
    })


@login_required
def leave_request_detail(request, request_id):
    leave = get_object_or_404(_leave_requests_for_request(request), id=request_id)
    can_manage = _can_manage_leave(request, leave)
    me = _current_employee(request)
    is_owner = (leave.employee_id is not None and (
        (me is not None and leave.employee_id == me.id) or leave.employee.user_id == request.user.id
    ))
    return render(request, 'hr_personnel/leave_request_detail.html', {
        'leave': leave,
        'can_manage': can_manage,
        'is_owner': is_owner,
    })


@login_required
def leave_request_approve(request, request_id):
    if request.method != 'POST':
        return redirect('hr_personnel:leave_request_detail', request_id=request_id)
    leave = get_object_or_404(_leave_requests_for_request(request), id=request_id)
    if not _can_manage_leave(request, leave):
        messages.error(request, _tr(request, 'You are not allowed to approve this request.', 'مجاز به تأیید این درخواست نیستید.'))
        return redirect('hr_personnel:leave_request_detail', request_id=request_id)
    if leave.status != LeaveRequest.Status.PENDING:
        messages.error(request, _tr(request, 'Only pending requests can be approved.', 'فقط درخواست‌های در حال بررسی قابل تأیید هستند.'))
        return redirect('hr_personnel:leave_request_detail', request_id=request_id)

    leave.status = LeaveRequest.Status.APPROVED
    leave.approved_by = request.user
    leave.approved_at = timezone.now()
    leave.rejection_reason = None
    leave.save(update_fields=['status', 'approved_by', 'approved_at', 'rejection_reason', 'updated_at'])
    messages.success(request, _tr(request, 'Leave request approved.', 'درخواست مرخصی تأیید شد.'))
    return redirect('hr_personnel:leave_request_detail', request_id=request_id)


@login_required
def leave_request_reject(request, request_id):
    if request.method != 'POST':
        return redirect('hr_personnel:leave_request_detail', request_id=request_id)
    leave = get_object_or_404(_leave_requests_for_request(request), id=request_id)
    if not _can_manage_leave(request, leave):
        messages.error(request, _tr(request, 'You are not allowed to reject this request.', 'مجاز به رد این درخواست نیستید.'))
        return redirect('hr_personnel:leave_request_detail', request_id=request_id)
    if leave.status != LeaveRequest.Status.PENDING:
        messages.error(request, _tr(request, 'Only pending requests can be rejected.', 'فقط درخواست‌های در حال بررسی قابل رد هستند.'))
        return redirect('hr_personnel:leave_request_detail', request_id=request_id)

    reason = (request.POST.get('rejection_reason') or '').strip()
    leave.status = LeaveRequest.Status.REJECTED
    leave.approved_by = request.user
    leave.approved_at = timezone.now()
    leave.rejection_reason = reason
    leave.save(update_fields=['status', 'approved_by', 'approved_at', 'rejection_reason', 'updated_at'])
    messages.success(request, _tr(request, 'Leave request rejected.', 'درخواست مرخصی رد شد.'))
    return redirect('hr_personnel:leave_request_detail', request_id=request_id)


@login_required
def leave_request_cancel(request, request_id):
    if request.method != 'POST':
        return redirect('hr_personnel:leave_request_detail', request_id=request_id)
    leave = get_object_or_404(_leave_requests_for_request(request), id=request_id)

    me = _current_employee(request)
    is_owner = leave.employee_id is not None and (
        (me is not None and leave.employee_id == me.id) or leave.employee.user_id == request.user.id
    )
    if not (is_owner or _can_manage_leave(request, leave)):
        messages.error(request, _tr(request, 'You are not allowed to cancel this request.', 'مجاز به لغو این درخواست نیستید.'))
        return redirect('hr_personnel:leave_request_detail', request_id=request_id)
    if leave.status not in (LeaveRequest.Status.PENDING, LeaveRequest.Status.APPROVED):
        messages.error(request, _tr(request, 'This request cannot be cancelled.', 'این درخواست قابل لغو نیست.'))
        return redirect('hr_personnel:leave_request_detail', request_id=request_id)

    leave.status = LeaveRequest.Status.CANCELLED
    leave.save(update_fields=['status', 'updated_at'])
    messages.success(request, _tr(request, 'Leave request cancelled.', 'درخواست مرخصی لغو شد.'))
    return redirect('hr_personnel:leave_request_detail', request_id=request_id)
