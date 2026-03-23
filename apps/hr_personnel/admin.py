from django.contrib import admin

from .models import BankAccount, Employee, PayrollItem, PayrollPeriod, PayrollRun, PayrollSlip, SalaryComponent, SalaryProfile


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'department', 'position_title', 'is_active')
    search_fields = ('first_name', 'last_name', 'national_id', 'phone', 'email')


@admin.register(SalaryProfile)
class SalaryProfileAdmin(admin.ModelAdmin):
    list_display = ('employee', 'effective_from', 'pay_type', 'currency', 'is_active')
    list_filter = ('pay_type', 'currency', 'is_active')


@admin.register(SalaryComponent)
class SalaryComponentAdmin(admin.ModelAdmin):
    list_display = ('salary_structure', 'component_type', 'title', 'calculation_method', 'amount', 'is_active')
    list_filter = ('component_type', 'calculation_method', 'is_active')


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = ('employee', 'bank_name', 'iban', 'account_number', 'is_primary')
    list_filter = ('is_primary',)


class PayrollItemInline(admin.TabularInline):
    model = PayrollItem
    extra = 0


@admin.register(PayrollSlip)
class PayrollSlipAdmin(admin.ModelAdmin):
    list_display = ('employee', 'period', 'period_year', 'period_month', 'net_amount', 'currency', 'status')
    list_filter = ('status', 'currency', 'period_year', 'period_month')
    inlines = [PayrollItemInline]


@admin.register(PayrollPeriod)
class PayrollPeriodAdmin(admin.ModelAdmin):
    list_display = ('name', 'organization', 'start_date', 'end_date', 'status')
    list_filter = ('status',)


@admin.register(PayrollRun)
class PayrollRunAdmin(admin.ModelAdmin):
    list_display = ('period', 'status', 'created_by', 'run_date', 'execution_ms')
    list_filter = ('status',)
