from decimal import Decimal, ROUND_HALF_UP
import csv
from io import BytesIO
from time import perf_counter

from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.http import HttpResponse
from django.template.loader import get_template

try:
    from xhtml2pdf import pisa
except ImportError:
    pisa = None

from .models import PayrollItem, PayrollRun, PayrollSlip, SalaryComponent, SalaryStructure


class PayrollCalculator:
    @staticmethod
    def _has_configured_base_rate(salary_structure):
        if salary_structure.pay_type == SalaryStructure.PayType.MONTHLY:
            return Decimal(str(salary_structure.base_salary or 0)) > 0
        if salary_structure.pay_type == SalaryStructure.PayType.DAILY:
            return Decimal(str(salary_structure.daily_rate or salary_structure.base_salary or 0)) > 0
        return Decimal(str(salary_structure.hourly_rate or salary_structure.base_salary or 0)) > 0

    @staticmethod
    def _sum_components(queryset, method):
        total = Decimal('0.000')
        for component in queryset:
            if component.calculation_method == method:
                total += component.amount
        return total

    @classmethod
    def validate_structure_components(cls, salary_structure):
        active_components = salary_structure.components.filter(is_active=True)
        earnings = active_components.filter(component_type=SalaryComponent.ComponentType.EARNING)

        if not earnings.exists() and not cls._has_configured_base_rate(salary_structure):
            raise ValidationError('Configure a base rate or add at least one earning component.')

        required_method = {
            SalaryStructure.PayType.MONTHLY: SalaryComponent.CalculationMethod.FIXED_MONTHLY,
            SalaryStructure.PayType.DAILY: SalaryComponent.CalculationMethod.PER_DAY,
            SalaryStructure.PayType.HOURLY: SalaryComponent.CalculationMethod.PER_HOUR,
        }[salary_structure.pay_type]

        if not earnings.filter(calculation_method=required_method).exists() and not cls._has_configured_base_rate(salary_structure):
            raise ValidationError('Selected pay type requires a matching earning calculation method.')

    @classmethod
    def calculate(cls, employee, period_start, period_end, worked_days=Decimal('0.00'), worked_hours=Decimal('0.00'), overtime_hours=Decimal('0.00')):
        structure = (
            employee.salary_structures.filter(
                is_active=True,
                effective_from__lte=period_end,
            )
            .filter(effective_to__isnull=True)
            .order_by('-effective_from')
            .first()
            or employee.salary_structures.filter(
                is_active=True,
                effective_from__lte=period_end,
                effective_to__gte=period_start,
            )
            .order_by('-effective_from')
            .first()
        )

        if structure is None:
            raise ValidationError('No active salary structure found for employee.')

        components = structure.components.filter(is_active=True)
        earnings = components.filter(component_type=SalaryComponent.ComponentType.EARNING)
        deductions = components.filter(component_type=SalaryComponent.ComponentType.DEDUCTION)

        payable_days_decimal = Decimal(str(worked_days or 0))
        payable_hours_decimal = Decimal(str(worked_hours or 0)) + Decimal(str(overtime_hours or 0))

        if structure.pay_type == SalaryStructure.PayType.MONTHLY:
            base_pay = cls._sum_components(earnings, SalaryComponent.CalculationMethod.FIXED_MONTHLY)
        elif structure.pay_type == SalaryStructure.PayType.DAILY:
            daily_rate = cls._sum_components(earnings, SalaryComponent.CalculationMethod.PER_DAY)
            base_pay = daily_rate * payable_days_decimal
        else:
            hourly_rate = cls._sum_components(earnings, SalaryComponent.CalculationMethod.PER_HOUR)
            base_pay = hourly_rate * payable_hours_decimal

        if base_pay <= Decimal('0.000') and cls._has_configured_base_rate(structure):
            base_pay = structure.resolve_base_pay(
                payable_days=payable_days_decimal,
                payable_hours=payable_hours_decimal,
            )

        other_earnings = Decimal('0.000')
        for component in earnings:
            if structure.pay_type == SalaryStructure.PayType.MONTHLY and component.calculation_method != SalaryComponent.CalculationMethod.FIXED_MONTHLY:
                if component.calculation_method == SalaryComponent.CalculationMethod.PER_DAY:
                    other_earnings += component.amount * Decimal(str(worked_days or 0))
                elif component.calculation_method == SalaryComponent.CalculationMethod.PER_HOUR:
                    other_earnings += component.amount * Decimal(str(worked_hours or 0))
            elif structure.pay_type == SalaryStructure.PayType.DAILY and component.calculation_method != SalaryComponent.CalculationMethod.PER_DAY:
                if component.calculation_method == SalaryComponent.CalculationMethod.FIXED_MONTHLY:
                    other_earnings += component.amount
                elif component.calculation_method == SalaryComponent.CalculationMethod.PER_HOUR:
                    other_earnings += component.amount * Decimal(str(worked_hours or 0))
            elif structure.pay_type == SalaryStructure.PayType.HOURLY and component.calculation_method != SalaryComponent.CalculationMethod.PER_HOUR:
                if component.calculation_method == SalaryComponent.CalculationMethod.FIXED_MONTHLY:
                    other_earnings += component.amount
                elif component.calculation_method == SalaryComponent.CalculationMethod.PER_DAY:
                    other_earnings += component.amount * Decimal(str(worked_days or 0))

        total_deductions = Decimal('0.000')
        for deduction in deductions:
            if deduction.calculation_method == SalaryComponent.CalculationMethod.FIXED_MONTHLY:
                total_deductions += deduction.amount
            elif deduction.calculation_method == SalaryComponent.CalculationMethod.PER_DAY:
                total_deductions += deduction.amount * Decimal(str(worked_days or 0))
            elif deduction.calculation_method == SalaryComponent.CalculationMethod.PER_HOUR:
                total_deductions += deduction.amount * Decimal(str(worked_hours or 0))

        gross = base_pay + other_earnings
        net = gross - total_deductions

        q = Decimal('0.001')
        return {
            'salary_structure': structure,
            'base_pay': base_pay.quantize(q, rounding=ROUND_HALF_UP),
            'total_earnings': gross.quantize(q, rounding=ROUND_HALF_UP),
            'total_deductions': total_deductions.quantize(q, rounding=ROUND_HALF_UP),
            'net_pay': net.quantize(q, rounding=ROUND_HALF_UP),
        }


