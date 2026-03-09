from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponse
from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from .models import Attendance, AttendanceAIInsight, Timesheet, AttendanceChangeLog
from django.utils import timezone
from django.utils.translation import gettext as _
from django.contrib.auth.models import User
from apps.hr_personnel.models import Employee, LeaveAIInsight, LeaveRequest
from apps.expenses.utils import render_to_pdf
import base64
import calendar
import datetime
import json
import logging
import time

try:
    from apps.hrms.models import Company, EmployeeShiftAssignment, ShiftTemplate, ShiftVersion, WorkCalendar, resolve_shift_window
except Exception:  # pragma: no cover - hrms may be unavailable in some environments
    Company = EmployeeShiftAssignment = ShiftTemplate = ShiftVersion = WorkCalendar = None
    resolve_shift_window = None


logger = logging.getLogger(__name__)
SLOW_SUPERVISOR_VIEW_MS = 1200


def _resolve_company_for_org(org):
    if not org or Company is None:
        return None
    try:
        return Company.objects.filter(organization=org).first()
    except Exception:
        return None


def _resolve_hrms_shift_context(employee, work_date, tenant):
    if employee is None or tenant is None:
        return {
            'calendar_day': None,
            'assignment': None,
            'shift_version': None,
            'scheduled_start': None,
            'scheduled_end': None,
            'required_minutes': 480,
        }

    calendar_day = None
    assignment = None
    shift_version = None
    scheduled_start = None
    scheduled_end = None
    required_minutes = 480

    if WorkCalendar is not None:
        calendar_day = WorkCalendar.objects.filter(tenant=tenant, date=work_date).first()
        if calendar_day is not None:
            required_minutes = int(calendar_day.standard_work_minutes or 0)

    if EmployeeShiftAssignment is not None and ShiftVersion is not None and resolve_shift_window is not None:
        assignment = (
            EmployeeShiftAssignment.objects.filter(
                tenant=tenant,
                employee__personnel_employee=employee,
                is_active=True,
                effective_from__lte=work_date,
            )
            .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=work_date))
            .select_related('shift')
            .order_by('-effective_from')
            .first()
        )
        if assignment is not None:
            shift_version = (
                ShiftVersion.objects.filter(
                    tenant=tenant,
                    shift=assignment.shift,
                    valid_from__lte=work_date,
                    valid_to__gte=work_date,
                )
                .order_by('-valid_from')
                .first()
            )
            if shift_version is not None:
                scheduled_start, scheduled_end = resolve_shift_window(
                    shift_version,
                    work_date,
                    timezone.get_current_timezone(),
                )
                shift_required = int(shift_version.required_work_minutes or 0)
                if required_minutes > 0:
                    required_minutes = min(required_minutes, shift_required) if shift_required > 0 else required_minutes
                else:
                    required_minutes = shift_required

    if required_minutes < 0:
        required_minutes = 0

    return {
        'calendar_day': calendar_day,
        'assignment': assignment,
        'shift_version': shift_version,
        'scheduled_start': scheduled_start,
        'scheduled_end': scheduled_end,
        'required_minutes': required_minutes,
    }


def _worked_hours(clock_in, clock_out):
    if not clock_in or not clock_out:
        return 0.0
    seconds = (clock_out - clock_in).total_seconds()
    if seconds <= 0:
        return 0.0
    return seconds / 3600


def _worked_hours_from_attendance(attendance):
    total_hours = _worked_hours(attendance.clock_in, attendance.clock_out)
    if total_hours <= 0:
        return 0.0

    if attendance.lunch_out and attendance.lunch_in and attendance.lunch_in > attendance.lunch_out:
        break_seconds = (attendance.lunch_in - attendance.lunch_out).total_seconds()
        total_hours -= max(break_seconds / 3600, 0)

    return max(total_hours, 0.0)


def _attendance_next_event(attendance):
    if not attendance.clock_in:
        return 'clock_in'
    if attendance.clock_out:
        return 'completed'
    if attendance.clock_in and not attendance.lunch_out:
        return 'lunch_out'
    if attendance.lunch_out and not attendance.lunch_in:
        return 'lunch_in'
    if attendance.lunch_in and not attendance.clock_out:
        return 'clock_out'
    return 'completed'


def _build_attendance_overview(request, selected_date):
    org = getattr(request, 'organization', None)
    employees_qs = Employee.objects.select_related('user', 'reporting_manager').all()
    if org:
        employees_qs = employees_qs.filter(organization=org)

    employee_ids = list(employees_qs.values_list('id', flat=True))
    user_ids = list(employees_qs.exclude(user__isnull=True).values_list('user_id', flat=True))

    today_records = Attendance.objects.filter(date=selected_date).filter(
        Q(employee_id__in=employee_ids) | Q(user_id__in=user_ids)
    ).distinct()
    checked_in_count = today_records.filter(clock_in__isnull=False).count()
    checked_out_count = today_records.filter(clock_out__isnull=False).count()

    total_employees = employees_qs.count()
    absent_count = max(total_employees - checked_in_count, 0)

    total_worked_hours_today = 0.0
    for row in today_records:
        total_worked_hours_today += _worked_hours_from_attendance(row)

    divisor = checked_out_count or checked_in_count or 1
    avg_worked_hours_today = total_worked_hours_today / divisor

    week_start = selected_date - datetime.timedelta(days=6)
    week_days = [week_start + datetime.timedelta(days=i) for i in range(7)]
    weekly_records = Attendance.objects.filter(
        Q(employee_id__in=employee_ids) | Q(user_id__in=user_ids),
        date__range=(week_start, selected_date),
        clock_in__isnull=False,
        clock_out__isnull=False,
    ).distinct().order_by('date')

    daily_hours = {day: 0.0 for day in week_days}
    for rec in weekly_records:
        daily_hours[rec.date] = daily_hours.get(rec.date, 0.0) + _worked_hours_from_attendance(rec)

    weekly_hours = [
        {
            'date': day,
            'hours': round(daily_hours.get(day, 0.0), 1),
        }
        for day in week_days
    ]
    peak_day = max(weekly_hours, key=lambda item: item['hours']) if weekly_hours else None
    peak_hours = float(peak_day['hours']) if peak_day else 0.0
    for row in weekly_hours:
        if peak_hours > 0:
            row['width_percent'] = round((float(row['hours']) / peak_hours) * 100, 1)
        else:
            row['width_percent'] = 0

    core_fields = [
        'employee_id', 'first_name', 'last_name', 'national_id', 'passport_no', 'nationality', 'gender',
        'date_of_birth', 'marital_status', 'company_id', 'branch_id', 'department_id', 'position_id',
        'employment_type', 'hire_date', 'probation_end_date', 'contract_start', 'contract_end',
        'reporting_manager', 'bank_name', 'iban', 'payment_method', 'basic_salary', 'currency',
        'omani_or_expat',
    ]

    employees = list(employees_qs)
    complete_profiles = 0
    top_missing = []
    for employee in employees:
        missing_count = 0
        for field in core_fields:
            value = getattr(employee, field, None)
            if value in (None, ''):
                missing_count += 1

        if missing_count == 0:
            complete_profiles += 1
        if missing_count > 0:
            top_missing.append({'employee': employee, 'missing_count': missing_count})

    top_missing.sort(key=lambda item: item['missing_count'], reverse=True)
    top_missing = top_missing[:5]

    total_basic_salary = sum(float(getattr(emp, 'basic_salary', 0) or 0) for emp in employees)

    attendance_ai_alerts = AttendanceAIInsight.objects.filter(
        employee__organization=org,
        score__gte=70,
    ).count() if org else AttendanceAIInsight.objects.filter(score__gte=70).count()

    pending_leave_requests = LeaveRequest.objects.filter(
        employee__organization=org,
        status=LeaveRequest.Status.PENDING,
    ).count() if org else LeaveRequest.objects.filter(status=LeaveRequest.Status.PENDING).count()

    leave_risk_alerts = LeaveAIInsight.objects.filter(
        leave_request__employee__organization=org,
        insight_type=LeaveAIInsight.InsightType.ABUSE_DETECTION,
        score__gte=70,
    ).count() if org else LeaveAIInsight.objects.filter(
        insight_type=LeaveAIInsight.InsightType.ABUSE_DETECTION,
        score__gte=70,
    ).count()

    return {
        'total_employees': total_employees,
        'checked_in_count': checked_in_count,
        'checked_out_count': checked_out_count,
        'absent_count': absent_count,
        'total_worked_hours_today': round(total_worked_hours_today, 1),
        'avg_worked_hours_today': round(avg_worked_hours_today, 1),
        'weekly_hours': weekly_hours,
        'peak_day': peak_day,
        'complete_profiles': complete_profiles,
        'incomplete_profiles': max(total_employees - complete_profiles, 0),
        'profile_completion_percent': round((complete_profiles / total_employees) * 100, 1) if total_employees else 0,
        'employees_missing_core': top_missing,
        'total_basic_salary': round(total_basic_salary, 3),
        'attendance_ai_alerts': attendance_ai_alerts,
        'pending_leave_requests': pending_leave_requests,
        'leave_risk_alerts': leave_risk_alerts,
    }


def _resolve_capture_fields(request, default_source='web', default_mode='web_punch'):
    source = str(request.POST.get('source') or default_source).lower()
    capture_mode = str(request.POST.get('capture_mode') or default_mode).lower()
    device_id = request.POST.get('device_id')

    valid_sources = {choice[0] for choice in Attendance.Source.choices}
    valid_modes = {choice[0] for choice in Attendance.CaptureMode.choices}

    if source not in valid_sources:
        source = default_source
    if capture_mode not in valid_modes:
        capture_mode = default_mode

    return source, capture_mode, device_id


