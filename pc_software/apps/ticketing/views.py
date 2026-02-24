from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from .models import Ticket, TicketComment, TicketAttachment
from django.utils.translation import gettext as _
from django.utils import timezone
from django.contrib.auth import get_user_model
import json

User = get_user_model()
MAX_TICKET_ATTACHMENTS = 5


def _localized_ticket_choices(is_fa):
    status_fa = {
        'open': 'باز',
        'waiting_response': 'منتظر پاسخگویی',
        'user_new_message': 'پیام جدید کاربر',
        'answered': 'پاسخ داده شده',
        'under_review': 'در حال بررسی',
        'referred': 'ارجاع به کارشناس',
        'in_progress': 'در دست انجام',
        'needs_info': 'نیاز به اطلاعات بیشتر',
        'closed': 'بسته شده',
    }
    priority_fa = {
        'low': 'کم',
        'medium': 'متوسط',
        'high': 'زیاد',
        'critical': 'بحرانی',
    }
    category_fa = {
        'bug': 'باگ',
        'feature': 'درخواست قابلیت',
        'support': 'پشتیبانی',
        'other': 'سایر',
    }

    localized_status_choices = []
    for val, label in Ticket.STATUS_CHOICES:
        if is_fa:
            label = status_fa.get(val, label)
        localized_status_choices.append((val, label))

    localized_priority_choices = []
    for val, label in Ticket.PRIORITY_CHOICES:
        if is_fa:
            label = priority_fa.get(val, label)
        localized_priority_choices.append((val, label))

    localized_category_choices = []
    for val, label in Ticket.CATEGORY_CHOICES:
        if is_fa:
            label = category_fa.get(val, label)
        localized_category_choices.append((val, label))

    return localized_status_choices, localized_priority_choices, localized_category_choices


def _organization_users(request):
    users = User.objects.all()
    org = getattr(request, 'organization', None)
    if org is not None:
        users = users.filter(profile__organization=org)
    return users.distinct()


def _organization_tickets(request):
    org = getattr(request, 'organization', None)
    if org is None:
        return Ticket.objects.all()

    return Ticket.objects.filter(
        Q(created_by__profile__organization=org)
        | Q(assigned_to__profile__organization=org)
    ).distinct()

@login_required
def ticket_list(request):
    if request.user.is_staff:
        tickets = _organization_tickets(request)
    else:
        tickets = Ticket.objects.filter(created_by=request.user)

    q = request.GET.get('q', '').strip()
    status = request.GET.get('status') or ''
    priority = request.GET.get('priority') or ''
    category = request.GET.get('category') or ''
    created_by = request.GET.get('created_by') or ''
    sort = request.GET.get('sort') or 'created_at'
    direction = request.GET.get('direction') or 'desc'

    if q:
        tickets = tickets.filter(Q(title__icontains=q) | Q(description__icontains=q))
    if status:
        tickets = tickets.filter(status=status)
    if priority:
        tickets = tickets.filter(priority=priority)
    if category:
        tickets = tickets.filter(category=category)
    if created_by and request.user.is_staff:
        tickets = tickets.filter(created_by_id=created_by)

    sortable_fields = {
        'id': 'id',
        'created_at': 'created_at',
        'title': 'title',
        'status': 'status',
        'created_by': 'created_by__username',
        'category': 'category',
        'priority': 'priority',
    }
    if sort not in sortable_fields:
        sort = 'created_at'
    if direction not in ('asc', 'desc'):
        direction = 'desc'

    sort_field = sortable_fields[sort]
    if direction == 'desc':
        sort_field = f'-{sort_field}'
    tickets = tickets.order_by(sort_field)

    lang = (getattr(request, 'LANGUAGE_CODE', '') or '').lower()
    is_fa = lang.startswith('fa')
    localized_status_choices, localized_priority_choices, localized_category_choices = _localized_ticket_choices(is_fa)

    context = {
        'tickets': tickets,
        'active_timezone': timezone.get_current_timezone_name(),
        'status_choices': localized_status_choices,
        'priority_choices': localized_priority_choices,
        'category_choices': localized_category_choices,
        'users': _organization_users(request) if request.user.is_staff else None,
        'selected': {
            'q': q, 'status': status, 'priority': priority, 'category': category, 'created_by': created_by,
            'sort': sort, 'direction': direction,
        }
    }
    return render(request, 'ticketing/ticket_list.html', context)