class PayrollProcessingService:
    @staticmethod
    def _timesheet_totals(employee, period):
        try:
            from apps.hr_attendance.models import Timesheet
        except Exception:
            return Decimal('30.00'), Decimal('0.00'), Decimal('0.00')

        totals = Timesheet.objects.filter(
            employee=employee,
            work_date__gte=period.start_date,
            work_date__lte=period.end_date,
        ).aggregate(
            total_worked_hours=Sum('worked_hours'),
            total_overtime_hours=Sum('overtime_hours'),
        )

        worked_days = Timesheet.objects.filter(
            employee=employee,
            work_date__gte=period.start_date,
            work_date__lte=period.end_date,
            worked_hours__gt=Decimal('0.00'),
        ).values('work_date').distinct().count()

        return (
            Decimal(str(worked_days or 0)),
            Decimal(str(totals.get('total_worked_hours') or 0)),
            Decimal(str(totals.get('total_overtime_hours') or 0)),
        )

    @classmethod
    def run_period(cls, period, employees_qs, created_by=None):
        started_at = perf_counter()
        payroll_run = PayrollRun.objects.create(period=period, created_by=created_by)

        slips = []
        for employee in employees_qs:
            worked_days, worked_hours, overtime_hours = cls._timesheet_totals(employee=employee, period=period)
            result = PayrollCalculator.calculate(
                employee=employee,
                period_start=period.start_date,
                period_end=period.end_date,
                worked_days=worked_days,
                worked_hours=worked_hours,
                overtime_hours=overtime_hours,
            )
            regular_result = PayrollCalculator.calculate(
                employee=employee,
                period_start=period.start_date,
                period_end=period.end_date,
                worked_days=worked_days,
                worked_hours=worked_hours,
                overtime_hours=Decimal('0.00'),
            )
            overtime_amount = (result['total_earnings'] - regular_result['total_earnings']).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)
            if overtime_amount < Decimal('0.000'):
                overtime_amount = Decimal('0.000')

            primary_bank_account = (
                employee.bank_accounts.filter(is_primary=True).order_by('-created_at').first()
                or employee.bank_accounts.order_by('-created_at').first()
            )

            slip, _ = PayrollSlip.objects.update_or_create(
                employee=employee,
                period_year=period.start_date.year,
                period_month=period.start_date.month,
                defaults={
                    'period': period,
                    'salary_profile': result['salary_structure'],
                    'bank_account': primary_bank_account,
                    'base_salary': result['base_pay'],
                    'total_allowances': result['total_earnings'] - result['base_pay'],
                    'total_deductions': result['total_deductions'],
                    'total_benefits': Decimal('0.000'),
                    'overtime_amount': overtime_amount,
                    'gross_amount': result['total_earnings'],
                    'net_amount': result['net_pay'],
                    'gross_salary': result['total_earnings'],
                    'net_salary': result['net_pay'],
                    'currency': result['salary_structure'].currency,
                    'payable_days': worked_days,
                    'payable_hours': worked_hours,
                    'status': PayrollSlip.Status.DRAFT,
                },
            )
            slips.append(slip)
            cls._sync_items_from_structure(slip)

        payroll_run.status = PayrollRun.Status.COMPLETED
        payroll_run.execution_ms = int((perf_counter() - started_at) * 1000)
        payroll_run.save(update_fields=['status', 'execution_ms'])
        return payroll_run, slips

    @staticmethod
    def _sync_items_from_structure(slip):
        if not slip.salary_profile_id:
            return

        existing_keys = {
            (item.component_type.strip().lower(), item.component_name.strip().lower())
            for item in slip.items.all()
        }

        create_items = []
        for component in slip.salary_profile.components.filter(is_active=True):
            component_type = str(component.component_type or '').strip().lower()
            component_name = str(component.title or '').strip()
            key = (component_type, component_name.lower())
            if not component_name or key in existing_keys:
                continue
            amount = component.calculate_amount(
                payable_days=slip.payable_days,
                payable_hours=slip.payable_hours,
            )
            if amount == Decimal('0.000'):
                continue
            create_items.append(
                PayrollItem(
                    payroll_slip=slip,
                    item_type=PayrollItem.ItemType.EARNING if component_type == SalaryComponent.ComponentType.EARNING else PayrollItem.ItemType.DEDUCTION,
                    component_type=component_type,
                    component_name=component_name,
                    title=component_name,
                    amount=amount,
                )
            )

        if create_items:
            PayrollItem.objects.bulk_create(create_items)


