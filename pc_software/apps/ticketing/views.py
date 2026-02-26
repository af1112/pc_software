from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import DatabaseError
from django.db.models import Q, Exists, OuterRef, Max
from .models import Ticket, TicketComment, TicketAttachment, TicketReadReceipt
from django.utils.translation import gettext as _
from django.utils import timezone
from django.contrib.auth import get_user_model
from apps.users.templatetags.local_dates import _format_jalali
import json

User = get_user_model()
MAX_TICKET_ATTACHMENTS = 5


def _normalize_digits(value):
    if value is None:
        return ""
    return str(value).translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))


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
        localized_category_choices.append((val, str(label)))

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


def _ticket_matches_query(ticket, query, is_fa):
    q = _normalize_digits(query).lower().replace("/", "-")
    if not q:
        return True

    serial_text = _normalize_digits(ticket.serial_display).lower()
    if q in serial_text:
        return True

    title_text = str(ticket.title or "").lower()
    description_text = str(ticket.description or "").lower()
    if q in title_text or q in description_text:
        return True

    local_dt = timezone.localtime(ticket.created_at)
    gregorian_full = local_dt.strftime("%Y-%m-%d %H:%M").lower()
    gregorian_date = local_dt.strftime("%Y-%m-%d").lower()
    gregorian_time = local_dt.strftime("%H:%M").lower()
    if q in gregorian_full or q in gregorian_date or q in gregorian_time:
        return True

    if is_fa:
        jalali_full = _normalize_digits(_format_jalali(local_dt, "Y-m-d H:i")).lower()
        jalali_date = _normalize_digits(_format_jalali(local_dt, "Y-m-d")).lower()
        if q in jalali_full or q in jalali_date:
            return True

    return False


def _ticket_matches_extra_filters(ticket, serial_query, date_query, time_query, is_fa):
    serial_q = _normalize_digits(serial_query).lower().strip()
    date_q = _normalize_digits(date_query).lower().strip().replace("/", "-")
    time_q = _normalize_digits(time_query).lower().strip()

    if serial_q:
        serial_text = _normalize_digits(ticket.serial_display).lower()
        issuer_serial_text = _normalize_digits(ticket.issuer_serial or "").lower()
        if serial_q not in serial_text and serial_q not in issuer_serial_text:
            return False

    local_dt = timezone.localtime(ticket.created_at)

    if date_q:
        gregorian_date = local_dt.strftime("%Y-%m-%d").lower()
        if date_q not in gregorian_date:
            if not is_fa:
                return False
            jalali_date = _normalize_digits(_format_jalali(local_dt, "Y-m-d")).lower()
            if date_q not in jalali_date:
                return False

    if time_q:
        gregorian_time = local_dt.strftime("%H:%M").lower()
        if time_q not in gregorian_time:
            return False

    return True


@login_required
def ticket_list(request):
    if request.user.is_staff:
        tickets = _organization_tickets(request)
    else:
        tickets = Ticket.objects.filter(created_by=request.user)

    tickets = tickets.annotate(
        has_ticket_attachment=Exists(TicketAttachment.objects.filter(ticket_id=OuterRef('pk'))),
        has_comment_attachment=Exists(TicketAttachment.objects.filter(comment__ticket_id=OuterRef('pk'))),
    )

    q = request.GET.get('q', '').strip()
    serial = request.GET.get('serial', '').strip()
    date = request.GET.get('date', '').strip()
    time = request.GET.get('time', '').strip()
    status = request.GET.get('status') or ''
    priority = request.GET.get('priority') or ''
    category = request.GET.get('category') or ''
    created_by = request.GET.get('created_by') or ''
    sort = request.GET.get('sort') or 'created_at'
    direction = request.GET.get('direction') or 'desc'

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
        'serial': 'issuer_serial',
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

    if q or serial or date or time:
        tickets = [
            t for t in tickets
            if (not q or _ticket_matches_query(t, q, is_fa))
            and _ticket_matches_extra_filters(t, serial, date, time, is_fa)
        ]

    if not isinstance(tickets, list):
        tickets = list(tickets)

    ticket_ids = [ticket.id for ticket in tickets]
    read_receipts = {
        row['ticket_id']: row['last_read_at']
        for row in TicketReadReceipt.objects.filter(user=request.user, ticket_id__in=ticket_ids)
        .values('ticket_id', 'last_read_at')
    }

    latest_other_comment_at = {
        row['ticket_id']: row['latest_at']
        for row in TicketComment.objects.filter(ticket_id__in=ticket_ids)
        .exclude(user=request.user)
        .values('ticket_id')
        .annotate(latest_at=Max('created_at'))
    }

    for ticket in tickets:
        last_read_at = read_receipts.get(ticket.id)
        if not last_read_at:
            ticket.is_unread_for_current_user = True
            continue

        other_latest_at = latest_other_comment_at.get(ticket.id)
        ticket.is_unread_for_current_user = bool(other_latest_at and other_latest_at > last_read_at)

    localized_status_choices, localized_priority_choices, localized_category_choices = _localized_ticket_choices(is_fa)

    context = {
        'tickets': tickets,
        'active_timezone': timezone.get_current_timezone_name(),
        'status_choices': localized_status_choices,
        'priority_choices': localized_priority_choices,
        'category_choices': localized_category_choices,
        'users': _organization_users(request) if request.user.is_staff else None,
        'selected': {
            'q': q,
            'serial': serial,
            'date': date,
            'time': time,
            'status': status,
            'priority': priority,
            'category': category,
            'created_by': created_by,
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

    read_receipt, created = TicketReadReceipt.objects.get_or_create(
        ticket=ticket,
        user=request.user,
    )
    if not created:
        read_receipt.save(update_fields=['last_read_at'])

    if request.method == 'POST':
        content = request.POST.get('content')
        if content:
            comment = TicketComment.objects.create(
                ticket=ticket,
                user=request.user,
                content=content
            )
            
            next_status = ticket.status
            if ticket.status == 'closed':
                next_status = 'open'
            elif ticket.status in ('open', 'waiting_response', 'answered', 'user_new_message'):
                next_status = 'answered' if request.user != ticket.created_by else 'user_new_message'

            if next_status != ticket.status:
                try:
                    Ticket.objects.filter(pk=ticket.pk).update(status=next_status)
                    ticket.status = next_status
                except DatabaseError:
                    # Keep comment submission successful even if status metadata update fails.
                    messages.warning(request, _("Comment saved, but ticket status could not be updated."))
            
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
