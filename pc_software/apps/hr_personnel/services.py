from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError

from .models import SalaryComponent, SalaryStructure


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
