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
    WorkClosureForm,
    WorkCalendarBulkGenerateForm,
    WorkCalendarForm,
    WorkUnitShiftAssignmentForm,
)
from apps.hrms.models import (
    Employee as HrmsEmployee,
    EmployeeShiftAssignment,
    OvertimePolicy,
    OvertimeRateRule,
    PayrollOvertimeEntry,
    ShiftTemplate,
    ShiftVersion,
    Timesheet,
    WorkClosure,
    WorkCalendar,
    WorkUnitShiftAssignment,
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


def _safe_count(queryset, fallback=0):
    try:
        return queryset.count()
    except (ProgrammingError, OperationalError):
        return fallback


def _ensure_hrms_employees_from_personnel(tenant):
    org = getattr(tenant, 'organization', None)
    if org is None:
        return

    from apps.hr_personnel.models import Employee as PersonnelEmployee

    personnel_rows = PersonnelEmployee.objects.filter(organization=org, is_active=True).select_related('user')
    existing_codes = set(HrmsEmployee.objects.filter(tenant=tenant).values_list('employee_code', flat=True))
    linked_codes = dict(
        HrmsEmployee.objects.filter(tenant=tenant, personnel_employee__isnull=False).values_list('personnel_employee_id', 'employee_code')
    )

    for personnel in personnel_rows:
        current_code = linked_codes.get(personnel.id)
        if current_code:
            chosen_code = current_code
        else:
            base_code = (
                str(personnel.employee_id or '').strip()
                or str(personnel.company_id or '').strip()
                or f"P-{str(personnel.id).split('-')[0]}"
            )
            chosen_code = base_code
            suffix = 2
            while chosen_code in existing_codes:
                chosen_code = f"{base_code}-{suffix}"
                suffix += 1

        HrmsEmployee.objects.update_or_create(
            tenant=tenant,
            personnel_employee=personnel,
            defaults={
                'user': personnel.user,
                'employee_code': chosen_code,
                'first_name': personnel.first_name,
                'last_name': personnel.last_name,
                'nationality': personnel.nationality,
                'hire_date': personnel.hire_date or datetime.date.today(),
                'is_active': bool(personnel.is_active),
            },
        )
        existing_codes.add(chosen_code)


@login_required
def hrms_dashboard(request):
    tenant = _tenant_or_redirect(request)
    if tenant is None:
        return redirect('main_dashboard')

    start_of_month = datetime.date.today().replace(day=1)
    work_unit_shift_qs = WorkUnitShiftAssignment.objects.filter(tenant=tenant, is_active=True)
    work_unit_shift_count = _safe_count(work_unit_shift_qs)
    if work_unit_shift_count == 0:
        try:
            _ = work_unit_shift_qs.exists()
        except (ProgrammingError, OperationalError):
            messages.warning(
                request,
                _tr(
                    request,
                    'Some HRMS tables are missing. Run migrations to enable all dashboard widgets.',
                    'برخی جداول HRMS موجود نیست. برای فعال شدن کامل ویجت‌های داشبورد، مهاجرت‌ها را اجرا کنید.',
                ),
            )

    context = {
        'tenant': tenant,
        'shift_templates_count': _safe_count(ShiftTemplate.objects.filter(tenant=tenant)),
        'shift_versions_count': _safe_count(ShiftVersion.objects.filter(tenant=tenant)),
        'work_unit_shift_assignments_count': work_unit_shift_count,
        'work_calendar_count': _safe_count(WorkCalendar.objects.filter(tenant=tenant)),
        'active_work_closures_count': _safe_count(WorkClosure.objects.filter(tenant=tenant, end_date__gte=start_of_month)),
        'active_overtime_policies_count': _safe_count(OvertimePolicy.objects.filter(tenant=tenant, is_active=True)),
        'timesheets_month_count': _safe_count(Timesheet.objects.filter(tenant=tenant, work_date__gte=start_of_month)),
        'payroll_overtime_month_count': _safe_count(PayrollOvertimeEntry.objects.filter(
            tenant=tenant,
            period_year=start_of_month.year,
            period_month=start_of_month.month,
        )),
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

    return render(
        request,
        'hrms/shift_template_form.html',
        {
            'tenant': tenant,
            'form': form,
            'is_edit': False,
        },
    )


@login_required
@user_passes_test(is_hrms_manager)
def shift_template_edit(request, template_id):
    tenant = _tenant_or_redirect(request)
    if tenant is None:
        return redirect('main_dashboard')

    shift_template = get_object_or_404(ShiftTemplate, tenant=tenant, id=template_id)

    if request.method == 'POST':
        form = ShiftTemplateForm(request.POST, instance=shift_template)
        if form.is_valid():
            form.save()
            messages.success(request, _tr(request, 'Shift template updated.', 'الگوی شیفت با موفقیت ویرایش شد.'))
            return redirect('hrms:shift_template_list')
    else:
        form = ShiftTemplateForm(instance=shift_template)

    return render(
        request,
        'hrms/shift_template_form.html',
        {
            'tenant': tenant,
            'form': form,
            'is_edit': True,
            'shift_template': shift_template,
        },
    )


@login_required
@user_passes_test(is_hrms_manager)
def shift_template_delete(request, template_id):
    tenant = _tenant_or_redirect(request)
    if tenant is None:
        return redirect('main_dashboard')

    shift_template = get_object_or_404(ShiftTemplate, tenant=tenant, id=template_id)
    if request.method != 'POST':
        messages.error(request, _tr(request, 'Invalid delete request.', 'درخواست حذف نامعتبر است.'))
        return redirect('hrms:shift_template_list')

    template_name = shift_template.name
    shift_template.delete()
    messages.success(
        request,
        _tr(request, f'Shift template "{template_name}" deleted.', f'الگوی شیفت "{template_name}" حذف شد.'),
    )
    return redirect('hrms:shift_template_list')


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
        form.instance.tenant = tenant
        if form.is_valid():
            form.save()
            messages.success(request, _tr(request, 'Shift version created.', 'نسخه شیفت با موفقیت ایجاد شد.'))
            return redirect('hrms:shift_version_list')
    else:
        form = ShiftVersionForm(tenant=tenant)

    return render(request, 'hrms/shift_version_form.html', {'tenant': tenant, 'form': form, 'is_edit': False})


@login_required
@user_passes_test(is_hrms_manager)
def shift_version_edit(request, version_id):
    tenant = _tenant_or_redirect(request)
    if tenant is None:
        return redirect('main_dashboard')

    version = get_object_or_404(ShiftVersion, tenant=tenant, id=version_id)

    if request.method == 'POST':
        form = ShiftVersionForm(request.POST, instance=version, tenant=tenant)
        form.instance.tenant = tenant
        if form.is_valid():
            form.save()
            messages.success(request, _tr(request, 'Shift version updated.', 'نسخه شیفت با موفقیت ویرایش شد.'))
            return redirect('hrms:shift_version_list')
    else:
        form = ShiftVersionForm(instance=version, tenant=tenant)

    return render(
        request,
        'hrms/shift_version_form.html',
        {
            'tenant': tenant,
            'form': form,
            'is_edit': True,
            'version': version,
        },
    )


@login_required
@user_passes_test(is_hrms_manager)
def shift_version_delete(request, version_id):
    tenant = _tenant_or_redirect(request)
    if tenant is None:
        return redirect('main_dashboard')

    version = get_object_or_404(ShiftVersion, tenant=tenant, id=version_id)
    if request.method != 'POST':
        messages.error(request, _tr(request, 'Invalid delete request.', 'درخواست حذف نامعتبر است.'))
        return redirect('hrms:shift_version_list')

    version_label = f'{version.shift.name} ({version.valid_from} - {version.valid_to})'
    version.delete()
    messages.success(
        request,
        _tr(request, f'Shift version "{version_label}" deleted.', f'نسخه شیفت "{version_label}" حذف شد.'),
    )
    return redirect('hrms:shift_version_list')


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

    _ensure_hrms_employees_from_personnel(tenant)

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

    return render(request, 'hrms/shift_assignment_form.html', {'tenant': tenant, 'form': form, 'is_edit': False})


@login_required
@user_passes_test(is_hrms_manager)
def shift_assignment_edit(request, assignment_id):
    tenant = _tenant_or_redirect(request)
    if tenant is None:
        return redirect('main_dashboard')

    _ensure_hrms_employees_from_personnel(tenant)
    assignment = get_object_or_404(EmployeeShiftAssignment, tenant=tenant, id=assignment_id)

    if request.method == 'POST':
        form = EmployeeShiftAssignmentForm(request.POST, instance=assignment, tenant=tenant)
        if form.is_valid():
            form.save()
            messages.success(request, _tr(request, 'Shift assignment updated.', 'اختصاص شیفت با موفقیت ویرایش شد.'))
            return redirect('hrms:shift_assignment_list')
    else:
        form = EmployeeShiftAssignmentForm(instance=assignment, tenant=tenant)

    return render(
        request,
        'hrms/shift_assignment_form.html',
        {'tenant': tenant, 'form': form, 'assignment': assignment, 'is_edit': True},
    )


@login_required
@user_passes_test(is_hrms_manager)
def shift_assignment_delete(request, assignment_id):
    tenant = _tenant_or_redirect(request)
    if tenant is None:
        return redirect('main_dashboard')

    assignment = get_object_or_404(EmployeeShiftAssignment, tenant=tenant, id=assignment_id)
    if request.method != 'POST':
        messages.error(request, _tr(request, 'Invalid delete request.', 'درخواست حذف نامعتبر است.'))
        return redirect('hrms:shift_assignment_list')

    assignment.delete()
    messages.success(request, _tr(request, 'Shift assignment deleted.', 'اختصاص شیفت حذف شد.'))
    return redirect('hrms:shift_assignment_list')


@login_required
@user_passes_test(is_hrms_manager)
def work_unit_shift_assignment_list(request):
    tenant = _tenant_or_redirect(request)
    if tenant is None:
        return redirect('main_dashboard')

    rows = WorkUnitShiftAssignment.objects.filter(tenant=tenant).select_related('work_unit', 'shift').order_by('-effective_from')
    return render(request, 'hrms/work_unit_shift_assignment_list.html', {'tenant': tenant, 'rows': rows})


@login_required
@user_passes_test(is_hrms_manager)
def work_unit_shift_assignment_create(request):
    tenant = _tenant_or_redirect(request)
    if tenant is None:
        return redirect('main_dashboard')

    if request.method == 'POST':
        form = WorkUnitShiftAssignmentForm(request.POST, tenant=tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = tenant
            obj.save()
            messages.success(request, _tr(request, 'Work-unit shift assignment created.', 'شیفت پیش‌فرض واحد کاری ثبت شد.'))
            return redirect('hrms:work_unit_shift_assignment_list')
    else:
        form = WorkUnitShiftAssignmentForm(tenant=tenant)

    return render(request, 'hrms/work_unit_shift_assignment_form.html', {'tenant': tenant, 'form': form, 'is_edit': False})


@login_required
@user_passes_test(is_hrms_manager)
def work_unit_shift_assignment_edit(request, assignment_id):
    tenant = _tenant_or_redirect(request)
    if tenant is None:
        return redirect('main_dashboard')

    assignment = get_object_or_404(WorkUnitShiftAssignment, tenant=tenant, id=assignment_id)
    if request.method == 'POST':
        form = WorkUnitShiftAssignmentForm(request.POST, instance=assignment, tenant=tenant)
        if form.is_valid():
            form.save()
            messages.success(request, _tr(request, 'Work-unit shift assignment updated.', 'شیفت پیش‌فرض واحد کاری ویرایش شد.'))
            return redirect('hrms:work_unit_shift_assignment_list')
    else:
        form = WorkUnitShiftAssignmentForm(instance=assignment, tenant=tenant)

    return render(
        request,
        'hrms/work_unit_shift_assignment_form.html',
        {'tenant': tenant, 'form': form, 'assignment': assignment, 'is_edit': True},
    )


@login_required
@user_passes_test(is_hrms_manager)
def work_unit_shift_assignment_delete(request, assignment_id):
    tenant = _tenant_or_redirect(request)
    if tenant is None:
        return redirect('main_dashboard')

    assignment = get_object_or_404(WorkUnitShiftAssignment, tenant=tenant, id=assignment_id)
    if request.method != 'POST':
        messages.error(request, _tr(request, 'Invalid delete request.', 'درخواست حذف نامعتبر است.'))
        return redirect('hrms:work_unit_shift_assignment_list')

    assignment.delete()
    messages.success(request, _tr(request, 'Work-unit shift assignment deleted.', 'شیفت پیش‌فرض واحد کاری حذف شد.'))
    return redirect('hrms:work_unit_shift_assignment_list')


@login_required
@user_passes_test(is_hrms_manager)
def work_closure_list(request):
    tenant = _tenant_or_redirect(request)
    if tenant is None:
        return redirect('main_dashboard')

    rows = WorkClosure.objects.filter(tenant=tenant).select_related('work_unit').order_by('-start_date', '-created_at')
    return render(request, 'hrms/work_closure_list.html', {'tenant': tenant, 'rows': rows})


@login_required
@user_passes_test(is_hrms_manager)
def work_closure_create(request):
    tenant = _tenant_or_redirect(request)
    if tenant is None:
        return redirect('main_dashboard')

    if request.method == 'POST':
        form = WorkClosureForm(request.POST, tenant=tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = tenant
            obj.created_by = request.user if request.user.is_authenticated else None
            obj.save()
            messages.success(request, _tr(request, 'Work closure saved.', 'تعطیلی اجباری ثبت شد.'))
            return redirect('hrms:work_closure_list')
    else:
        form = WorkClosureForm(tenant=tenant)

    return render(request, 'hrms/work_closure_form.html', {'tenant': tenant, 'form': form, 'is_edit': False})


@login_required
@user_passes_test(is_hrms_manager)
def work_closure_edit(request, closure_id):
    tenant = _tenant_or_redirect(request)
    if tenant is None:
        return redirect('main_dashboard')

    closure = get_object_or_404(WorkClosure, tenant=tenant, id=closure_id)
    if request.method == 'POST':
        form = WorkClosureForm(request.POST, instance=closure, tenant=tenant)
        if form.is_valid():
            form.save()
            messages.success(request, _tr(request, 'Work closure updated.', 'تعطیلی اجباری ویرایش شد.'))
            return redirect('hrms:work_closure_list')
    else:
        form = WorkClosureForm(instance=closure, tenant=tenant)

    return render(request, 'hrms/work_closure_form.html', {'tenant': tenant, 'form': form, 'closure': closure, 'is_edit': True})


@login_required
@user_passes_test(is_hrms_manager)
def work_closure_delete(request, closure_id):
    tenant = _tenant_or_redirect(request)
    if tenant is None:
        return redirect('main_dashboard')

    closure = get_object_or_404(WorkClosure, tenant=tenant, id=closure_id)
    if request.method != 'POST':
        messages.error(request, _tr(request, 'Invalid delete request.', 'درخواست حذف نامعتبر است.'))
        return redirect('hrms:work_closure_list')

    closure.delete()
    messages.success(request, _tr(request, 'Work closure deleted.', 'تعطیلی اجباری حذف شد.'))
    return redirect('hrms:work_closure_list')


@login_required
@user_passes_test(is_hrms_manager)
def work_calendar_list(request):
    tenant = _tenant_or_redirect(request)
    if tenant is None:
        return redirect('main_dashboard')

    selected_month = request.GET.get('month')
    rows = WorkCalendar.objects.filter(tenant=tenant)
    selected_year = datetime.date.today().year
    if selected_month:
        try:
            year, month = selected_month.split('-')
            selected_year = int(year)
            rows = rows.filter(date__year=selected_year, date__month=int(month))
        except Exception:
            pass

    rows = rows.order_by('-date')
    return render(
        request,
        'hrms/work_calendar_list.html',
        {
            'tenant': tenant,
            'rows': rows,
            'selected_month': selected_month or '',
            'selected_year': selected_year,
        },
    )


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

    return render(request, 'hrms/work_calendar_form.html', {'tenant': tenant, 'form': form, 'is_edit': False})


@login_required
@user_passes_test(is_hrms_manager)
def work_calendar_edit(request, row_id):
    tenant = _tenant_or_redirect(request)
    if tenant is None:
        return redirect('main_dashboard')

    row = get_object_or_404(WorkCalendar, tenant=tenant, id=row_id)
    if request.method == 'POST':
        form = WorkCalendarForm(request.POST, instance=row)
        if form.is_valid():
            form.save()
            messages.success(request, _tr(request, 'Work calendar day updated.', 'روز تقویم کاری بروزرسانی شد.'))
            return redirect('hrms:work_calendar_list')
    else:
        form = WorkCalendarForm(instance=row)

    return render(request, 'hrms/work_calendar_form.html', {'tenant': tenant, 'form': form, 'is_edit': True, 'row': row})


@login_required
@user_passes_test(is_hrms_manager)
def work_calendar_delete(request, row_id):
    tenant = _tenant_or_redirect(request)
    if tenant is None:
        return redirect('main_dashboard')

    row = get_object_or_404(WorkCalendar, tenant=tenant, id=row_id)
    if request.method != 'POST':
        messages.error(request, _tr(request, 'Invalid delete request.', 'درخواست حذف نامعتبر است.'))
        return redirect('hrms:work_calendar_list')

    row.delete()
    messages.success(request, _tr(request, 'Work calendar day deleted.', 'روز تقویم کاری حذف شد.'))
    return redirect('hrms:work_calendar_list')


@login_required
@user_passes_test(is_hrms_manager)
def work_calendar_delete_year(request):
    tenant = _tenant_or_redirect(request)
    if tenant is None:
        return redirect('main_dashboard')

    if request.method != 'POST':
        messages.error(request, _tr(request, 'Invalid delete request.', 'درخواست حذف نامعتبر است.'))
        return redirect('hrms:work_calendar_list')

    year_raw = (request.POST.get('year') or '').strip()
    try:
        year = int(year_raw)
    except Exception:
        messages.error(request, _tr(request, 'Please provide a valid year.', 'لطفا سال معتبر وارد کنید.'))
        return redirect('hrms:work_calendar_list')

    deleted_count, _ = WorkCalendar.objects.filter(tenant=tenant, date__year=year).delete()
    messages.success(
        request,
        _tr(
            request,
            f'All work-calendar rows for {year} were deleted ({deleted_count} rows).',
            f'تمام ردیف‌های تقویم کاری سال {year} حذف شد ({deleted_count} ردیف).',
        ),
    )
    return redirect('hrms:work_calendar_list')


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
            custom_weekday_minutes = {
                int(day) for day in (form.cleaned_data.get('custom_weekday_minutes') or [])
            }
            custom_work_minutes = form.cleaned_data.get('custom_work_minutes')
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
                    elif custom_weekday_minutes and current_date.weekday() in custom_weekday_minutes:
                        minutes = int(custom_work_minutes or default_work_minutes)
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

    policies = OvertimePolicy.objects.filter(tenant=tenant).prefetch_related('rate_rules').order_by('-effective_from')
    return render(request, 'hrms/overtime_policy_list.html', {'tenant': tenant, 'policies': policies})


@login_required
@user_passes_test(is_hrms_manager)
def overtime_policy_create(request):
    tenant = _tenant_or_redirect(request)
    if tenant is None:
        return redirect('main_dashboard')

    if request.method == 'POST':
        form = OvertimePolicyForm(request.POST, tenant=tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = tenant
            obj.save()
            messages.success(request, _tr(request, 'Overtime policy created.', 'قانون اضافه‌کاری با موفقیت ایجاد شد.'))
            return redirect('hrms:overtime_policy_list')
    else:
        form = OvertimePolicyForm(tenant=tenant)

    return render(request, 'hrms/overtime_policy_form.html', {'tenant': tenant, 'form': form, 'is_edit': False})


@login_required
@user_passes_test(is_hrms_manager)
def overtime_policy_edit(request, policy_id):
    tenant = _tenant_or_redirect(request)
    if tenant is None:
        return redirect('main_dashboard')

    policy = get_object_or_404(OvertimePolicy, id=policy_id, tenant=tenant)

    if request.method == 'POST':
        form = OvertimePolicyForm(request.POST, instance=policy, tenant=tenant)
        if form.is_valid():
            form.save()
            messages.success(request, _tr(request, 'Overtime policy updated.', 'قانون اضافه‌کاری با موفقیت ویرایش شد.'))
            return redirect('hrms:overtime_policy_list')
    else:
        form = OvertimePolicyForm(instance=policy, tenant=tenant)

    return render(request, 'hrms/overtime_policy_form.html', {'tenant': tenant, 'form': form, 'is_edit': True, 'policy': policy})


@login_required
@user_passes_test(is_hrms_manager)
def overtime_policy_delete(request, policy_id):
    tenant = _tenant_or_redirect(request)
    if tenant is None:
        return redirect('main_dashboard')

    policy = get_object_or_404(OvertimePolicy, id=policy_id, tenant=tenant)
    if request.method != 'POST':
        messages.error(request, _tr(request, 'Invalid delete request.', 'درخواست حذف نامعتبر است.'))
        return redirect('hrms:overtime_policy_list')

    policy_name = policy.name
    policy.delete()
    messages.success(request, _tr(request, f'Overtime policy "{policy_name}" deleted.', f'قانون اضافه‌کاری "{policy_name}" حذف شد.'))
    return redirect('hrms:overtime_policy_list')


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

    return render(request, 'hrms/overtime_rule_form.html', {'tenant': tenant, 'policy': policy, 'form': form, 'is_edit': False})


@login_required
@user_passes_test(is_hrms_manager)
def overtime_rule_edit(request, policy_id, rule_id):
    tenant = _tenant_or_redirect(request)
    if tenant is None:
        return redirect('main_dashboard')

    policy = get_object_or_404(OvertimePolicy, id=policy_id, tenant=tenant)
    rule = get_object_or_404(OvertimeRateRule, id=rule_id, policy=policy)

    if request.method == 'POST':
        form = OvertimeRateRuleForm(request.POST, instance=rule)
        if form.is_valid():
            form.save()
            messages.success(request, _tr(request, 'Overtime rate rule updated.', 'قانون نرخ اضافه‌کاری ویرایش شد.'))
            return redirect('hrms:overtime_policy_list')
    else:
        form = OvertimeRateRuleForm(instance=rule)

    return render(
        request,
        'hrms/overtime_rule_form.html',
        {
            'tenant': tenant,
            'policy': policy,
            'form': form,
            'is_edit': True,
            'rule': rule,
        },
    )


@login_required
@user_passes_test(is_hrms_manager)
def overtime_rule_delete(request, policy_id, rule_id):
    tenant = _tenant_or_redirect(request)
    if tenant is None:
        return redirect('main_dashboard')

    policy = get_object_or_404(OvertimePolicy, id=policy_id, tenant=tenant)
    rule = get_object_or_404(OvertimeRateRule, id=rule_id, policy=policy)

    if request.method != 'POST':
        messages.error(request, _tr(request, 'Invalid delete request.', 'درخواست حذف نامعتبر است.'))
        return redirect('hrms:overtime_policy_list')

    rule_label = f'{rule.get_day_type_display()} / {rule.get_overtime_type_display()}'
    rule.delete()
    messages.success(request, _tr(request, f'Overtime rule "{rule_label}" deleted.', f'قانون اضافه‌کاری "{rule_label}" حذف شد.'))
    return redirect('hrms:overtime_policy_list')