def _resolve_manual_punch_datetime(request, field_name, selected_date):
    raw_value = str(request.POST.get(field_name, '') or '').strip()
    if not raw_value:
        return timezone.now(), False, True

    try:
        selected_time = datetime.time.fromisoformat(raw_value)
    except ValueError:
        return None, True, False

    naive_dt = datetime.datetime.combine(selected_date, selected_time)
    aware_dt = timezone.make_aware(naive_dt, timezone.get_current_timezone())
    return aware_dt, True, True


def _upsert_timesheet_from_attendance(attendance):
    employee = attendance.employee or _employee_for_user(attendance.user)
    if not employee:
        return

    worked_hours = _worked_hours_from_attendance(attendance)
    overtime_hours = max(worked_hours - 8, 0)
    late_minutes = 0
    early_leave_minutes = 0

    tenant = _resolve_company_for_org(getattr(employee, 'organization', None))
    shift_ctx = _resolve_hrms_shift_context(employee, attendance.date, tenant)
    calendar_day = shift_ctx.get('calendar_day')
    required_minutes = int(shift_ctx.get('required_minutes') or 0)

    if worked_hours > 0:
        if required_minutes <= 0:
            overtime_hours = worked_hours
        else:
            overtime_hours = max(worked_hours - (required_minutes / 60.0), 0)

    if attendance.shift and attendance.clock_in and attendance.clock_out:
        in_local = timezone.localtime(attendance.clock_in)
        out_local = timezone.localtime(attendance.clock_out)

        scheduled_in = datetime.datetime.combine(attendance.date, attendance.shift.start_time, tzinfo=in_local.tzinfo)
        scheduled_out = datetime.datetime.combine(attendance.date, attendance.shift.end_time, tzinfo=out_local.tzinfo)

        late_threshold = scheduled_in + datetime.timedelta(minutes=attendance.shift.grace_in or 0)
        early_threshold = scheduled_out - datetime.timedelta(minutes=attendance.shift.grace_out or 0)

        if in_local > late_threshold:
            late_minutes = int((in_local - late_threshold).total_seconds() // 60)
        if out_local < early_threshold:
            early_leave_minutes = int((early_threshold - out_local).total_seconds() // 60)
    elif attendance.clock_in and attendance.clock_out and required_minutes > 0:
        scheduled_start = shift_ctx.get('scheduled_start')
        if scheduled_start is None:
            scheduled_start = timezone.localtime(attendance.clock_in).replace(second=0, microsecond=0)
        scheduled_end = scheduled_start + datetime.timedelta(minutes=required_minutes)
        in_local = timezone.localtime(attendance.clock_in)
        out_local = timezone.localtime(attendance.clock_out)
        if in_local > scheduled_start:
            late_minutes = int((in_local - scheduled_start).total_seconds() // 60)
        if out_local < scheduled_end:
            early_leave_minutes = int((scheduled_end - out_local).total_seconds() // 60)

    if calendar_day is not None and calendar_day.day_type in {'weekend', 'public_holiday'}:
        late_minutes = 0
        early_leave_minutes = 0

    Timesheet.objects.update_or_create(
        employee=employee,
        work_date=attendance.date,
        defaults={
            'worked_hours': round(worked_hours, 2),
            'overtime_hours': round(overtime_hours, 2),
            'late_minutes': max(late_minutes, 0),
            'early_leave_minutes': max(early_leave_minutes, 0),
            'absence_flag': not bool(attendance.clock_in),
            'source_attendance': attendance,
        },
    )


def _parse_location_from_request(request):
    lat = request.POST.get('latitude')
    lng = request.POST.get('longitude')
    if not lat or not lng:
        return None, None
    return lat, lng


def _save_location(attendance, lat, lng, event_type):
    if not lat or not lng:
        return
    attendance.latitude = lat
    attendance.longitude = lng
    attendance.location_lat = lat
    attendance.location_lng = lng
    if event_type == 'in':
        attendance.clock_in_latitude = lat
        attendance.clock_in_longitude = lng
    elif event_type == 'out':
        attendance.clock_out_latitude = lat
        attendance.clock_out_longitude = lng
    elif event_type == 'lunch_out':
        attendance.lunch_out_latitude = lat
        attendance.lunch_out_longitude = lng
    elif event_type == 'lunch_in':
        attendance.lunch_in_latitude = lat
        attendance.lunch_in_longitude = lng


def _log_attendance_change(attendance, actor, field_name, action_type, old_value, new_value, note=''):
    AttendanceChangeLog.objects.create(
        attendance=attendance,
        field_name=field_name,
        action_type=action_type,
        old_value=old_value,
        new_value=new_value,
        performed_by=actor,
        note=note,
    )


def _parse_supervisor_action_datetime(selected_date, raw_value):
    try:
        parsed_time = datetime.time.fromisoformat(str(raw_value or '').strip())
    except ValueError:
        return None
    naive_dt = datetime.datetime.combine(selected_date, parsed_time)
    return timezone.make_aware(naive_dt, timezone.get_current_timezone())


def _format_hm(value):
    if not value:
        return '-'
    return timezone.localtime(value).strftime('%H:%M')


def _employee_for_user(user):
    if not user:
        return None
    try:
        return user.employee
    except Exception:
        return None


def _find_attendance(selected_date, user=None, employee=None):
    base_qs = Attendance.objects.filter(date=selected_date)
    if employee is not None:
        attendance = base_qs.filter(employee=employee).first()
        if attendance:
            return attendance
    if user is not None:
        return base_qs.filter(user=user).first()
    return None


def _get_or_create_attendance(selected_date, user=None, employee=None):
    attendance = _find_attendance(selected_date, user=user, employee=employee)
    if attendance:
        update_fields = []
        if employee is not None and attendance.employee_id is None:
            attendance.employee = employee
            update_fields.append('employee')
        if user is not None and attendance.user_id is None:
            attendance.user = user
            update_fields.append('user')
        if update_fields:
            attendance.save(update_fields=update_fields)
        return attendance, False
    return Attendance.objects.create(user=user, employee=employee, date=selected_date), True


def _redirect_supervisor_by_date(date_value):
    if date_value:
        return redirect(f"/attendance/supervisor/?date={date_value}")
    return redirect('hr_attendance:supervisor_panel')


def _is_target_in_scope(request, target):
    if request.user.is_superuser:
        return True
    try:
        if request.user.profile.organization_id != target.profile.organization_id:
            return False
    except Exception:
        return False

    role = getattr(request.user.profile, 'role', 'user')
    if role == 'supervisor':
        return target.profile.supervisor_id == request.user.id and not target.is_superuser and getattr(target.profile, 'role', 'user') != 'admin'
    return True


def _is_employee_in_scope(request, employee):
    if request.user.is_superuser:
        return True

    request_org_id = getattr(getattr(request.user, 'profile', None), 'organization_id', None)
    if not request_org_id or employee.organization_id != request_org_id:
        return False

    role = getattr(getattr(request.user, 'profile', None), 'role', 'user')
    if role != 'supervisor':
        return True

    current_employee = _employee_for_user(request.user)
    if not current_employee:
        return False

    if employee.user_id:
        target_user = employee.user
        target_role = getattr(getattr(target_user, 'profile', None), 'role', 'user')
        if target_user.is_superuser or target_role == 'admin':
            return False
        return getattr(getattr(target_user, 'profile', None), 'supervisor_id', None) == request.user.id

    is_assigned_to_supervisor = (
        employee.reporting_manager_id == current_employee.id
        or getattr(employee.work_unit, 'supervisor_id', None) == current_employee.id
    )
    if is_assigned_to_supervisor:
        return True

    # Fallback: allow supervisors to manage org employees that are still unassigned.
    return employee.reporting_manager_id is None and getattr(employee.work_unit, 'supervisor_id', None) is None


def _clock_redirect(request):
    if request.POST.get('next') == 'quick_success':
        return redirect('hr_attendance:quick_clock_success')
    if request.POST.get('next') == 'clock_center':
        return redirect('hr_attendance:clock_center')
    if request.POST.get('next') == 'quick':
        return redirect('hr_attendance:quick_clock')
    if not is_supervisor_or_admin(request.user):
        return redirect('hr_attendance:quick_clock')
    return redirect('hr_attendance:hub')


def _clock_center_context(request, selected_date):
    employee = _employee_for_user(request.user)
    attendance, created = _get_or_create_attendance(selected_date, user=request.user, employee=employee)
    recent_attendances = Attendance.objects.filter(user=request.user).order_by('-date')[:10]
    next_event = _attendance_next_event(attendance)

    require_photo = True
    if hasattr(request.user, 'profile'):
        require_photo = request.user.profile.require_photo

    return {
        'attendance': attendance,
        'recent_attendances': recent_attendances,
        'today': selected_date,
        'require_photo': require_photo,
        'next_event': next_event,
    }


def _monthly_attendance_summary(user):
    today = timezone.localtime(timezone.now()).date()
    month_start = today.replace(day=1)
    month_end = today

    employee = _employee_for_user(user)
    records = Attendance.objects.filter(date__range=(month_start, month_end))
    if employee:
        records = records.filter(Q(employee=employee) | Q(user=user)).distinct()
    else:
        records = records.filter(user=user)
    records = records.order_by('date')
    days_present = records.filter(clock_in__isnull=False).count()
    days_absent = max((month_end - month_start).days + 1 - days_present, 0)
    total_worked_hours = 0.0
    for row in records:
        total_worked_hours += _worked_hours_from_attendance(row)

    return {
        'days_present': days_present,
        'days_absent': days_absent,
        'total_worked_hours': round(total_worked_hours, 2),
        'month_label': month_start.strftime('%Y-%m'),
    }

def is_supervisor_or_admin(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    try:
        return getattr(user.profile, 'role', 'user') in ['admin', 'supervisor']
    except Exception:
        return False


def _attendance_users_for_manager(request):
    org = None
    current_employee = None
    try:
        org = request.user.profile.organization
    except Exception:
        org = None

    try:
        current_employee = request.user.employee
    except Exception:
        current_employee = None

    users_qs = User.objects.filter(employee__isnull=False).select_related('profile', 'employee').order_by('username')
    if not request.user.is_superuser and org:
        users_qs = users_qs.filter(employee__organization=org)
    elif not request.user.is_superuser and not org:
        users_qs = User.objects.none()

    if not request.user.is_superuser:
        try:
            role = getattr(request.user.profile, 'role', 'user')
        except Exception:
            role = 'user'
        if role == 'supervisor':
            scope_filter = Q(profile__supervisor=request.user)
            if current_employee:
                scope_filter |= Q(employee__work_unit__supervisor=current_employee)
            users_qs = users_qs.filter(scope_filter).exclude(profile__role='admin').exclude(is_superuser=True).distinct()

    return users_qs


def _scoped_unlinked_employees(request, org, current_employee, role):
    unlinked_employees = Employee.objects.filter(user__isnull=True).order_by('first_name', 'last_name')
    if not request.user.is_superuser and org:
        unlinked_employees = unlinked_employees.filter(organization=org)
    elif not request.user.is_superuser and not org:
        return Employee.objects.none()

    if not request.user.is_superuser and role == 'supervisor' and current_employee:
        unlinked_employees = unlinked_employees.filter(
            Q(work_unit__supervisor=current_employee)
            | Q(reporting_manager=current_employee)
            | (Q(reporting_manager__isnull=True) & Q(work_unit__isnull=True))
            | (Q(reporting_manager__isnull=True) & Q(work_unit__supervisor__isnull=True))
        )
    return unlinked_employees


def _attendance_maps_for_targets(selected_date, users, employees):
    user_ids = [u.id for u in users if u is not None]
    employee_ids = [e.id for e in employees if e is not None]

    if not user_ids and not employee_ids:
        return {}, {}

    attendances = Attendance.objects.filter(date=selected_date).filter(
        Q(user_id__in=user_ids) | Q(employee_id__in=employee_ids)
    ).select_related('user', 'employee')

    by_user_id = {}
    by_employee_id = {}
    for attendance in attendances:
        if attendance.user_id and attendance.user_id not in by_user_id:
            by_user_id[attendance.user_id] = attendance
        if attendance.employee_id and attendance.employee_id not in by_employee_id:
            by_employee_id[attendance.employee_id] = attendance

    return by_user_id, by_employee_id


def _history_payloads_for_attendances(attendance_ids, per_attendance_limit=20):
    if not attendance_ids:
        return {}

    payloads = {}
    logs = AttendanceChangeLog.objects.filter(attendance_id__in=attendance_ids).select_related('performed_by').order_by('attendance_id', '-performed_at')
    for log in logs:
        bucket = payloads.setdefault(log.attendance_id, [])
        if len(bucket) >= per_attendance_limit:
            continue
        bucket.append(
            {
                'field': log.get_field_name_display(),
                'action': log.get_action_type_display(),
                'old_value': _format_hm(log.old_value),
                'new_value': _format_hm(log.new_value),
                'by': (log.performed_by.get_full_name() or log.performed_by.username) if log.performed_by else '-',
                'performed_at': timezone.localtime(log.performed_at).strftime('%Y-%m-%d %H:%M'),
                'note': log.note,
            }
        )
    return payloads


def _parse_month_start(month_value, fallback_date):
    if not month_value:
        return fallback_date.replace(day=1)
    try:
        year_str, month_str = str(month_value).split('-', 1)
        year = int(year_str)
        month = int(month_str)
        return datetime.date(year, month, 1)
    except Exception:
        return fallback_date.replace(day=1)


def _shift_month(date_value, delta_months):
    month_index = (date_value.month - 1) + delta_months
    year = date_value.year + (month_index // 12)
    month = (month_index % 12) + 1
    day = min(date_value.day, calendar.monthrange(year, month)[1])
    return datetime.date(year, month, day)


@login_required
def attendance_hub(request):
    selected_date = timezone.localtime(timezone.now()).date()
    employee = _employee_for_user(request.user)
    attendance, created = _get_or_create_attendance(selected_date, user=request.user, employee=employee)
    is_manager = is_supervisor_or_admin(request.user)

    next_event = _attendance_next_event(attendance)
    if next_event == 'clock_in':
        current_status = _('Not Clocked In')
    elif next_event == 'lunch_out':
        current_status = _('Working (Morning Shift)')
    elif next_event == 'lunch_in':
        current_status = _('On Lunch Break')
    elif next_event == 'clock_out':
        current_status = _('Working (Afternoon Shift)')
    else:
        current_status = _('Completed')

    context = {
        'today': selected_date,
        'attendance': attendance,
        'summary': _monthly_attendance_summary(request.user),
        'is_manager': is_manager,
        'current_status': current_status,
    }

    if is_manager:
        overview = _build_attendance_overview(request, selected_date)
        context.update(
            {
                'total_employees': overview['total_employees'],
                'checked_in_count': overview['checked_in_count'],
                'checked_out_count': overview['checked_out_count'],
                'absent_count': overview['absent_count'],
            }
        )

    return render(request, 'hr_attendance/attendance_hub.html', context)

@login_required
def attendance_dashboard(request):
    if not is_supervisor_or_admin(request.user):
        return redirect('hr_attendance:quick_clock')

    # Use organization timezone activated in middleware
    date_str = request.GET.get('date')
    if date_str:
        try:
            selected_date = datetime.date.fromisoformat(date_str)
        except Exception:
            selected_date = timezone.localtime(timezone.now()).date()
    else:
        selected_date = timezone.localtime(timezone.now()).date()
    overview = _build_attendance_overview(request, selected_date)

    context = {
        'today': selected_date,
        **overview,
    }
    return render(request, 'hr_attendance/dashboard.html', context)


@login_required
def attendance_clock_center(request):
    if not is_supervisor_or_admin(request.user):
        return redirect('hr_attendance:quick_clock')

    selected_date = timezone.localtime(timezone.now()).date()
    context = _clock_center_context(request, selected_date)
    return render(request, 'hr_attendance/clock_center.html', context)


@login_required
@user_passes_test(is_supervisor_or_admin)
def attendance_card(request):
    today = timezone.localtime(timezone.now()).date()
    month_start = _parse_month_start(request.GET.get('month') or request.POST.get('month'), today)
    month_days = calendar.monthrange(month_start.year, month_start.month)[1]
    month_end = month_start.replace(day=month_days)

    org = getattr(request, 'organization', None)
    if org is None:
        org = getattr(getattr(request.user, 'profile', None), 'organization', None)

    employees_qs = Employee.objects.select_related('user', 'reporting_manager').order_by('first_name', 'last_name')
    if not request.user.is_superuser and org:
        employees_qs = employees_qs.filter(organization=org)
    elif not request.user.is_superuser and not org:
        employees_qs = Employee.objects.none()

    employees = list(employees_qs)
    employee_map = {str(employee.id): employee for employee in employees}

    selected_employee_id = str(request.GET.get('employee_id') or request.POST.get('employee_id') or '').strip()
    legacy_user_id = str(request.GET.get('user_id') or request.POST.get('user_id') or '').strip()

    selected_employee = employee_map.get(selected_employee_id)
    if selected_employee is None and legacy_user_id:
        selected_employee = next((employee for employee in employees if str(getattr(employee, 'user_id', '')) == legacy_user_id), None)
    if selected_employee is None and employees:
        selected_employee = employees[0]

    role = getattr(getattr(request.user, 'profile', None), 'role', 'user')
    current_employee = _employee_for_user(request.user)

    if request.method == 'POST' and request.POST.get('action') == 'connect_supervisor':
        if role != 'supervisor' or current_employee is None:
            messages.error(request, _("Only supervisors can perform this action."))
        elif selected_employee is None:
            messages.error(request, _("Please select a valid employee."))
        elif selected_employee.id == current_employee.id:
            messages.error(request, _("You cannot assign yourself as your own manager."))
        elif (
            not request.user.is_superuser
            and getattr(selected_employee, 'organization_id', None)
            != getattr(getattr(request.user, 'profile', None), 'organization_id', None)
        ):
            messages.error(request, _("You cannot modify employees outside your organization."))
        else:
            selected_employee.reporting_manager = current_employee
            selected_employee.save(update_fields=['reporting_manager'])
            messages.success(request, _("Employee connected to this supervisor successfully."))
        if selected_employee:
            return redirect(
                f"/attendance/card/?employee_id={selected_employee.id}&month={month_start.strftime('%Y-%m')}"
            )
        return redirect(f"/attendance/card/?month={month_start.strftime('%Y-%m')}")

    rows = []
    summary = {
        'days_present': 0,
        'days_absent': 0,
        'total_worked_hours': 0.0,
    }

    if selected_employee:
        attendance_filter = Q(employee=selected_employee)
        if selected_employee.user_id:
            attendance_filter |= Q(user_id=selected_employee.user_id)

        attendances = Attendance.objects.filter(
            date__range=(month_start, month_end),
        ).filter(attendance_filter).distinct().order_by('date')
        attendance_by_date = {item.date: item for item in attendances}

        timesheets = Timesheet.objects.filter(
            employee=selected_employee,
            work_date__range=(month_start, month_end),
        )
        timesheet_by_date = {item.work_date: item for item in timesheets}

        for day in range(1, month_days + 1):
            current_date = month_start.replace(day=day)
            attendance = attendance_by_date.get(current_date)
            timesheet = timesheet_by_date.get(current_date)

            worked_hours = float(getattr(timesheet, 'worked_hours', 0) or 0)
            if attendance and attendance.clock_in:
                summary['days_present'] += 1
            else:
                summary['days_absent'] += 1
            summary['total_worked_hours'] += worked_hours

            rows.append(
                {
                    'date': current_date,
                    'attendance': attendance,
                    'timesheet': timesheet,
                    'worked_hours': round(worked_hours, 2),
                }
            )

    context = {
        'employees': employees,
        'selected_employee': selected_employee,
        'selected_employee_id': str(selected_employee.id) if selected_employee else '',
        'can_connect_selected': bool(
            role == 'supervisor'
            and current_employee is not None
            and selected_employee is not None
            and selected_employee.id != current_employee.id
            and selected_employee.reporting_manager_id != current_employee.id
        ),
        'month_value': month_start.strftime('%Y-%m'),
        'rows': rows,
        'summary': {
            'days_present': summary['days_present'],
            'days_absent': summary['days_absent'],
            'total_worked_hours': round(summary['total_worked_hours'], 2),
        },
        'pdf_url': (
            f"{reverse('hr_attendance:attendance_card_pdf')}?employee_id={selected_employee.id}&month={month_start.strftime('%Y-%m')}"
            if selected_employee else f"{reverse('hr_attendance:attendance_card_pdf')}?month={month_start.strftime('%Y-%m')}"
        ),
    }
    return render(request, 'hr_attendance/attendance_card.html', context)


@login_required
@user_passes_test(is_supervisor_or_admin)
def attendance_card_pdf(request):
    today = timezone.localtime(timezone.now()).date()
    month_start = _parse_month_start(request.GET.get('month'), today)
    month_days = calendar.monthrange(month_start.year, month_start.month)[1]
    month_end = month_start.replace(day=month_days)

    org = getattr(request, 'organization', None)
    if org is None:
        org = getattr(getattr(request.user, 'profile', None), 'organization', None)

    employees_qs = Employee.objects.select_related('user').order_by('first_name', 'last_name')
    if not request.user.is_superuser and org:
        employees_qs = employees_qs.filter(organization=org)
    elif not request.user.is_superuser and not org:
        employees_qs = Employee.objects.none()

    employees = list(employees_qs)
    employee_map = {str(employee.id): employee for employee in employees}
    selected_employee_id = str(request.GET.get('employee_id') or '').strip()
    selected_employee = employee_map.get(selected_employee_id)
    if selected_employee is None and employees:
        selected_employee = employees[0]

    rows = []
    summary = {'days_present': 0, 'days_absent': 0, 'total_worked_hours': 0.0}

    if selected_employee:
        attendance_filter = Q(employee=selected_employee)
        if selected_employee.user_id:
            attendance_filter |= Q(user_id=selected_employee.user_id)

        attendances = Attendance.objects.filter(
            date__range=(month_start, month_end),
        ).filter(attendance_filter).distinct().order_by('date')
        attendance_by_date = {item.date: item for item in attendances}

        timesheets = Timesheet.objects.filter(
            employee=selected_employee,
            work_date__range=(month_start, month_end),
        )
        timesheet_by_date = {item.work_date: item for item in timesheets}

        for day in range(1, month_days + 1):
            current_date = month_start.replace(day=day)
            attendance = attendance_by_date.get(current_date)
            timesheet = timesheet_by_date.get(current_date)
            worked_hours = float(getattr(timesheet, 'worked_hours', 0) or 0)

            if attendance and attendance.clock_in:
                summary['days_present'] += 1
            else:
                summary['days_absent'] += 1
            summary['total_worked_hours'] += worked_hours

            rows.append(
                {
                    'date': current_date,
                    'attendance': attendance,
                    'timesheet': timesheet,
                    'worked_hours': round(worked_hours, 2),
                }
            )

    response = render_to_pdf(
        'hr_attendance/attendance_card_pdf.html',
        {
            'employee': selected_employee,
            'month_start': month_start,
            'month_end': month_end,
            'rows': rows,
            'summary': {
                'days_present': summary['days_present'],
                'days_absent': summary['days_absent'],
                'total_worked_hours': round(summary['total_worked_hours'], 2),
            },
            'org': org,
        },
    )
    if hasattr(response, 'status_code') and response.status_code == 503:
        return response
    if response is None:
        return HttpResponse("Error Rendering PDF", status=400)

    employee_label = selected_employee.employee_id if selected_employee and selected_employee.employee_id else 'employee'
    filename = f"AttendanceCard_{employee_label}_{month_start.strftime('%Y-%m')}.pdf"
    response['Content-Disposition'] = f"attachment; filename={filename}"
    return response


@login_required
def quick_clock(request):
    selected_date = timezone.localtime(timezone.now()).date()
    employee = _employee_for_user(request.user)
    attendance, created = _get_or_create_attendance(selected_date, user=request.user, employee=employee)
    context = {
        'attendance': attendance,
        'today': selected_date,
        'can_open_dashboard': is_supervisor_or_admin(request.user),
        'summary': _monthly_attendance_summary(request.user),
    }
    return render(request, 'hr_attendance/quick_clock.html', context)


@login_required
def quick_clock_success(request):
    selected_date = timezone.localtime(timezone.now()).date()
    employee = _employee_for_user(request.user)
    attendance, created = _get_or_create_attendance(selected_date, user=request.user, employee=employee)
    next_event = _attendance_next_event(attendance)
    context = {
        'attendance': attendance,
        'today': selected_date,
        'summary': _monthly_attendance_summary(request.user),
        'next_event': next_event,
        'can_continue': next_event != 'completed',
    }
    return render(request, 'hr_attendance/quick_clock_success.html', context)


@login_required
def my_attendance_card(request):
    today = timezone.localtime(timezone.now()).date()
    month_start = _parse_month_start(request.GET.get('month'), today)
    month_days = calendar.monthrange(month_start.year, month_start.month)[1]
    month_end = month_start.replace(day=month_days)
    show_details = str(request.GET.get('details', '')).lower() in {'1', 'true', 'yes', 'on'}

    attendances = Attendance.objects.filter(
        user=request.user,
        date__range=(month_start, month_end),
    ).order_by('date')
    attendance_by_date = {item.date: item for item in attendances}

    rows = []
    summary = {
        'days_present': 0,
        'days_absent': 0,
        'total_worked_hours': 0.0,
    }

    for day in range(1, month_days + 1):
        current_date = month_start.replace(day=day)
        attendance = attendance_by_date.get(current_date)
        worked_hours = 0.0
        if attendance and attendance.clock_in and attendance.clock_out:
            worked_hours = _worked_hours_from_attendance(attendance)

        if attendance and attendance.clock_in:
            summary['days_present'] += 1
        else:
            summary['days_absent'] += 1
        summary['total_worked_hours'] += worked_hours

        rows.append(
            {
                'date': current_date,
                'attendance': attendance,
                'worked_hours': round(worked_hours, 2),
            }
        )

    context = {
        'month_value': month_start.strftime('%Y-%m'),
        'rows': rows,
        'show_details': show_details,
        'summary': {
            'days_present': summary['days_present'],
            'days_absent': summary['days_absent'],
            'total_worked_hours': round(summary['total_worked_hours'], 2),
        },
    }
    return render(request, 'hr_attendance/my_attendance_card.html', context)

@login_required
def clock_in(request):
    if request.method == 'POST':
        today = timezone.localtime(timezone.now()).date()
        employee = _employee_for_user(request.user)
        attendance, created = _get_or_create_attendance(today, user=request.user, employee=employee)
        
        if not attendance.clock_in:
            now_dt = timezone.now()
            attendance.clock_in = now_dt
            attendance.user_clock_in = now_dt
            attendance.clock_in_by = request.user
            source, capture_mode, device_id = _resolve_capture_fields(request, default_source='web', default_mode='web_punch')
            attendance.source = source
            attendance.capture_mode = capture_mode
            attendance.device_id = device_id
            attendance.status = Attendance.Status.PRESENT
            
            # Save location if provided
            lat, lng = _parse_location_from_request(request)
            _save_location(attendance, lat, lng, 'in')
            
            # Save photo if provided
            photo_data = request.POST.get('photo')
            if photo_data:
                # Save the raw base64 string directly to the database
                # since the filesystem is read-only on production
                attendance.photo_in = photo_data
            
            # Get IP address
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                attendance.ip_address = x_forwarded_for.split(',')[0]
            else:
                attendance.ip_address = request.META.get('REMOTE_ADDR')

            attendance.save()
            messages.success(request, _("Clock-in recorded successfully!"))
        elif attendance.lunch_out and not attendance.lunch_in:
            now_dt = timezone.now()
            attendance.lunch_in = now_dt
            attendance.user_lunch_in = now_dt
            attendance.lunch_in_by = request.user
            source, capture_mode, device_id = _resolve_capture_fields(request, default_source='web', default_mode='web_punch')
            attendance.source = source
            attendance.capture_mode = capture_mode
            attendance.device_id = device_id
            attendance.status = Attendance.Status.PRESENT

            lat, lng = _parse_location_from_request(request)
            _save_location(attendance, lat, lng, 'lunch_in')

            attendance.save()
            messages.success(request, _("Lunch break ended successfully!"))
        elif attendance.clock_in and not attendance.lunch_out and not attendance.clock_out:
            messages.warning(request, _("Use clock-out action to start lunch break."))
        elif attendance.lunch_in and not attendance.clock_out:
            messages.warning(request, _("Use clock-out action to finish the workday."))
        else:
            messages.warning(request, _("Today's attendance flow is already completed."))
            
    return _clock_redirect(request)

@login_required
def clock_out(request):
    if request.method == 'POST':
        today = timezone.localtime(timezone.now()).date()
        out_mode = str(request.POST.get('out_mode') or '').strip().lower()
        try:
            employee = _employee_for_user(request.user)
            attendance = _find_attendance(today, user=request.user, employee=employee)
            if attendance is None:
                raise Attendance.DoesNotExist
            if attendance.clock_in and not attendance.lunch_out and not attendance.clock_out:
                now_dt = timezone.now()
                source, capture_mode, device_id = _resolve_capture_fields(request, default_source='web', default_mode='web_punch')
                attendance.source = source
                attendance.capture_mode = capture_mode
                attendance.device_id = device_id
                attendance.status = Attendance.Status.PRESENT

                lat, lng = _parse_location_from_request(request)
                if out_mode in {'end_day', 'end', 'clock_out'}:
                    attendance.clock_out = now_dt
                    attendance.user_clock_out = now_dt
                    attendance.clock_out_by = request.user
                    _save_location(attendance, lat, lng, 'out')
                    attendance.save()
                    _upsert_timesheet_from_attendance(attendance)
                    messages.success(request, _("Clock-out recorded successfully!"))
                else:
                    attendance.lunch_out = now_dt
                    attendance.user_lunch_out = now_dt
                    attendance.lunch_out_by = request.user
                    _save_location(attendance, lat, lng, 'lunch_out')
                    attendance.save()
                    messages.success(request, _("Lunch break started successfully!"))
            elif attendance.lunch_out and not attendance.lunch_in:
                messages.error(request, _("You must clock in from lunch break first."))
            elif attendance.lunch_in and not attendance.clock_out:
                now_dt = timezone.now()
                attendance.clock_out = now_dt
                attendance.user_clock_out = now_dt
                attendance.clock_out_by = request.user
                source, capture_mode, device_id = _resolve_capture_fields(request, default_source='web', default_mode='web_punch')
                attendance.source = source
                attendance.capture_mode = capture_mode
                attendance.device_id = device_id
                attendance.status = Attendance.Status.PRESENT
                
                # Update location if provided (exit location)
                lat, lng = _parse_location_from_request(request)
                _save_location(attendance, lat, lng, 'out')
                
                # Save photo if provided
                photo_data = request.POST.get('photo')
                if photo_data:
                    # Save the raw base64 string directly to the database
                    # since the filesystem is read-only on production
                    attendance.photo_out = photo_data

                attendance.save()
                _upsert_timesheet_from_attendance(attendance)
                messages.success(request, _("Clock-out recorded successfully!"))
            elif not attendance.clock_in:
                messages.error(request, _("You must clock in first."))
            else:
                messages.warning(request, _("You have already finished today's attendance flow."))
        except Attendance.DoesNotExist:
            messages.error(request, _("No attendance record found for today. Please clock in first."))
            
    return _clock_redirect(request)


@login_required
@user_passes_test(is_supervisor_or_admin)
def supervisor_panel(request):
    """
    Supervisor dashboard to record clock-in/out for users in the same organization.
    """
    view_started = time.perf_counter()
    users_qs = _attendance_users_for_manager(request)

    date_str = request.GET.get('date')
    if date_str:
        try:
            selected_date = datetime.date.fromisoformat(date_str)
        except Exception:
            selected_date = timezone.localtime(timezone.now()).date()
    else:
        selected_date = timezone.localtime(timezone.now()).date()

    org = getattr(request, 'organization', None)
    current_employee = _employee_for_user(request.user)
    role = getattr(getattr(request.user, 'profile', None), 'role', 'user')

    users = list(users_qs)
    records = []

    linked_employee_ids = {
        u.employee_id
        for u in users
        if getattr(u, 'employee_id', None)
    }

    unlinked_employees = list(
        _scoped_unlinked_employees(request, org, current_employee, role).exclude(id__in=linked_employee_ids)
    )

    linked_employees = [getattr(u, 'employee', None) for u in users if getattr(u, 'employee', None) is not None]
    attendance_by_user_id, attendance_by_employee_id = _attendance_maps_for_targets(
        selected_date,
        users,
        linked_employees + unlinked_employees,
    )

    attendance_ids = {
        attendance.id
        for attendance in list(attendance_by_user_id.values()) + list(attendance_by_employee_id.values())
        if attendance is not None
    }
    history_payloads_by_attendance = _history_payloads_for_attendances(attendance_ids)

    for u in users:
        employee = getattr(u, 'employee', None)
        att = attendance_by_employee_id.get(employee.id) if employee else None
        if att is None:
            att = attendance_by_user_id.get(u.id)
        history_payload = history_payloads_by_attendance.get(att.id, []) if att else []
        records.append(
            {
                'user': u,
                'employee': employee,
                'attendance': att,
                'history_count': len(history_payload),
                'history_json': json.dumps(history_payload, ensure_ascii=False),
            }
        )

    for employee in unlinked_employees:
        att = attendance_by_employee_id.get(employee.id)
        history_payload = history_payloads_by_attendance.get(att.id, []) if att else []
        records.append(
            {
                'user': None,
                'employee': employee,
                'attendance': att,
                'history_count': len(history_payload),
                'history_json': json.dumps(history_payload, ensure_ascii=False),
            }
        )

    pdf_url = request.build_absolute_uri(
        f"/attendance/supervisor/pdf/?date={selected_date.isoformat()}"
    )

    elapsed_ms = (time.perf_counter() - view_started) * 1000
    logger.info(
        "supervisor_panel_timing_ms=%.2f users=%s unlinked=%s records=%s date=%s",
        elapsed_ms,
        len(users),
        len(unlinked_employees),
        len(records),
        selected_date.isoformat(),
    )
    if elapsed_ms >= SLOW_SUPERVISOR_VIEW_MS:
        logger.warning(
            "slow_supervisor_panel_timing_ms=%.2f users=%s unlinked=%s records=%s date=%s",
            elapsed_ms,
            len(users),
            len(unlinked_employees),
            len(records),
            selected_date.isoformat(),
        )

    prev_day = selected_date - datetime.timedelta(days=1)
    next_day = selected_date + datetime.timedelta(days=1)
    prev_month = _shift_month(selected_date, -1)
    next_month = _shift_month(selected_date, 1)

    return render(request, 'hr_attendance/supervisor_panel.html', {
        'records': records,
        'today': selected_date,
        'selected_date': selected_date,
        'date_str': selected_date.isoformat(),
        'pdf_url': pdf_url,
        'prev_day_str': prev_day.isoformat(),
        'next_day_str': next_day.isoformat(),
        'prev_month_str': prev_month.isoformat(),
        'next_month_str': next_month.isoformat(),
    })


@login_required
@user_passes_test(is_supervisor_or_admin)
def supervisor_bulk_range_entry(request):
    org = getattr(request, 'organization', None)
    current_employee = _employee_for_user(request.user)
    role = getattr(getattr(request.user, 'profile', None), 'role', 'user')

    employees_qs = Employee.objects.select_related('user', 'work_unit', 'reporting_manager')
    if not request.user.is_superuser and org:
        employees_qs = employees_qs.filter(organization=org)
    elif not request.user.is_superuser and not org:
        employees_qs = Employee.objects.none()

    employees = [
        employee for employee in employees_qs.order_by('first_name', 'last_name')
        if _is_employee_in_scope(request, employee)
    ]
    employee_map = {str(employee.id): employee for employee in employees}

    today_str = timezone.localtime(timezone.now()).date().isoformat()
    selected_employee_id = request.POST.get('employee_id') or request.GET.get('employee_id') or ''
    start_date_str = request.POST.get('start_date') or request.GET.get('start_date') or today_str
    end_date_str = request.POST.get('end_date') or request.GET.get('end_date') or today_str
    in_time_str = request.POST.get('in_time') or ''
    lunch_out_time_str = request.POST.get('lunch_out_time') or ''
    lunch_in_time_str = request.POST.get('lunch_in_time') or ''
    out_time_str = request.POST.get('out_time') or ''
    selected_shift_id = request.POST.get('shift_id') or request.GET.get('shift_id') or ''
    use_shift_schedule = str(request.POST.get('use_shift_schedule') or request.GET.get('use_shift_schedule') or '').lower() in {
        '1', 'true', 'yes', 'on'
    }
    apply_non_working = str(request.POST.get('apply_non_working') or request.GET.get('apply_non_working') or '').lower() in {
        '1', 'true', 'yes', 'on'
    }
    submit_action_values = [
        str(value or '').strip().lower()
        for value in request.POST.getlist('submit_action')
        if str(value or '').strip()
    ]
    confirm_replace_values = [
        str(value or '').strip().lower()
        for value in request.POST.getlist('confirm_replace')
    ]
    confirm_replace = any(value in {'1', 'true', 'yes', 'on'} for value in confirm_replace_values)
    submit_action = submit_action_values[0] if submit_action_values else str(request.POST.get('submit_action') or 'apply').strip().lower()
    if 'confirm_replace_apply' in submit_action_values or submit_action == 'confirm_replace_apply':
        confirm_replace = True
        submit_action = 'apply'
    replace_confirmation_needed = False
    existing_days_count = 0

    tenant = _resolve_company_for_org(org)
    shifts = []
    shift_map = {}
    if tenant is not None and ShiftTemplate is not None:
        shifts = list(ShiftTemplate.objects.filter(tenant=tenant).order_by('name'))
        shift_map = {str(shift.id): shift for shift in shifts}

    if request.method == 'POST':
        logger.info(
            (
                'bulk_range_post_received user_id=%s submit_action_values=%s resolved_submit_action=%s '
                'confirm_replace_values=%s resolved_confirm_replace=%s use_shift_schedule=%s selected_shift_id=%s post_keys=%s'
            ),
            request.user.id,
            submit_action_values,
            submit_action,
            confirm_replace_values,
            confirm_replace,
            use_shift_schedule,
            selected_shift_id,
            sorted(list(request.POST.keys())),
        )
        target_employee = employee_map.get(selected_employee_id)
        if target_employee is None:
            messages.error(request, _("Please select a valid employee."))
        else:
            selected_shift = shift_map.get(selected_shift_id) if use_shift_schedule else None
            try:
                start_date = datetime.date.fromisoformat(start_date_str)
                end_date = datetime.date.fromisoformat(end_date_str)
            except Exception:
                messages.error(request, _("Please select valid start/end dates."))
                start_date = None
                end_date = None

            if start_date and end_date and end_date < start_date:
                messages.error(request, _("End date cannot be earlier than start date."))
                start_date = None
                end_date = None

            if start_date and end_date and (end_date - start_date).days > 93:
                messages.error(request, _("Date range is too large. Maximum is 93 days."))
                start_date = None
                end_date = None

            if start_date and end_date and submit_action == 'rebuild':
                attendance_qs = Attendance.objects.filter(
                    employee=target_employee,
                    date__range=(start_date, end_date),
                ).order_by('date')
                recalculated_count = 0
                for attendance in attendance_qs:
                    _upsert_timesheet_from_attendance(attendance)
                    recalculated_count += 1
                messages.success(
                    request,
                    _("Timesheets rebuilt for %(count)s day(s) in selected range.") % {'count': recalculated_count},
                )
                return _redirect_supervisor_by_date(start_date.isoformat())

            if start_date and end_date and submit_action == 'apply':
                existing_days_count = Attendance.objects.filter(
                    employee=target_employee,
                    date__range=(start_date, end_date),
                ).count()
                logger.info(
                    (
                        'bulk_range_replace_check user_id=%s employee_id=%s start=%s end=%s '
                        'submit_action=%s confirm_replace_values=%s confirm_replace=%s existing_days=%s '
                        'post_keys=%s'
                    ),
                    request.user.id,
                    target_employee.id,
                    start_date.isoformat(),
                    end_date.isoformat(),
                    submit_action,
                    confirm_replace_values,
                    confirm_replace,
                    existing_days_count,
                    sorted(list(request.POST.keys())),
                )
                if existing_days_count and not confirm_replace:
                    replace_confirmation_needed = True
                    logger.warning(
                        (
                            'bulk_range_replace_confirmation_required user_id=%s employee_id=%s start=%s end=%s '
                            'confirm_replace_values=%s post_confirm_replace=%s'
                        ),
                        request.user.id,
                        target_employee.id,
                        start_date.isoformat(),
                        end_date.isoformat(),
                        confirm_replace_values,
                        request.POST.getlist('confirm_replace'),
                    )
                    messages.warning(
                        request,
                        _(
                            "%(count)s existing attendance day(s) were found in this range. "
                            "Please confirm replacement to delete previous rows and apply new data."
                        ) % {'count': existing_days_count},
                    )

            parsed_in_time = None
            parsed_lunch_out_time = None
            parsed_lunch_in_time = None
            parsed_out_time = None
            if start_date and end_date:
                if use_shift_schedule and selected_shift is None:
                    messages.error(request, _("Please select a valid shift for shift-based range apply."))
                    start_date = None
                elif not use_shift_schedule and not in_time_str and not lunch_out_time_str and not lunch_in_time_str and not out_time_str:
                    messages.error(request, _("Please enter at least one time."))
                elif not use_shift_schedule:
                    try:
                        parsed_in_time = datetime.time.fromisoformat(in_time_str) if in_time_str else None
                    except ValueError:
                        messages.error(request, _("Clock-in time format is invalid."))
                        start_date = None

                    try:
                        parsed_lunch_out_time = datetime.time.fromisoformat(lunch_out_time_str) if lunch_out_time_str else None
                    except ValueError:
                        messages.error(request, _("Lunch-out time format is invalid."))
                        start_date = None

                    try:
                        parsed_lunch_in_time = datetime.time.fromisoformat(lunch_in_time_str) if lunch_in_time_str else None
                    except ValueError:
                        messages.error(request, _("Lunch-in time format is invalid."))
                        start_date = None

                    try:
                        parsed_out_time = datetime.time.fromisoformat(out_time_str) if out_time_str else None
                    except ValueError:
                        messages.error(request, _("Clock-out time format is invalid."))
                        start_date = None

                    if (
                        start_date
                        and parsed_lunch_out_time
                        and parsed_lunch_in_time
                        and parsed_lunch_in_time <= parsed_lunch_out_time
                    ):
                        messages.error(request, _("Lunch-in time must be later than lunch-out time."))
                        start_date = None

            if start_date and end_date and submit_action == 'apply' and not replace_confirmation_needed:
                logger.info(
                    (
                        'bulk_range_apply_proceed user_id=%s employee_id=%s start=%s end=%s '
                        'existing_days=%s confirm_replace=%s apply_non_working=%s'
                    ),
                    request.user.id,
                    target_employee.id,
                    start_date.isoformat(),
                    end_date.isoformat(),
                    existing_days_count,
                    confirm_replace,
                    apply_non_working,
                )
                source, capture_mode, device_id = _resolve_capture_fields(
                    request,
                    default_source='manual',
                    default_mode='manual',
                )
                with transaction.atomic():
                    Attendance.objects.filter(
                        employee=target_employee,
                        date__range=(start_date, end_date),
                    ).delete()
                    Timesheet.objects.filter(
                        employee=target_employee,
                        work_date__range=(start_date, end_date),
                    ).delete()

                processed_days = 0
                updated_days = 0
                skipped_non_working_days = 0
                applied_non_working_days = 0
                skipped_shift_days = 0
                cursor_date = start_date
                target_user = getattr(target_employee, 'user', None)

                while cursor_date <= end_date:
                    shift_ctx = _resolve_hrms_shift_context(target_employee, cursor_date, tenant)
                    calendar_day = shift_ctx.get('calendar_day')
                    required_minutes = int(shift_ctx.get('required_minutes') or 0)
                    is_non_working_day = calendar_day is not None and (
                        calendar_day.day_type in {'weekend', 'public_holiday'}
                        or required_minutes <= 0
                    )
                    if is_non_working_day and not apply_non_working:
                        skipped_non_working_days += 1
                        processed_days += 1
                        cursor_date += datetime.timedelta(days=1)
                        continue
                    if is_non_working_day and apply_non_working:
                        applied_non_working_days += 1

                    day_in_time = parsed_in_time
                    day_lunch_out_time = parsed_lunch_out_time
                    day_lunch_in_time = parsed_lunch_in_time
                    day_out_time = parsed_out_time
                    if use_shift_schedule:
                        day_shift_version = None
                        if selected_shift is not None:
                            day_shift_version = (
                                ShiftVersion.objects.filter(
                                    tenant=tenant,
                                    shift=selected_shift,
                                    valid_from__lte=cursor_date,
                                    valid_to__gte=cursor_date,
                                )
                                .order_by('-valid_from')
                                .first()
                            )
                        if day_shift_version is None:
                            skipped_shift_days += 1
                            processed_days += 1
                            cursor_date += datetime.timedelta(days=1)
                            continue
                        day_in_time = day_shift_version.start_time
                        day_out_time = day_shift_version.end_time
                        day_lunch_out_time = None
                        day_lunch_in_time = None

                    attendance, _created = _get_or_create_attendance(
                        cursor_date,
                        user=target_user,
                        employee=target_employee,
                    )
                    changed = False

                    if day_in_time:
                        new_clock_in = timezone.make_aware(
                            datetime.datetime.combine(cursor_date, day_in_time),
                            timezone.get_current_timezone(),
                        )
                        if attendance.clock_in != new_clock_in:
                            old_clock_in = attendance.clock_in
                            attendance.clock_in = new_clock_in
                            attendance.supervisor_clock_in = new_clock_in
                            attendance.clock_in_by = request.user
                            _log_attendance_change(
                                attendance=attendance,
                                actor=request.user,
                                field_name='clock_in',
                                action_type='edit' if old_clock_in else 'set',
                                old_value=old_clock_in,
                                new_value=new_clock_in,
                                note='Supervisor bulk range',
                            )
                            changed = True

                    if day_lunch_out_time:
                        new_lunch_out = timezone.make_aware(
                            datetime.datetime.combine(cursor_date, day_lunch_out_time),
                            timezone.get_current_timezone(),
                        )
                        if attendance.lunch_out != new_lunch_out:
                            old_lunch_out = attendance.lunch_out
                            attendance.lunch_out = new_lunch_out
                            attendance.supervisor_lunch_out = new_lunch_out
                            attendance.lunch_out_by = request.user
                            _log_attendance_change(
                                attendance=attendance,
                                actor=request.user,
                                field_name='lunch_out',
                                action_type='edit' if old_lunch_out else 'set',
                                old_value=old_lunch_out,
                                new_value=new_lunch_out,
                                note='Supervisor bulk range',
                            )
                            changed = True

                    if day_lunch_in_time:
                        new_lunch_in = timezone.make_aware(
                            datetime.datetime.combine(cursor_date, day_lunch_in_time),
                            timezone.get_current_timezone(),
                        )
                        if attendance.lunch_in != new_lunch_in:
                            old_lunch_in = attendance.lunch_in
                            attendance.lunch_in = new_lunch_in
                            attendance.supervisor_lunch_in = new_lunch_in
                            attendance.lunch_in_by = request.user
                            _log_attendance_change(
                                attendance=attendance,
                                actor=request.user,
                                field_name='lunch_in',
                                action_type='edit' if old_lunch_in else 'set',
                                old_value=old_lunch_in,
                                new_value=new_lunch_in,
                                note='Supervisor bulk range',
                            )
                            changed = True

                    if day_out_time:
                        out_date = cursor_date
                        if day_in_time and day_out_time <= day_in_time:
                            out_date = cursor_date + datetime.timedelta(days=1)
                        new_clock_out = timezone.make_aware(
                            datetime.datetime.combine(out_date, day_out_time),
                            timezone.get_current_timezone(),
                        )
                        if attendance.clock_out != new_clock_out:
                            old_clock_out = attendance.clock_out
                            attendance.clock_out = new_clock_out
                            attendance.supervisor_clock_out = new_clock_out
                            attendance.clock_out_by = request.user
                            _log_attendance_change(
                                attendance=attendance,
                                actor=request.user,
                                field_name='clock_out',
                                action_type='edit' if old_clock_out else 'set',
                                old_value=old_clock_out,
                                new_value=new_clock_out,
                                note='Supervisor bulk range',
                            )
                            changed = True

                    if changed:
                        attendance.source = source
                        attendance.capture_mode = capture_mode
                        attendance.device_id = device_id
                        attendance.status = Attendance.Status.PRESENT
                        attendance.save()
                        _upsert_timesheet_from_attendance(attendance)
                        updated_days += 1

                    processed_days += 1
                    cursor_date += datetime.timedelta(days=1)

                messages.success(
                    request,
                    _("Bulk attendance applied for %(updated)s of %(processed)s days.")
                    % {'updated': updated_days, 'processed': processed_days},
                )
                if existing_days_count:
                    messages.info(
                        request,
                        _("Existing attendance rows in the selected range were replaced: %(count)s day(s).")
                        % {'count': existing_days_count},
                    )
                if skipped_non_working_days:
                    messages.info(
                        request,
                        _("%(count)s non-working day(s) were skipped based on Work Calendar.")
                        % {'count': skipped_non_working_days},
                    )
                if applied_non_working_days:
                    messages.info(
                        request,
                        _("%(count)s non-working day(s) were applied as overtime candidates.")
                        % {'count': applied_non_working_days},
                    )
                if skipped_shift_days:
                    messages.info(
                        request,
                        _("%(count)s day(s) were skipped because selected shift had no active version on those dates.")
                        % {'count': skipped_shift_days},
                    )
                return _redirect_supervisor_by_date(start_date.isoformat())

    return render(
        request,
        'hr_attendance/supervisor_bulk_range.html',
        {
            'employees': employees,
            'selected_employee_id': selected_employee_id,
            'start_date': start_date_str,
            'end_date': end_date_str,
            'in_time': in_time_str,
            'lunch_out_time': lunch_out_time_str,
            'lunch_in_time': lunch_in_time_str,
            'out_time': out_time_str,
            'shift_id': selected_shift_id,
            'use_shift_schedule': use_shift_schedule,
            'shifts': shifts,
            'apply_non_working': apply_non_working,
            'confirm_replace': confirm_replace,
            'replace_confirmation_needed': replace_confirmation_needed,
            'existing_days_count': existing_days_count,
            'today': timezone.localtime(timezone.now()).date(),
        },
    )


@login_required
@user_passes_test(is_supervisor_or_admin)
def supervisor_report_pdf(request):
    view_started = time.perf_counter()
    org = None
    try:
        org = request.user.profile.organization
    except Exception:
        org = None

    date_str = request.GET.get('date')
    if date_str:
        try:
            selected_date = datetime.date.fromisoformat(date_str)
        except Exception:
            selected_date = timezone.localtime(timezone.now()).date()
    else:
        selected_date = timezone.localtime(timezone.now()).date()

    users = list(_attendance_users_for_manager(request))
    records = []

    linked_employee_ids = {
        u.employee_id
        for u in users
        if getattr(u, 'employee_id', None)
    }

    current_employee = _employee_for_user(request.user)
    role = getattr(getattr(request.user, 'profile', None), 'role', 'user')
    unlinked_employees = list(
        _scoped_unlinked_employees(request, org, current_employee, role).exclude(id__in=linked_employee_ids)
    )

    linked_employees = [getattr(u, 'employee', None) for u in users if getattr(u, 'employee', None) is not None]
    attendance_by_user_id, attendance_by_employee_id = _attendance_maps_for_targets(
        selected_date,
        users,
        linked_employees + unlinked_employees,
    )

    for u in users:
        employee = getattr(u, 'employee', None)
        att = attendance_by_employee_id.get(employee.id) if employee else None
        if att is None:
            att = attendance_by_user_id.get(u.id)
        records.append({'user': u, 'employee': employee, 'attendance': att})

    for employee in unlinked_employees:
        att = attendance_by_employee_id.get(employee.id)
        records.append({'user': None, 'employee': employee, 'attendance': att})

    response = render_to_pdf(
        'hr_attendance/supervisor_report_pdf.html',
        {
            'records': records,
            'date': selected_date,
            'org': org,
        },
    )
    if hasattr(response, 'status_code') and response.status_code == 503:
        return response
    if response is None:
        return HttpResponse("Error Rendering PDF", status=400)

    filename = f"Attendance_{(org.slug if org else 'all')}_{selected_date.isoformat()}.pdf"
    response['Content-Disposition'] = f"attachment; filename={filename}"
    elapsed_ms = (time.perf_counter() - view_started) * 1000
    logger.info(
        "supervisor_pdf_timing_ms=%.2f users=%s unlinked=%s records=%s date=%s",
        elapsed_ms,
        len(users),
        len(unlinked_employees),
        len(records),
        selected_date.isoformat(),
    )
    return response


@login_required
@user_passes_test(is_supervisor_or_admin)
def supervisor_clock_in(request, user_id):
    if request.method == 'POST':
        target = get_object_or_404(User, pk=user_id)
        # Organization boundary
        if not request.user.is_superuser:
            try:
                if request.user.profile.organization_id != target.profile.organization_id:
                    messages.error(request, _("You cannot modify users outside your organization."))
                    return redirect('hr_attendance:supervisor_panel')
            except Exception:
                messages.error(request, _("Invalid organization context."))
                return redirect('hr_attendance:supervisor_panel')
        date_str = request.POST.get('date') or request.GET.get('date')
        if date_str:
            try:
                selected_date = datetime.date.fromisoformat(date_str)
            except Exception:
                selected_date = timezone.localtime(timezone.now()).date()
        else:
            selected_date = timezone.localtime(timezone.now()).date()

        target_employee = _employee_for_user(target)
        attendance, created = _get_or_create_attendance(selected_date, user=target, employee=target_employee)
        manual_clock_in, has_manual_input, is_valid_time = _resolve_manual_punch_datetime(request, 'manual_clock_in', selected_date)
        if not is_valid_time:
            messages.error(request, _("Invalid manual clock-in time format."))
            if request.POST.get('date'):
                return redirect(f"/attendance/supervisor/?date={request.POST.get('date')}")
            return redirect('hr_attendance:supervisor_panel')

        if attendance.clock_in_by_id == target.id and attendance.clock_in and not attendance.user_clock_in:
            attendance.user_clock_in = attendance.clock_in

        attendance.clock_in = manual_clock_in
        attendance.supervisor_clock_in = manual_clock_in
        attendance.clock_in_by = request.user
        source, capture_mode, device_id = _resolve_capture_fields(request, default_source='manual', default_mode='manual')
        attendance.source = source
        attendance.capture_mode = capture_mode
        attendance.device_id = device_id
        attendance.status = Attendance.Status.PRESENT
        lat, lng = _parse_location_from_request(request)
        _save_location(attendance, lat, lng, 'in')
        attendance.save()
        if created:
            messages.success(request, _("Clock-in recorded for ") + target.username)
        else:
            messages.success(request, _("Clock-in corrected for ") + target.username)
    if request.POST.get('date'):
        return redirect(f"/attendance/supervisor/?date={request.POST.get('date')}")
    return redirect('hr_attendance:supervisor_panel')


@login_required
@user_passes_test(is_supervisor_or_admin)
def supervisor_attendance_action(request, user_id):
    if request.method != 'POST':
        return redirect('hr_attendance:supervisor_panel')

    target = get_object_or_404(User, pk=user_id)
    if not _is_target_in_scope(request, target):
        messages.error(request, _("You cannot modify this user."))
        return _redirect_supervisor_by_date(request.POST.get('date'))

    return _supervisor_attendance_action_core(
        request,
        target_user=target,
        target_employee=_employee_for_user(target),
    )


@login_required
@user_passes_test(is_supervisor_or_admin)
def supervisor_attendance_action_employee(request, employee_id):
    if request.method != 'POST':
        return redirect('hr_attendance:supervisor_panel')

    target_employee = get_object_or_404(Employee, pk=employee_id)
    if not _is_employee_in_scope(request, target_employee):
        messages.error(request, _("You cannot modify this employee."))
        return _redirect_supervisor_by_date(request.POST.get('date'))

    return _supervisor_attendance_action_core(
        request,
        target_user=getattr(target_employee, 'user', None),
        target_employee=target_employee,
    )


def _supervisor_attendance_action_core(request, target_user=None, target_employee=None):
    action_started = time.perf_counter()
    if target_user is None and target_employee is None:
        messages.error(request, _("Invalid attendance target."))
        return _redirect_supervisor_by_date(request.POST.get('date'))

    date_str = request.POST.get('date')
    try:
        selected_date = datetime.date.fromisoformat(date_str) if date_str else timezone.localtime(timezone.now()).date()
    except Exception:
        selected_date = timezone.localtime(timezone.now()).date()

    action = str(request.POST.get('action') or '').strip().lower()
    time_value = request.POST.get('time_value')
    valid_actions = {
        'set_in', 'set_lunch_out', 'set_lunch_in', 'set_out',
        'edit_in', 'edit_lunch_out', 'edit_lunch_in', 'edit_out',
        'delete_in', 'delete_lunch_out', 'delete_lunch_in', 'delete_out',
    }
    if action not in valid_actions:
        messages.error(request, _("Invalid action."))
        return _redirect_supervisor_by_date(selected_date.isoformat())

    attendance = _find_attendance(selected_date, user=target_user, employee=target_employee)
    if not attendance and action.startswith('delete'):
        messages.error(request, _("No attendance record exists for this employee on this date."))
        return _redirect_supervisor_by_date(selected_date.isoformat())
    if not attendance:
        attendance, created = _get_or_create_attendance(selected_date, user=target_user, employee=target_employee)

    action_map = {
        'in': ('clock_in', 'supervisor_clock_in', 'clock_in_by', 'in'),
        'lunch_out': ('lunch_out', 'supervisor_lunch_out', 'lunch_out_by', 'lunch_out'),
        'lunch_in': ('lunch_in', 'supervisor_lunch_in', 'lunch_in_by', 'lunch_in'),
        'out': ('clock_out', 'supervisor_clock_out', 'clock_out_by', 'out'),
    }

    action_suffix = action.split('_', 1)[1]
    field_name, supervisor_field, actor_field, location_event_key = action_map[action_suffix]
    old_value = getattr(attendance, field_name)

    if action.startswith('set') or action.startswith('edit'):
        parsed_dt = _parse_supervisor_action_datetime(selected_date, time_value)
        if not parsed_dt:
            messages.error(request, _("Please select a valid time."))
            return _redirect_supervisor_by_date(selected_date.isoformat())
        if action.startswith('set') and old_value:
            messages.warning(request, _("Time already exists. Use edit instead."))
            return _redirect_supervisor_by_date(selected_date.isoformat())
        if action.startswith('edit') and not old_value:
            messages.warning(request, _("No existing time to edit. Use set instead."))
            return _redirect_supervisor_by_date(selected_date.isoformat())

        setattr(attendance, field_name, parsed_dt)
        setattr(attendance, supervisor_field, parsed_dt)
        setattr(attendance, actor_field, request.user)
        source, capture_mode, device_id = _resolve_capture_fields(request, default_source='manual', default_mode='manual')
        attendance.source = source
        attendance.capture_mode = capture_mode
        attendance.device_id = device_id
        attendance.status = Attendance.Status.PRESENT
        lat, lng = _parse_location_from_request(request)
        _save_location(attendance, lat, lng, location_event_key)
        attendance.save()

        _log_attendance_change(
            attendance=attendance,
            actor=request.user,
            field_name=field_name,
            action_type='set' if action.startswith('set') else 'edit',
            old_value=old_value,
            new_value=parsed_dt,
            note='Supervisor panel',
        )
        _upsert_timesheet_from_attendance(attendance)
        elapsed_ms = (time.perf_counter() - action_started) * 1000
        logger.info(
            "supervisor_action_timing_ms=%.2f action=%s date=%s target_user_id=%s target_employee_id=%s",
            elapsed_ms,
            action,
            selected_date.isoformat(),
            getattr(target_user, 'id', None),
            getattr(target_employee, 'id', None),
        )
        if elapsed_ms >= SLOW_SUPERVISOR_VIEW_MS:
            logger.warning(
                "slow_supervisor_action_timing_ms=%.2f action=%s date=%s target_user_id=%s target_employee_id=%s",
                elapsed_ms,
                action,
                selected_date.isoformat(),
                getattr(target_user, 'id', None),
                getattr(target_employee, 'id', None),
            )
        messages.success(request, _("Attendance time saved."))
        return _redirect_supervisor_by_date(selected_date.isoformat())

    if not old_value:
        messages.warning(request, _("No saved time to delete."))
        return _redirect_supervisor_by_date(selected_date.isoformat())

    setattr(attendance, field_name, None)
    setattr(attendance, supervisor_field, None)
    setattr(attendance, actor_field, request.user)
    if field_name == 'clock_in':
        attendance.clock_in_latitude = None
        attendance.clock_in_longitude = None
    elif field_name == 'clock_out':
        attendance.clock_out_latitude = None
        attendance.clock_out_longitude = None
    elif field_name == 'lunch_out':
        attendance.lunch_out_latitude = None
        attendance.lunch_out_longitude = None
    elif field_name == 'lunch_in':
        attendance.lunch_in_latitude = None
        attendance.lunch_in_longitude = None
    attendance.save()

    _log_attendance_change(
        attendance=attendance,
        actor=request.user,
        field_name=field_name,
        action_type='delete',
        old_value=old_value,
        new_value=None,
        note='Supervisor panel',
    )
    _upsert_timesheet_from_attendance(attendance)
    elapsed_ms = (time.perf_counter() - action_started) * 1000
    logger.info(
        "supervisor_action_timing_ms=%.2f action=%s date=%s target_user_id=%s target_employee_id=%s",
        elapsed_ms,
        action,
        selected_date.isoformat(),
        getattr(target_user, 'id', None),
        getattr(target_employee, 'id', None),
    )
    if elapsed_ms >= SLOW_SUPERVISOR_VIEW_MS:
        logger.warning(
            "slow_supervisor_action_timing_ms=%.2f action=%s date=%s target_user_id=%s target_employee_id=%s",
            elapsed_ms,
            action,
            selected_date.isoformat(),
            getattr(target_user, 'id', None),
            getattr(target_employee, 'id', None),
        )
    messages.success(request, _("Attendance time deleted."))
    return _redirect_supervisor_by_date(selected_date.isoformat())


@login_required
@user_passes_test(is_supervisor_or_admin)
def supervisor_clock_out(request, user_id):
    if request.method == 'POST':
        target = get_object_or_404(User, pk=user_id)
        if not request.user.is_superuser:
            try:
                if request.user.profile.organization_id != target.profile.organization_id:
                    messages.error(request, _("You cannot modify users outside your organization."))
                    return redirect('hr_attendance:supervisor_panel')
            except Exception:
                messages.error(request, _("Invalid organization context."))
                return redirect('hr_attendance:supervisor_panel')
        date_str = request.POST.get('date') or request.GET.get('date')
        if date_str:
            try:
                selected_date = datetime.date.fromisoformat(date_str)
            except Exception:
                selected_date = timezone.localtime(timezone.now()).date()
        else:
            selected_date = timezone.localtime(timezone.now()).date()

        target_employee = _employee_for_user(target)
        attendance, created = _get_or_create_attendance(selected_date, user=target, employee=target_employee)
        manual_clock_out, has_manual_input, is_valid_time = _resolve_manual_punch_datetime(request, 'manual_clock_out', selected_date)
        if not is_valid_time:
            messages.error(request, _("Invalid manual clock-out time format."))
            if request.POST.get('date'):
                return redirect(f"/attendance/supervisor/?date={request.POST.get('date')}")
            return redirect('hr_attendance:supervisor_panel')

        if not attendance.clock_in:
            messages.error(request, _("The user has not clocked in yet."))
        else:
            if attendance.clock_out_by_id == target.id and attendance.clock_out and not attendance.user_clock_out:
                attendance.user_clock_out = attendance.clock_out

            attendance.clock_out = manual_clock_out
            attendance.supervisor_clock_out = manual_clock_out
            attendance.clock_out_by = request.user
            source, capture_mode, device_id = _resolve_capture_fields(request, default_source='manual', default_mode='manual')
            attendance.source = source
            attendance.capture_mode = capture_mode
            attendance.device_id = device_id
            attendance.status = Attendance.Status.PRESENT
            lat, lng = _parse_location_from_request(request)
            _save_location(attendance, lat, lng, 'out')
            attendance.save()
            _upsert_timesheet_from_attendance(attendance)
            if created:
                messages.success(request, _("Clock-out recorded for ") + target.username)
            else:
                messages.success(request, _("Clock-out corrected for ") + target.username)
    if request.POST.get('date'):
        return redirect(f"/attendance/supervisor/?date={request.POST.get('date')}")
    return redirect('hr_attendance:supervisor_panel')
