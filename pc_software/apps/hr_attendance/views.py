from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from django.contrib import messages
from .models import Attendance, AttendanceAIInsight, Timesheet
from django.utils.translation import gettext as _
from django.contrib.auth.models import User
from apps.hr_personnel.models import Employee, LeaveAIInsight, LeaveRequest
from apps.expenses.utils import render_to_pdf
import base64
import calendar
import datetime


def _worked_hours(clock_in, clock_out):
    if not clock_in or not clock_out:
        return 0.0
    seconds = (clock_out - clock_in).total_seconds()
    if seconds <= 0:
        return 0.0
    return seconds / 3600


def _build_attendance_overview(request, selected_date):
    org = getattr(request, 'organization', None)
    employees_qs = Employee.objects.select_related('user', 'reporting_manager').all()
    if org:
        employees_qs = employees_qs.filter(organization=org)

    user_ids = list(employees_qs.exclude(user__isnull=True).values_list('user_id', flat=True))

    today_records = Attendance.objects.filter(user_id__in=user_ids, date=selected_date)
    checked_in_count = today_records.filter(clock_in__isnull=False).count()
    checked_out_count = today_records.filter(clock_out__isnull=False).count()

    total_employees = employees_qs.count()
    absent_count = max(total_employees - checked_in_count, 0)

    total_worked_hours_today = 0.0
    for row in today_records:
        total_worked_hours_today += _worked_hours(row.clock_in, row.clock_out)

    divisor = checked_out_count or checked_in_count or 1
    avg_worked_hours_today = total_worked_hours_today / divisor

    week_start = selected_date - datetime.timedelta(days=6)
    week_days = [week_start + datetime.timedelta(days=i) for i in range(7)]
    weekly_records = Attendance.objects.filter(
        user_id__in=user_ids,
        date__range=(week_start, selected_date),
        clock_in__isnull=False,
        clock_out__isnull=False,
    ).order_by('date')

    daily_hours = {day: 0.0 for day in week_days}
    for rec in weekly_records:
        daily_hours[rec.date] = daily_hours.get(rec.date, 0.0) + _worked_hours(rec.clock_in, rec.clock_out)

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
    employee = getattr(attendance.user, 'employee', None)
    if not employee:
        return

    worked_hours = _worked_hours(attendance.clock_in, attendance.clock_out)
    overtime_hours = max(worked_hours - 8, 0)
    late_minutes = 0
    early_leave_minutes = 0

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


def _clock_redirect(request):
    if request.POST.get('next') == 'quick_success':
        return redirect('hr_attendance:quick_clock_success')
    if request.POST.get('next') == 'clock_center':
        return redirect('hr_attendance:clock_center')
    if request.POST.get('next') == 'quick':
        return redirect('hr_attendance:quick_clock')
    if not is_supervisor_or_admin(request.user):
        return redirect('hr_attendance:quick_clock')
    return redirect('hr_attendance:dashboard')


def _clock_center_context(request, selected_date):
    attendance, _ = Attendance.objects.get_or_create(user=request.user, date=selected_date)
    recent_attendances = Attendance.objects.filter(user=request.user).order_by('-date')[:10]

    require_photo = True
    if hasattr(request.user, 'profile'):
        require_photo = request.user.profile.require_photo

    return {
        'attendance': attendance,
        'recent_attendances': recent_attendances,
        'today': selected_date,
        'require_photo': require_photo,
    }