@login_required
def ticket_detail(request, pk):
    ticket_scope = _organization_tickets(request) if request.user.is_staff else Ticket.objects.all()
    ticket = get_object_or_404(ticket_scope, pk=pk)
    if ticket.created_by != request.user and not request.user.is_staff and ticket.assigned_to != request.user:
        messages.error(request, _("You do not have permission to view this ticket."))
        return redirect('ticketing:ticket_list')

    if request.method == 'POST':
        content = request.POST.get('content')
        if content:
            comment = TicketComment.objects.create(
                ticket=ticket,
                user=request.user,
                content=content
            )
            
            if ticket.status == 'closed':
                ticket.status = 'open'
            else:
                if ticket.status in ('open', 'waiting_response', 'answered', 'user_new_message'):
                    ticket.status = 'answered' if request.user != ticket.created_by else 'user_new_message'
            
            ticket.save()
            
            # Handle multiple file attachments
            files = request.FILES.getlist('attachments')
            for f in files:
                TicketAttachment.objects.create(
                    comment=comment,
                    file=f,
                    file_type='file'
                )
            
            # Handle voice recording
            voice_data = request.FILES.get('voice_recording')
            if voice_data:
                TicketAttachment.objects.create(
                    comment=comment,
                    file=voice_data,
                    file_type='voice'
                )
                
            # Handle video recording
            video_data = request.FILES.get('video_recording')
            if video_data:
                TicketAttachment.objects.create(
                    comment=comment,
                    file=video_data,
                    file_type='video'
                )

            messages.success(request, _("Comment added."))
            return redirect('ticketing:ticket_detail', pk=pk)

    lang = (getattr(request, 'LANGUAGE_CODE', '') or '').lower()
    is_fa = lang.startswith('fa')
    localized_status_choices, _, _ = _localized_ticket_choices(is_fa)

    status_display = ticket.get_status_display()
    if is_fa:
        status_display_map = dict(localized_status_choices)
        status_display = status_display_map.get(ticket.status, status_display)

    context = {
        'ticket': ticket,
        'active_timezone': timezone.get_current_timezone_name(),
        'all_users': _organization_users(request) if request.user.is_staff else None,
        'status_choices': localized_status_choices,
        'status_display': status_display,
    }
    return render(request, 'ticketing/ticket_detail.html', context)

@login_required
def ticket_assign(request, pk):
    if not request.user.is_staff:
        messages.error(request, _("Only staff can assign tickets."))
        return redirect('ticketing:ticket_detail', pk=pk)
    
    ticket = get_object_or_404(_organization_tickets(request), pk=pk)
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        if user_id:
            assigned_user = get_object_or_404(_organization_users(request), pk=user_id)
            ticket.assigned_to = assigned_user
            ticket.status = 'referred'
            ticket.save()
            messages.success(request, _("Ticket assigned to %(user)s.") % {'user': assigned_user.username})
        else:
            ticket.assigned_to = None
            ticket.save()
            messages.success(request, _("Ticket unassigned."))
            
    return redirect('ticketing:ticket_detail', pk=pk)

@login_required
def ticket_update_status(request, pk):
    ticket_scope = _organization_tickets(request) if request.user.is_staff else Ticket.objects.all()
    ticket = get_object_or_404(ticket_scope, pk=pk)
    
    # Check permissions: Staff can change to anything, Creator can only close
    is_creator = (ticket.created_by == request.user)
    is_staff = request.user.is_staff
    
    if not (is_creator or is_staff):
        messages.error(request, _("Permission denied."))
        return redirect('ticketing:ticket_detail', pk=pk)

    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status:
            if not is_staff and new_status != 'closed':
                messages.error(request, _("You can only close your own tickets."))
            else:
                ticket.status = new_status
                ticket.save()
                messages.success(request, _("Status updated to %(status)s.") % {'status': ticket.get_status_display()})
                
    return redirect('ticketing:ticket_detail', pk=pk)

@login_required
def ticket_create(request):
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        priority = request.POST.get('priority')
        category = request.POST.get('category')
        remote_software_name = request.POST.get('remote_software_name')
        remote_software_id = request.POST.get('remote_software_id')
        files = request.FILES.getlist('attachments')

        if len(files) > MAX_TICKET_ATTACHMENTS:
            messages.error(
                request,
                _("You can upload up to %(max_count)s files per ticket.") % {'max_count': MAX_TICKET_ATTACHMENTS}
            )
            return render(request, 'ticketing/ticket_form.html', context={})
        
        if title and description:
            ticket = Ticket.objects.create(
                title=title,
                description=description,
                priority=priority,
                category=category,
                remote_software_name=remote_software_name,
                remote_software_id=remote_software_id,
                created_by=request.user
            )
            
            # Handle multiple file attachments
            for f in files:
                TicketAttachment.objects.create(
                    ticket=ticket,
                    file=f,
                    file_type='file'
                )

            # Handle voice recording
            voice_data = request.FILES.get('voice_recording')
            if voice_data:
                TicketAttachment.objects.create(
                    ticket=ticket,
                    file=voice_data,
                    file_type='voice'
                )
                
            # Handle video recording
            video_data = request.FILES.get('video_recording')
            if video_data:
                TicketAttachment.objects.create(
                    ticket=ticket,
                    file=video_data,
                    file_type='video'
                )

            messages.success(request, _("Ticket created successfully."))
            return redirect('ticketing:ticket_list')
        else:
            messages.error(request, _("Please fill in all required fields."))
            
    return render(request, 'ticketing/ticket_form.html', context={})
