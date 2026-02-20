import datetime
import calendar

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import OperationalError, ProgrammingError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from apps.hrms.forms import (
    EmployeeShiftAssignmentForm,
    OvertimePolicyForm,
    OvertimeRateRuleForm,
    ShiftTemplateForm,
    ShiftVersionForm,
    WorkCalendarBulkGenerateForm,
    WorkCalendarForm,
)
from apps.hrms.models import (
    EmployeeShiftAssignment,
    OvertimePolicy,
    OvertimeRateRule,
    PayrollOvertimeEntry,
    ShiftTemplate,
    ShiftVersion,
    Timesheet,
    WorkCalendar,
)
from apps.hrms.tenant import resolve_company_for_request


DEFAULT_PUBLIC_HOLIDAYS = {
    'IR': {
        (1, 1): 'Nowruz',
        (1, 2): 'Nowruz Holiday',
        (1, 3): 'Nowruz Holiday',
        (1, 4): 'Nowruz Holiday',
        (2, 1): 'Islamic Republic Day',
    },
    'OM': {
        (1, 1): 'New Year',
        (11, 18): 'National Day',
    },
}


def _tr(request, en_text, fa_text):
    lang = str(getattr(request, 'LANGUAGE_CODE', '')).lower()
    if lang.startswith('fa'):
        return fa_text
    return _(en_text)