def _monthly_attendance_summary(user):
    today = timezone.localtime(timezone.now()).date()
    month_start = today.replace(day=1)
    month_end = today

    records = Attendance.objects.filter(user=user, date__range=(month_start, month_end)).order_by('date')
    days_present = records.filter(clock_in__isnull=False).count()
    days_absent = max((month_end - month_start).days + 1 - days_present, 0)
    total_worked_hours = 0.0
    for row in records:
        total_worked_hours += _worked_hours(row.clock_in, row.clock_out)

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
    try:
        org = request.user.profile.organization
    except Exception:
        org = None

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
            users_qs = users_qs.filter(profile__supervisor=request.user).exclude(profile__role='admin').exclude(is_superuser=True)

    return users_qs


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
    month_start = _parse_month_start(request.GET.get('month'), today)
    month_days = calendar.monthrange(month_start.year, month_start.month)[1]
    month_end = month_start.replace(day=month_days)

    users_qs = _attendance_users_for_manager(request)
    selected_user = None
    user_id = request.GET.get('user_id')

    if user_id:
        selected_user = users_qs.filter(id=user_id).first()
    if not selected_user:
        selected_user = users_qs.first()

    rows = []
    summary = {
        'days_present': 0,
        'days_absent': 0,
        'total_worked_hours': 0.0,
    }

    if selected_user:
        attendances = Attendance.objects.filter(
            user=selected_user,
            date__range=(month_start, month_end),
        ).order_by('date')
        attendance_by_date = {item.date: item for item in attendances}

        employee = getattr(selected_user, 'employee', None)
        if employee:
            timesheets = Timesheet.objects.filter(
                employee=employee,
                work_date__range=(month_start, month_end),
            )
            timesheet_by_date = {item.work_date: item for item in timesheets}
        else:
            timesheet_by_date = {}

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
        'users': users_qs,
        'selected_user': selected_user,
        'selected_user_id': str(selected_user.id) if selected_user else '',
        'month_value': month_start.strftime('%Y-%m'),
        'rows': rows,
        'summary': {
            'days_present': summary['days_present'],
            'days_absent': summary['days_absent'],
            'total_worked_hours': round(summary['total_worked_hours'], 2),
        },
    }
    return render(request, 'hr_attendance/attendance_card.html', context)


@login_required
def quick_clock(request):
    selected_date = timezone.localtime(timezone.now()).date()
    attendance, _ = Attendance.objects.get_or_create(user=request.user, date=selected_date)
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
    attendance, _ = Attendance.objects.get_or_create(user=request.user, date=selected_date)
    context = {
        'attendance': attendance,
        'today': selected_date,
        'summary': _monthly_attendance_summary(request.user),
        'can_clock_out': bool(attendance.clock_in and not attendance.clock_out),
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
            worked_hours = _worked_hours(attendance.clock_in, attendance.clock_out)

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
        attendance, created = Attendance.objects.get_or_create(user=request.user, date=today)
        
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
        else:
            messages.warning(request, _("You have already clocked in today."))
            
    return _clock_redirect(request)

@login_required
def clock_out(request):
    if request.method == 'POST':
        today = timezone.localtime(timezone.now()).date()
        try:
            attendance = Attendance.objects.get(user=request.user, date=today)
            if attendance.clock_in and not attendance.clock_out:
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
                messages.warning(request, _("You have already clocked out today."))
        except Attendance.DoesNotExist:
            messages.error(request, _("No attendance record found for today. Please clock in first."))
            
    return _clock_redirect(request)


@login_required
@user_passes_test(is_supervisor_or_admin)
def supervisor_panel(request):
    """
    Supervisor dashboard to record clock-in/out for users in the same organization.
    """
    # Determine organization
    org = None
    try:
        org = request.user.profile.organization
    except Exception:
        org = None
    users_qs = User.objects.filter(employee__isnull=False).select_related('profile').order_by('username')
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
            users_qs = users_qs.filter(profile__supervisor=request.user).exclude(profile__role='admin').exclude(is_superuser=True)

    date_str = request.GET.get('date')
    if date_str:
        try:
            selected_date = datetime.date.fromisoformat(date_str)
        except Exception:
            selected_date = timezone.localtime(timezone.now()).date()
    else:
        selected_date = timezone.localtime(timezone.now()).date()

    # Build list with selected date attendance
    records = []
    for u in users_qs:
        att = Attendance.objects.filter(user=u, date=selected_date).first()
        employee = getattr(u, 'employee', None)
        records.append({
            'user': u,
            'employee': employee,
            'attendance': att
        })

    pdf_url = request.build_absolute_uri(
        f"/attendance/supervisor/pdf/?date={selected_date.isoformat()}"
    )

    return render(request, 'hr_attendance/supervisor_panel.html', {
        'records': records,
        'today': selected_date,
        'selected_date': selected_date,
        'date_str': selected_date.isoformat(),
        'pdf_url': pdf_url,
    })


@login_required
@user_passes_test(is_supervisor_or_admin)
def supervisor_report_pdf(request):
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

    users_qs = User.objects.filter(employee__isnull=False).select_related('profile').order_by('username')
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
            users_qs = users_qs.filter(profile__supervisor=request.user).exclude(profile__role='admin').exclude(is_superuser=True)

    records = []
    for u in users_qs:
        att = Attendance.objects.filter(user=u, date=selected_date).first()
        employee = getattr(u, 'employee', None)
        records.append({'user': u, 'employee': employee, 'attendance': att})

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

        attendance, created = Attendance.objects.get_or_create(user=target, date=selected_date)
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

        attendance, created = Attendance.objects.get_or_create(user=target, date=selected_date)
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
