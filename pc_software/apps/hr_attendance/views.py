from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from django.contrib import messages
from .models import Attendance
from django.utils.translation import gettext as _
from django.contrib.auth.models import User
from apps.hr_personnel.models import Employee
from apps.expenses.utils import render_to_pdf
import base64
import datetime

def is_supervisor_or_admin(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    try:
        return getattr(user.profile, 'role', 'user') in ['admin', 'supervisor']
    except Exception:
        return False

@login_required
def attendance_dashboard(request):
    # Use organization timezone activated in middleware
    date_str = request.GET.get('date')
    if date_str:
        try:
            selected_date = datetime.date.fromisoformat(date_str)
        except Exception:
            selected_date = timezone.localtime(timezone.now()).date()
    else:
        selected_date = timezone.localtime(timezone.now()).date()
    attendance, created = Attendance.objects.get_or_create(user=request.user, date=today)
    
    recent_attendances = Attendance.objects.filter(user=request.user).order_by('-date')[:5]
    
    # Check if photo is required
    require_photo = True
    if hasattr(request.user, 'profile'):
        require_photo = request.user.profile.require_photo
    
    context = {
        'attendance': attendance,
        'recent_attendances': recent_attendances,
        'today': today,
        'require_photo': require_photo,
    }
    return render(request, 'hr_attendance/dashboard.html', context)

@login_required
def clock_in(request):
    if request.method == 'POST':
        today = timezone.localtime(timezone.now()).date()
        attendance, created = Attendance.objects.get_or_create(user=request.user, date=today)
        
        if not attendance.clock_in:
            attendance.clock_in = timezone.now()
            attendance.clock_in_by = request.user
            
            # Save location if provided
            lat = request.POST.get('latitude')
            lng = request.POST.get('longitude')
            if lat and lng:
                attendance.latitude = lat
                attendance.longitude = lng
            
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
            
    return redirect('hr_attendance:dashboard')

@login_required
def clock_out(request):
    if request.method == 'POST':
        today = timezone.localtime(timezone.now()).date()
        try:
            attendance = Attendance.objects.get(user=request.user, date=today)
            if attendance.clock_in and not attendance.clock_out:
                attendance.clock_out = timezone.now()
                attendance.clock_out_by = request.user
                
                # Update location if provided (exit location)
                lat = request.POST.get('latitude')
                lng = request.POST.get('longitude')
                if lat and lng:
                    attendance.latitude = lat
                    attendance.longitude = lng
                
                # Save photo if provided
                photo_data = request.POST.get('photo')
                if photo_data:
                    # Save the raw base64 string directly to the database
                    # since the filesystem is read-only on production
                    attendance.photo_out = photo_data

                attendance.save()
                messages.success(request, _("Clock-out recorded successfully!"))
            elif not attendance.clock_in:
                messages.error(request, _("You must clock in first."))
            else:
                messages.warning(request, _("You have already clocked out today."))
        except Attendance.DoesNotExist:
            messages.error(request, _("No attendance record found for today. Please clock in first."))
            
    return redirect('hr_attendance:dashboard')


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
    users_qs = User.objects.filter(employee__isnull=False).order_by('username')
    if not request.user.is_superuser and org:
        users_qs = users_qs.filter(employee__organization=org)
    elif not request.user.is_superuser and not org:
        users_qs = User.objects.none()
    today = timezone.localtime(timezone.now()).date()
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

    users_qs = User.objects.filter(employee__isnull=False).order_by('username')
    if not request.user.is_superuser and org:
        users_qs = users_qs.filter(employee__organization=org)
    elif not request.user.is_superuser and not org:
        users_qs = User.objects.none()

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

        attendance, _ = Attendance.objects.get_or_create(user=target, date=selected_date)
        if not attendance.clock_in:
            attendance.clock_in = timezone.now()
            attendance.clock_in_by = request.user
            attendance.save()
            messages.success(request, _("Clock-in recorded for ") + target.username)
        else:
            messages.warning(request, _("The user has already clocked in."))
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

        attendance, _ = Attendance.objects.get_or_create(user=target, date=selected_date)
        if attendance.clock_in and not attendance.clock_out:
            attendance.clock_out = timezone.now()
            attendance.clock_out_by = request.user
            attendance.save()
            messages.success(request, _("Clock-out recorded for ") + target.username)
        elif not attendance.clock_in:
            messages.error(request, _("The user has not clocked in yet."))
        else:
            messages.warning(request, _("The user has already clocked out."))
    if request.POST.get('date'):
        return redirect(f"/attendance/supervisor/?date={request.POST.get('date')}")
    return redirect('hr_attendance:supervisor_panel')
