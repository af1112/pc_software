from django.contrib import admin
from .models import Attendance, AttendanceAIInsight, Timesheet, AttendanceChangeLog, Holiday


@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display = ['name', 'date', 'holiday_type', 'organization', 'is_recurring']
    list_filter = ['holiday_type', 'is_recurring', 'organization']
    search_fields = ['name', 'notes']
    date_hierarchy = 'date'
    ordering = ['-date']
