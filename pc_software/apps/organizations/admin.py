from django.contrib import admin
from .models import Organization

@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_active', 'subscription_end_date')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    
    fieldsets = (
        (None, {
            'fields': ('name', 'slug', 'logo', 'representative_name', 'representative_phone', 'company_email', 'timezone')
        }),
        ('Subscription Status', {
            'fields': ('is_active', 'subscription_end_date')
        }),
        ('Module Activation (Software Support Only)', {
            'fields': (
                'can_use_expenses', 'can_use_ticketing', 'can_use_attendance', 'can_use_projects',
                'can_use_dms', 'can_use_ai', 'can_use_menu', 'can_use_club'
            ),
            'description': 'Only the software support team should manage these settings.'
        }),
    )

    def get_readonly_fields(self, request, obj=None):
        # If the user is not a superuser, they cannot change module activation
        if not request.user.is_superuser:
            return [
                'can_use_expenses', 'can_use_ticketing', 'can_use_attendance', 'can_use_projects',
                'can_use_dms', 'can_use_ai', 'can_use_menu', 'can_use_club'
            ]
        return super().get_readonly_fields(request, obj)
