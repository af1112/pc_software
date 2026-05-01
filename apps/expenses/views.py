from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Sum, Count
from django.contrib import messages
from .models import ExpenseReport, ExpenseItem, Trip, Advance, ExpenseCategory
from .forms import ExpenseItemForm, TripForm, AdvanceForm, ExpenseReportForm, ExpenseCategoryForm
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.translation import gettext as _
from apps.ai_engine.ocr import extract_receipt_data
from .utils import render_to_pdf
import os
import logging
import tempfile

logger = logging.getLogger(__name__)


def _can_approve_report(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True
    profile = getattr(user, 'profile', None)
    return bool(profile and profile.role in ['admin', 'supervisor'])

def dashboard(request):
    user = request.user if request.user.is_authenticated else None
    
    context = {}
    if user:
        context['unreported_count'] = ExpenseItem.objects.filter(report__isnull=True, created_by=user).count()
        context['unsubmitted_count'] = ExpenseReport.objects.filter(status='draft', submitted_by=user).count()
        context['submitted_count'] = ExpenseReport.objects.filter(status__in=['submitted', 'approved'], submitted_by=user).count()
        context['pending_reports'] = ExpenseReport.objects.filter(status='draft', submitted_by=user).order_by('-created_at')[:5]
        context['recent_trips'] = Trip.objects.filter(created_by=user).order_by('-created_at')[:5]
        context['recent_advances'] = Advance.objects.filter(user=user).order_by('-created_at')[:5]
        # Add recent unreported expenses
        context['recent_unreported'] = ExpenseItem.objects.filter(report__isnull=True, created_by=user).order_by('-created_at')[:5]
    else:
        # Fallback for demo/dev without login
        # Only show public data or nothing, but for now we keep it empty or safe default
        context['unreported_count'] = 0
        context['unsubmitted_count'] = 0
        context['submitted_count'] = 0
        context['pending_reports'] = []
        context['recent_trips'] = []
        context['recent_advances'] = []
        context['recent_unreported'] = []

    return render(request, 'expenses/dashboard.html', context)

def create_trip(request):
    if request.method == 'POST':
        form = TripForm(request.POST)
        if form.is_valid():
            trip = form.save(commit=False)
            if request.user.is_authenticated:
                trip.created_by = request.user
            else:
                # Assign to first user or admin for dev
                from django.contrib.auth import get_user_model
                User = get_user_model()
                trip.created_by = User.objects.first()
            trip.save()
            return redirect('expenses:dashboard')
    else:
        form = TripForm()
    return render(request, 'expenses/trip_form.html', {'form': form})

def create_report(request):
    if request.method == 'POST':
        form = ExpenseReportForm(request.POST)
        if form.is_valid():
            report = form.save(commit=False)
            if request.user.is_authenticated:
                report.submitted_by = request.user
            else:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                report.submitted_by = User.objects.first()
            report.save()
            return redirect('expenses:dashboard')
    else:
        form = ExpenseReportForm()
    return render(request, 'expenses/report_form.html', {'form': form})

def statement_list(request):
    user = request.user if request.user.is_authenticated else None
    selected_status = request.GET.get('status', 'all')
    source = request.GET.get('source', '')

    if user:
        reports = ExpenseReport.objects.filter(submitted_by=user).order_by('-created_at')
    else:
        reports = ExpenseReport.objects.all().order_by('-created_at')

    valid_statuses = {'all', 'draft', 'submitted', 'approved', 'rejected'}
    if selected_status not in valid_statuses:
        selected_status = 'all'
    if selected_status != 'all':
        reports = reports.filter(status=selected_status)
    
    return render(
        request,
        'expenses/statement_list.html',
        {
            'reports': reports,
            'selected_status': selected_status,
            'from_expense_dashboard': source == 'dashboard',
        },
    )


@login_required
def unreported_expenses(request):
    expenses = ExpenseItem.objects.filter(
        created_by=request.user,
        report__isnull=True,
    ).order_by('-date', '-created_at')
    return render(
        request,
        'expenses/unreported_expenses.html',
        {
            'expenses': expenses,
        },
    )

@login_required
def create_advance(request):
    if request.method == 'POST':
        form = AdvanceForm(request.POST, user=request.user)
        if form.is_valid():
            advance = form.save(commit=False)
            if advance.report and advance.report.status != 'draft':
                messages.error(request, _('You can only link advances to draft statements.'))
                return redirect('expenses:create_advance')
            advance.user = request.user
            if hasattr(request.user, 'profile'):
                advance.currency = request.user.profile.currency_code
            advance.save()
            return redirect('expenses:dashboard')
    else:
        form = AdvanceForm(user=request.user)

    user_currency_code = getattr(getattr(request.user, 'profile', None), 'currency_code', 'OMR')
    return render(
        request,
        'expenses/advance_form.html',
        {
            'form': form,
            'user_currency_code': user_currency_code,
        },
    )

def create_expense(request):
    user = request.user if request.user.is_authenticated else None
    edit_id = request.GET.get('edit')
    expense_instance = None
    
    # Handle editing existing expense
    if edit_id:
        try:
            expense_instance = ExpenseItem.objects.get(id=edit_id, created_by=user)
            if expense_instance.report and expense_instance.report.status != 'draft':
                messages.error(request, _('This expense cannot be edited because it belongs to a submitted statement.'))
                return redirect('expenses:dashboard')
        except ExpenseItem.DoesNotExist:
            messages.error(request, _('Expense not found.'))
            return redirect('expenses:dashboard')

    if request.method == 'POST':
        form = ExpenseItemForm(request.POST, request.FILES, user=user, instance=expense_instance)
        if form.is_valid():
            expense = form.save(commit=False)
            if expense.report and expense.report.status != 'draft':
                messages.error(request, _('Selected statement is not editable anymore.'))
                return redirect('expenses:create_expense')
            
            # Ensure created_by is set
            if user:
                expense.created_by = user
                # Enforce currency from profile to be safe
                if hasattr(user, 'profile'):
                    expense.currency = user.profile.currency_code
            
            # Link to report if selected in form, otherwise it's unreported
            # expense.report is already handled by form save if field exists
            expense.save()
            
            # Update report total if linked
            if expense.report:
                expense.report.update_total()
            
            action = "updated" if edit_id else "added"
            messages.success(request, _(f'Expense {action} successfully.'))
            return redirect('expenses:dashboard')
        else:
            # Form errors will be displayed in the template
            pass
    else:
        form = ExpenseItemForm(user=user, instance=expense_instance)

    user_currency_code = getattr(getattr(user, 'profile', None), 'currency_code', 'OMR')
    return render(
        request,
        'expenses/expense_form.html',
        {
            'form': form,
            'merchant_suggestions': getattr(form, 'merchant_suggestions', []),
            'user_currency_code': user_currency_code,
            'editing': bool(edit_id),
        },
    )


@login_required
def category_list(request):
    categories = ExpenseCategory.objects.filter(created_by=request.user).order_by('name')
    form = ExpenseCategoryForm()
    return render(
        request,
        'expenses/category_list.html',
        {
            'categories': categories,
            'form': form,
        },
    )


@login_required
def category_create(request):
    if request.method != 'POST':
        return redirect('expenses:category_list')

    form = ExpenseCategoryForm(request.POST)
    if form.is_valid():
        category = form.save(commit=False)
        category.created_by = request.user
        category.save()
        messages.success(request, _("Category created successfully."))
    else:
        messages.error(request, _("Please correct the category form errors."))

    return redirect('expenses:category_list')


@login_required
def category_update(request, category_id):
    category = get_object_or_404(ExpenseCategory, id=category_id, created_by=request.user)
    if request.method != 'POST':
        return redirect('expenses:category_list')

    form = ExpenseCategoryForm(request.POST, instance=category)
    if form.is_valid():
        form.save()
        messages.success(request, _("Category updated successfully."))
    else:
        messages.error(request, _("Please correct the category form errors."))

    return redirect('expenses:category_list')


@login_required
def category_delete(request, category_id):
    category = get_object_or_404(ExpenseCategory, id=category_id, created_by=request.user)
    if request.method == 'POST':
        category.delete()
        messages.success(request, _("Category deleted."))
    return redirect('expenses:category_list')

def report_detail(request, report_id):
    report = get_object_or_404(ExpenseReport, id=report_id)
    # Group expenses by date or category if needed
    expenses = report.items.all().order_by('date')
    expense_count = expenses.count()
    advances = report.advances.select_related('user').order_by('date', 'created_at')
    advance_count = advances.count()
    total_advances = advances.aggregate(total=Sum('amount'))['total'] or 0
    net_balance = report.total_amount - total_advances
    
    context = {
        'report': report,
        'expenses': expenses,
        'advances': advances,
        'expense_count': expense_count,
        'advance_count': advance_count,
        'total_advances': total_advances,
        'net_balance': net_balance,
        'can_submit': request.user == report.submitted_by and report.status == 'draft',
        'can_approve': _can_approve_report(request.user) and report.status == 'submitted',
        'is_locked': report.status == 'approved',
    }
    return render(request, 'expenses/report_detail.html', context)


@login_required
def submit_report(request, report_id):
    report = get_object_or_404(ExpenseReport, id=report_id, submitted_by=request.user)
    if request.method != 'POST':
        return redirect('expenses:report_detail', report_id=report.id)

    if report.status != 'draft':
        messages.error(request, _('Only draft statements can be submitted.'))
        return redirect('expenses:report_detail', report_id=report.id)

    report.status = 'submitted'
    report.save(update_fields=['status', 'updated_at'])
    messages.success(request, _('Statement submitted for approval.'))
    return redirect('expenses:report_detail', report_id=report.id)


@login_required
def approve_report(request, report_id):
    report = get_object_or_404(ExpenseReport, id=report_id)
    if request.method != 'POST':
        return redirect('expenses:report_detail', report_id=report.id)

    if not _can_approve_report(request.user):
        messages.error(request, _('You are not allowed to approve statements.'))
        return redirect('expenses:report_detail', report_id=report.id)

    if report.status != 'submitted':
        messages.error(request, _('Only submitted statements can be approved.'))
        return redirect('expenses:report_detail', report_id=report.id)

    report.status = 'approved'
    report.save(update_fields=['status', 'updated_at'])
    messages.success(request, _('Statement approved. It is now locked for editing.'))
    return redirect('expenses:report_detail', report_id=report.id)

@csrf_exempt
def scan_receipt_api(request):
    if request.method != 'POST' or not request.FILES.get('image'):
        return JsonResponse({'status': 'error', 'message': _('No image provided')}, status=400)

    image_file = request.FILES['image']
    suffix = os.path.splitext(image_file.name or '')[1] or '.jpg'
    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            for chunk in image_file.chunks():
                temp_file.write(chunk)
            temp_path = temp_file.name

        data = extract_receipt_data(temp_path)
        return JsonResponse({'status': 'success', 'data': data})
    except Exception as e:
        logger.exception('scan_receipt_api failed')
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)

def export_report_pdf(request, report_id):
    report = get_object_or_404(ExpenseReport, id=report_id)
    expenses = report.items.all().order_by('date')
    receipt_items = expenses.exclude(receipt_image='').exclude(receipt_image__isnull=True)

    submitter = report.submitted_by
    submitter_name = submitter.get_full_name().strip() or submitter.username
    organization = getattr(getattr(submitter, 'profile', None), 'organization', None)
    language_code = str(getattr(request, 'LANGUAGE_CODE', '')).lower()
    is_rtl = language_code.startswith('fa') or language_code.startswith('ar')

    pdf = render_to_pdf(
        'expenses/report_pdf.html',
        {
            'report': report,
            'expenses': expenses,
            'receipt_items': receipt_items,
            'organization': organization,
            'submitter_name': submitter_name,
            'is_rtl': is_rtl,
        },
        landscape=True,
    )
    if pdf and isinstance(pdf, HttpResponse):
        filename = f"Expense_Report_{report.title}_{report.created_at.strftime('%Y%m%d')}.pdf"
        pdf['Content-Disposition'] = f"inline; filename={filename}"
        return pdf
    return HttpResponse(_("Error rendering PDF"), status=400)