def render_payslip_pdf_response(slip, request=None):
    if pisa is None:
        return HttpResponse('PDF generation dependency is not available.', status=503)

    template = get_template('hr_personnel/payslip_pdf.html')
    html = template.render({'slip': slip, 'request': request})
    output = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html.encode('utf-8')), output)
    if pdf.err:
        return HttpResponse('Could not generate PDF payslip.', status=500)

    response = HttpResponse(output.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="payslip-{slip.employee_id}-{slip.period_year}{slip.period_month:02}.pdf"'
    return response


def render_payroll_summary_pdf_response(context):
    if pisa is None:
        return HttpResponse('PDF generation dependency is not available.', status=503)

    template = get_template('hr_personnel/payroll_report_summary_pdf.html')
    html = template.render(context)
    output = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html.encode('utf-8')), output)
    if pdf.err:
        return HttpResponse('Could not generate payroll summary PDF.', status=500)

    response = HttpResponse(output.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="payroll-summary.pdf"'
    return response


def render_bank_payroll_csv_response(rows, selected_period, bank_code):
    bank = str(bank_code or '').strip().lower()
    period_name = getattr(selected_period, 'name', 'payroll') if selected_period is not None else 'payroll'
    safe_period_name = str(period_name).replace(' ', '-')

    if bank == 'bank_muscat':
        headers = [
            'Employee ID',
            'Employee Name',
            'IBAN',
            'Account Number',
            'Bank Name',
            'Net Amount',
            'Currency',
            'Payment Date',
            'Reference',
        ]
        filename = f'bank-muscat-payroll-{safe_period_name}.csv'
    elif bank == 'sohar_international':
        headers = [
            'Staff Number',
            'Beneficiary Name',
            'IBAN',
            'Amount',
            'Currency',
            'Payment Date',
            'Narration',
            'Bank Name',
        ]
        filename = f'sohar-international-payroll-{safe_period_name}.csv'
    else:
        return HttpResponse('Unsupported bank export format.', status=400)

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow(headers)

    payment_date = ''
    if selected_period is not None and getattr(selected_period, 'end_date', None):
        payment_date = selected_period.end_date.isoformat()

    for slip in rows:
        employee = getattr(slip, 'employee', None)
        bank_account = getattr(slip, 'bank_account', None)
        employee_name = ''
        if employee is not None:
            employee_name = f"{employee.first_name or ''} {employee.last_name or ''}".strip()
            if bank_account is None:
                bank_account = (
                    employee.bank_accounts.filter(is_primary=True).order_by('-created_at').first()
                    or employee.bank_accounts.order_by('-created_at').first()
                )

        iban = ''
        account_number = ''
        bank_name = ''
        if bank_account is not None:
            iban = bank_account.iban or ''
            account_number = bank_account.account_number or ''
            bank_name = bank_account.bank_name or ''
        elif employee is not None:
            iban = getattr(employee, 'iban', '') or ''
            bank_name = getattr(employee, 'bank_name', '') or ''

        reference = f"Payroll {period_name}" if period_name else 'Payroll'
        net_amount = Decimal(str(getattr(slip, 'net_amount', 0) or 0)).quantize(Decimal('0.001'))
        currency = getattr(slip, 'currency', '') or ''
        employee_code = getattr(employee, 'employee_id', '') if employee is not None else ''

        if bank == 'bank_muscat':
            writer.writerow([
                employee_code,
                employee_name,
                iban,
                account_number,
                bank_name,
                str(net_amount),
                currency,
                payment_date,
                reference,
            ])
        else:
            writer.writerow([
                employee_code,
                employee_name,
                iban,
                str(net_amount),
                currency,
                payment_date,
                reference,
                bank_name,
            ])

    return response
