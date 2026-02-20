from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Ticket, TicketComment, TicketAttachment
from django.utils.translation import gettext as _
from django.contrib.auth import get_user_model
import json

User = get_user_model()
MAX_TICKET_ATTACHMENTS = 5

@login_required
def ticket_list(request):
    if request.user.is_staff:
        tickets = Ticket.objects.all()
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
        from django.db.models import Q
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

    context = {
        'tickets': tickets,
        'status_choices': Ticket.STATUS_CHOICES,
        'priority_choices': Ticket.PRIORITY_CHOICES,
        'category_choices': Ticket.CATEGORY_CHOICES,
        'users': User.objects.all() if request.user.is_staff else None,
        'selected': {
            'q': q, 'status': status, 'priority': priority, 'category': category, 'created_by': created_by,
            'sort': sort, 'direction': direction,
        }
    }
    return render(request, 'ticketing/ticket_list.html', context)

@login_required
def ticket_detail(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk)
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
            
            # Auto status update based on who replied
            if ticket.status == 'closed':
                ticket.status = 'open'
            elif request.user != ticket.created_by:
                ticket.status = 'answered'
            
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

    context = {
        'ticket': ticket,
        'all_users': User.objects.all() if request.user.is_staff else None,
        'status_choices': Ticket.STATUS_CHOICES
    }
    return render(request, 'ticketing/ticket_detail.html', context)

@login_required
def ticket_assign(request, pk):
    if not request.user.is_staff:
        messages.error(request, _("Only staff can assign tickets."))
        return redirect('ticketing:ticket_detail', pk=pk)
    
    ticket = get_object_or_404(Ticket, pk=pk)
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        if user_id:
            assigned_user = get_object_or_404(User, pk=user_id)
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
    ticket = get_object_or_404(Ticket, pk=pk)
    
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