def is_hrms_manager(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    try:
        return getattr(user.profile, 'role', 'user') in ['admin', 'supervisor']
    except Exception:
        return False


def _tenant_or_redirect(request):
    try:
        tenant = resolve_company_for_request(request)
    except (ProgrammingError, OperationalError):
        messages.error(
            request,
            _tr(
                request,
                'HRMS database tables are not ready yet. Please run migrations first.',
                'جداول دیتابیس HRMS هنوز آماده نیست. لطفا ابتدا مهاجرت‌ها را اجرا کنید.',
            ),
        )
        return None
    if tenant is None:
        messages.error(request, _tr(request, 'HRMS is not configured for your organization yet.', 'ماژول HRMS برای سازمان شما هنوز پیکربندی نشده است.'))
        return None
    return tenant


@login_required
def hrms_dashboard(request):
    tenant = _tenant_or_redirect(request)
    if tenant is None:
        return redirect('main_dashboard')

    start_of_month = datetime.date.today().replace(day=1)
    context = {
        'tenant': tenant,
        'shift_templates_count': ShiftTemplate.objects.filter(tenant=tenant).count(),
        'shift_versions_count': ShiftVersion.objects.filter(tenant=tenant).count(),
        'work_calendar_count': WorkCalendar.objects.filter(tenant=tenant).count(),
        'active_overtime_policies_count': OvertimePolicy.objects.filter(tenant=tenant, is_active=True).count(),
        'timesheets_month_count': Timesheet.objects.filter(tenant=tenant, work_date__gte=start_of_month).count(),
        'payroll_overtime_month_count': PayrollOvertimeEntry.objects.filter(
            tenant=tenant,
            period_year=start_of_month.year,
            period_month=start_of_month.month,
        ).count(),
    }
    return render(request, 'hrms/dashboard.html', context)


@login_required
@user_passes_test(is_hrms_manager)
def shift_template_list(request):
    tenant = _tenant_or_redirect(request)
    if tenant is None:
        return redirect('main_dashboard')

    templates = ShiftTemplate.objects.filter(tenant=tenant).order_by('name')
    return render(request, 'hrms/shift_template_list.html', {'tenant': tenant, 'templates': templates})


@login_required
@user_passes_test(is_hrms_manager)
def shift_template_create(request):
    tenant = _tenant_or_redirect(request)
    if tenant is None:
        return redirect('main_dashboard')

    if request.method == 'POST':
        form = ShiftTemplateForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = tenant
            obj.save()
            messages.success(request, _tr(request, 'Shift template created.', 'الگوی شیفت با موفقیت ایجاد شد.'))
            return redirect('hrms:shift_template_list')
    else:
        form = ShiftTemplateForm()

    return render(request, 'hrms/shift_template_form.html', {'tenant': tenant, 'form': form})


@login_required
@user_passes_test(is_hrms_manager)
def shift_version_list(request):
    tenant = _tenant_or_redirect(request)
    if tenant is None:
        return redirect('main_dashboard')

    versions = ShiftVersion.objects.filter(tenant=tenant).select_related('shift').order_by('-valid_from')
    return render(request, 'hrms/shift_version_list.html', {'tenant': tenant, 'versions': versions})


@login_required
@user_passes_test(is_hrms_manager)
def shift_version_create(request):
    tenant = _tenant_or_redirect(request)
    if tenant is None:
        return redirect('main_dashboard')

    if request.method == 'POST':
        form = ShiftVersionForm(request.POST, tenant=tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = tenant
            obj.save()
            messages.success(request, _tr(request, 'Shift version created.', 'نسخه شیفت با موفقیت ایجاد شد.'))
            return redirect('hrms:shift_version_list')
    else:
        form = ShiftVersionForm(tenant=tenant)

    return render(request, 'hrms/shift_version_form.html', {'tenant': tenant, 'form': form})


@login_required
@user_passes_test(is_hrms_manager)
def shift_assignment_list(request):
    tenant = _tenant_or_redirect(request)
    if tenant is None:
        return redirect('main_dashboard')

    assignments = EmployeeShiftAssignment.objects.filter(tenant=tenant).select_related('employee', 'shift').order_by('-effective_from')
    return render(request, 'hrms/shift_assignment_list.html', {'tenant': tenant, 'assignments': assignments})


@login_required
@user_passes_test(is_hrms_manager)
def shift_assignment_create(request):
    tenant = _tenant_or_redirect(request)
    if tenant is None:
        return redirect('main_dashboard')

    if request.method == 'POST':
        form = EmployeeShiftAssignmentForm(request.POST, tenant=tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = tenant
            obj.save()
            messages.success(request, _tr(request, 'Shift assignment created.', 'اختصاص شیفت با موفقیت ثبت شد.'))
            return redirect('hrms:shift_assignment_list')
    else:
        form = EmployeeShiftAssignmentForm(tenant=tenant)

    return render(request, 'hrms/shift_assignment_form.html', {'tenant': tenant, 'form': form})


@login_required
@user_passes_test(is_hrms_manager)
def work_calendar_list(request):
    tenant = _tenant_or_redirect(request)
    if tenant is None:
        return redirect('main_dashboard')

    selected_month = request.GET.get('month')
    rows = WorkCalendar.objects.filter(tenant=tenant)
    if selected_month:
        try:
            year, month = selected_month.split('-')
            rows = rows.filter(date__year=int(year), date__month=int(month))
        except Exception:
            pass

    rows = rows.order_by('-date')
    return render(request, 'hrms/work_calendar_list.html', {'tenant': tenant, 'rows': rows, 'selected_month': selected_month or ''})


@login_required
@user_passes_test(is_hrms_manager)
def work_calendar_create(request):
    tenant = _tenant_or_redirect(request)
    if tenant is None:
        return redirect('main_dashboard')

    if request.method == 'POST':
        form = WorkCalendarForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = tenant
            obj.save()
            messages.success(request, _tr(request, 'Work calendar day saved.', 'روز کاری/تعطیلی با موفقیت ذخیره شد.'))
            return redirect('hrms:work_calendar_list')
    else:
        form = WorkCalendarForm()

    return render(request, 'hrms/work_calendar_form.html', {'tenant': tenant, 'form': form})


@login_required
@user_passes_test(is_hrms_manager)
def work_calendar_bulk_generate(request):
    tenant = _tenant_or_redirect(request)
    if tenant is None:
        return redirect('main_dashboard')

    if request.method == 'POST':
        form = WorkCalendarBulkGenerateForm(request.POST, country=tenant.country)
        if form.is_valid():
            year = form.cleaned_data['year']
            default_work_minutes = form.cleaned_data['default_work_minutes']
            weekend_days = {int(day) for day in form.cleaned_data['weekend_days']}
            include_public_holidays = form.cleaned_data['include_public_holidays']
            overwrite_existing = form.cleaned_data['overwrite_existing']

            holiday_map = DEFAULT_PUBLIC_HOLIDAYS.get(tenant.country, {}) if include_public_holidays else {}
            created_count = 0
            updated_count = 0

            for month in range(1, 13):
                month_days = calendar.monthrange(year, month)[1]
                for day in range(1, month_days + 1):
                    current_date = datetime.date(year, month, day)
                    is_weekend = current_date.weekday() in weekend_days
                    holiday_name = holiday_map.get((month, day))

                    day_type = WorkCalendar.DayType.WORKING
                    minutes = default_work_minutes
                    if is_weekend:
                        day_type = WorkCalendar.DayType.WEEKEND
                        minutes = 0
                    if holiday_name:
                        day_type = WorkCalendar.DayType.PUBLIC_HOLIDAY
                        minutes = 0

                    defaults = {
                        'day_type': day_type,
                        'holiday_name': holiday_name,
                        'standard_work_minutes': minutes,
                    }

                    if overwrite_existing:
                        _, created = WorkCalendar.objects.update_or_create(
                            tenant=tenant,
                            date=current_date,
                            defaults=defaults,
                        )
                        if created:
                            created_count += 1
                        else:
                            updated_count += 1
                    else:
                        _, created = WorkCalendar.objects.get_or_create(
                            tenant=tenant,
                            date=current_date,
                            defaults=defaults,
                        )
                        if created:
                            created_count += 1

            messages.success(
                request,
                _tr(
                    request,
                    f'Calendar generated for {year}. Created: {created_count}, Updated: {updated_count}.',
                    f'تقویم سال {year} ساخته شد. ایجاد: {created_count}، بروزرسانی: {updated_count}.',
                ),
            )
            return redirect('hrms:work_calendar_list')
    else:
        form = WorkCalendarBulkGenerateForm(
            initial={'year': datetime.date.today().year},
            country=tenant.country,
        )

    return render(request, 'hrms/work_calendar_generate.html', {'tenant': tenant, 'form': form})


@login_required
@user_passes_test(is_hrms_manager)
def overtime_policy_list(request):
    tenant = _tenant_or_redirect(request)
    if tenant is None:
        return redirect('main_dashboard')

    policies = OvertimePolicy.objects.filter(tenant=tenant).order_by('-effective_from')
    return render(request, 'hrms/overtime_policy_list.html', {'tenant': tenant, 'policies': policies})


@login_required
@user_passes_test(is_hrms_manager)
def overtime_policy_create(request):
    tenant = _tenant_or_redirect(request)
    if tenant is None:
        return redirect('main_dashboard')

    if request.method == 'POST':
        form = OvertimePolicyForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = tenant
            obj.save()
            messages.success(request, _tr(request, 'Overtime policy created.', 'قانون اضافه‌کاری با موفقیت ایجاد شد.'))
            return redirect('hrms:overtime_policy_list')
    else:
        form = OvertimePolicyForm()

    return render(request, 'hrms/overtime_policy_form.html', {'tenant': tenant, 'form': form})


@login_required
@user_passes_test(is_hrms_manager)
def overtime_rule_create(request, policy_id):
    tenant = _tenant_or_redirect(request)
    if tenant is None:
        return redirect('main_dashboard')

    policy = get_object_or_404(OvertimePolicy, id=policy_id, tenant=tenant)

    if request.method == 'POST':
        form = OvertimeRateRuleForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.policy = policy
            obj.save()
            messages.success(request, _tr(request, 'Overtime rate rule added.', 'قانون نرخ اضافه‌کاری اضافه شد.'))
            return redirect('hrms:overtime_policy_list')
    else:
        form = OvertimeRateRuleForm()

    return render(request, 'hrms/overtime_rule_form.html', {'tenant': tenant, 'policy': policy, 'form': form})
