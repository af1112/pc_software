from django.contrib import admin
from .models import ExpenseReport, ExpenseItem, Trip, Advance, ExpenseCategory

class ExpenseItemInline(admin.TabularInline):
    model = ExpenseItem
    extra = 1
    fields = ('date', 'category', 'description', 'amount', 'receipt_image', 'is_ai_scanned')
    readonly_fields = ('is_ai_scanned', 'ai_confidence')

@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_by', 'created_at')
    search_fields = ('name',)

@admin.register(Advance)
class AdvanceAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount', 'currency', 'date', 'paid_through')
    list_filter = ('date', 'paid_through')


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_by', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'created_by__username')

@admin.register(ExpenseItem)
class ExpenseItemAdmin(admin.ModelAdmin):
    list_display = ('date', 'category', 'amount', 'currency', 'merchant', 'report')
    list_filter = ('category', 'date', 'report')
    search_fields = ('merchant', 'description', 'category')
    readonly_fields = ('is_ai_scanned', 'ai_confidence', 'raw_ocr_text')

@admin.register(ExpenseReport)
class ExpenseReportAdmin(admin.ModelAdmin):
    list_display = ('title', 'submitted_by', 'total_amount', 'status', 'created_at')
    list_filter = ('status', 'submitted_by', 'created_at')
    inlines = [ExpenseItemInline]
    actions = ['generate_pdf_report']

    def generate_pdf_report(self, request, queryset):
        # Placeholder for PDF generation action
        pass
    generate_pdf_report.short_description = "Download PDF Report"
