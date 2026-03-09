from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO
from time import perf_counter

from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.template.loader import get_template

try:
    from xhtml2pdf import pisa
except ImportError:
    pisa = None

from .models import PayrollItem, PayrollRun, PayrollSlip, SalaryComponent, SalaryStructure


class PayrollCalculator:
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

        if not earnings.exists():
            raise ValidationError('At least one earning component is required.')

        required_method = {
            SalaryStructure.PayType.MONTHLY: SalaryComponent.CalculationMethod.FIXED_MONTHLY,
            SalaryStructure.PayType.DAILY: SalaryComponent.CalculationMethod.PER_DAY,
            SalaryStructure.PayType.HOURLY: SalaryComponent.CalculationMethod.PER_HOUR,
        }[salary_structure.pay_type]

        if not earnings.filter(calculation_method=required_method).exists():
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

        if structure.pay_type == SalaryStructure.PayType.MONTHLY:
            base_pay = cls._sum_components(earnings, SalaryComponent.CalculationMethod.FIXED_MONTHLY)
        elif structure.pay_type == SalaryStructure.PayType.DAILY:
            daily_rate = cls._sum_components(earnings, SalaryComponent.CalculationMethod.PER_DAY)
            base_pay = daily_rate * Decimal(str(worked_days or 0))
        else:
            hourly_rate = cls._sum_components(earnings, SalaryComponent.CalculationMethod.PER_HOUR)
            base_pay = hourly_rate * (Decimal(str(worked_hours or 0)) + Decimal(str(overtime_hours or 0)))

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
    @classmethod
    def run_period(cls, period, employees_qs, created_by=None):
        started_at = perf_counter()
        payroll_run = PayrollRun.objects.create(period=period, created_by=created_by)

        slips = []
        for employee in employees_qs:
            result = PayrollCalculator.calculate(
                employee=employee,
                period_start=period.start_date,
                period_end=period.end_date,
                worked_days=Decimal('30.00'),
                worked_hours=Decimal('0.00'),
                overtime_hours=Decimal('0.00'),
            )

            slip, _ = PayrollSlip.objects.update_or_create(
                employee=employee,
                period_year=period.start_date.year,
                period_month=period.start_date.month,
                defaults={
                    'period': period,
                    'salary_profile': result['salary_structure'],
                    'base_salary': result['base_pay'],
                    'total_allowances': result['total_earnings'] - result['base_pay'],
                    'total_deductions': result['total_deductions'],
                    'total_benefits': Decimal('0.000'),
                    'overtime_amount': Decimal('0.000'),
                    'gross_amount': result['total_earnings'],
                    'net_amount': result['net_pay'],
                    'gross_salary': result['total_earnings'],
                    'net_salary': result['net_pay'],
                    'currency': result['salary_structure'].currency,
                    'payable_days': Decimal('30.00'),
                    'payable_hours': Decimal('0.00'),
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
