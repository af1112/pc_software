from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

User = get_user_model()

class Ticket(models.Model):
    STATUS_CHOICES = [
        ('open', _('Open')),
        ('waiting_response', _('Waiting for Response')),
        ('user_new_message', _('User New Message')),
        ('answered', _('Answered')),
        ('under_review', _('Under Review')),
        ('referred', _('Referred to Expert')),
        ('in_progress', _('In Progress')),
        ('needs_info', _('Needs More Info')),
        ('closed', _('Closed')),
    ]

    PRIORITY_CHOICES = [
        ('low', _('Low')),
        ('medium', _('Medium')),
        ('high', _('High')),
        ('critical', _('Critical')),
    ]

    CATEGORY_CHOICES = [
        ('bug', _('Bug')),
        ('feature', _('Feature Request')),
        ('support', _('Support')),
        ('other', _('Other')),
    ]

    title = models.CharField(_("Title"), max_length=200)
    description = models.TextField(_("Description"))
    
    status = models.CharField(_("Status"), max_length=20, choices=STATUS_CHOICES, default='open')
    priority = models.CharField(_("Priority"), max_length=20, choices=PRIORITY_CHOICES, default='medium')
    category = models.CharField(_("Category"), max_length=20, choices=CATEGORY_CHOICES, default='support')
    
    # Remote Software Fields
    remote_software_name = models.CharField(_("Remote Software Name"), max_length=100, blank=True, null=True)
    remote_software_id = models.CharField(_("Remote Software ID"), max_length=100, blank=True, null=True)
    
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_tickets', verbose_name=_("Created By"))
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_tickets', verbose_name=_("Assigned To"))
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # We will use TicketAttachment model for multiple files
    # attachment field is kept for backward compatibility or can be removed if not needed
    attachment = models.FileField(_("Attachment"), upload_to='tickets/%Y/%m/', blank=True, null=True)

    class Meta:
        verbose_name = _("Ticket")
        verbose_name_plural = _("Tickets")
        ordering = ['-created_at']

    def __str__(self):
        return f"#{self.id} - {self.title}"

class TicketComment(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField(_("Comment"))
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Comment by {self.user} on #{self.ticket.id}"

class TicketAttachment(models.Model):
    FILE_TYPES = [
        ('file', _('File')),
        ('voice', _('Voice')),
        ('video', _('Video')),
    ]
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='attachments', null=True, blank=True)
    comment = models.ForeignKey(TicketComment, on_delete=models.CASCADE, related_name='attachments', null=True, blank=True)
    file = models.FileField(_("File"), upload_to='ticket_attachments/%Y/%m/')
    file_type = models.CharField(_("File Type"), max_length=10, choices=FILE_TYPES, default='file')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Ticket Attachment")
        verbose_name_plural = _("Ticket Attachments")
