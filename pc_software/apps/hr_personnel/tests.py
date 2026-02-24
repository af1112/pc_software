import datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from .models import Employee, SalaryComponent, SalaryStructure
from .services import PayrollCalculator


class PayrollCalculatorTests(TestCase):
    def setUp(self):
        self.employee = Employee.objects.create(first_name='Ali', last_name='Tester')

    def test_monthly_calculation_with_extra_earnings_and_deduction(self):
        structure = SalaryStructure.objects.create(
            employee=self.employee,
            effective_from=datetime.date(2026, 1, 1),
            pay_type=SalaryStructure.PayType.MONTHLY,
            currency='OMR',
            is_active=True,
        )
        SalaryComponent.objects.create(
            salary_structure=structure,
            component_type=SalaryComponent.ComponentType.EARNING,
            title='Basic Salary',
            calculation_method=SalaryComponent.CalculationMethod.FIXED_MONTHLY,
            amount=Decimal('1000.000'),
            is_active=True,
        )
        SalaryComponent.objects.create(
            salary_structure=structure,
            component_type=SalaryComponent.ComponentType.EARNING,
            title='Attendance Bonus',
            calculation_method=SalaryComponent.CalculationMethod.PER_DAY,
            amount=Decimal('10.000'),
            is_active=True,
        )
        SalaryComponent.objects.create(
            salary_structure=structure,
            component_type=SalaryComponent.ComponentType.DEDUCTION,
            title='Loan',
            calculation_method=SalaryComponent.CalculationMethod.FIXED_MONTHLY,
            amount=Decimal('50.000'),
            is_active=True,
        )

        result = PayrollCalculator.calculate(
            employee=self.employee,
            period_start=datetime.date(2026, 1, 1),
            period_end=datetime.date(2026, 1, 31),
            worked_days=Decimal('20.00'),
            worked_hours=Decimal('0.00'),
            overtime_hours=Decimal('0.00'),
        )

        self.assertEqual(result['base_pay'], Decimal('1000.000'))
        self.assertEqual(result['total_earnings'], Decimal('1200.000'))
        self.assertEqual(result['total_deductions'], Decimal('50.000'))
        self.assertEqual(result['net_pay'], Decimal('1150.000'))

    def test_daily_calculation(self):
        structure = SalaryStructure.objects.create(
            employee=self.employee,
            effective_from=datetime.date(2026, 1, 1),
            pay_type=SalaryStructure.PayType.DAILY,
            currency='OMR',
            is_active=True,
        )
        SalaryComponent.objects.create(
            salary_structure=structure,
            component_type=SalaryComponent.ComponentType.EARNING,
            title='Daily Wage',
            calculation_method=SalaryComponent.CalculationMethod.PER_DAY,
            amount=Decimal('12.500'),
            is_active=True,
        )
        SalaryComponent.objects.create(
            salary_structure=structure,
            component_type=SalaryComponent.ComponentType.DEDUCTION,
            title='Late Penalty',
            calculation_method=SalaryComponent.CalculationMethod.PER_DAY,
            amount=Decimal('1.000'),
            is_active=True,
        )

        result = PayrollCalculator.calculate(
            employee=self.employee,
            period_start=datetime.date(2026, 2, 1),
            period_end=datetime.date(2026, 2, 28),
            worked_days=Decimal('22.00'),
            worked_hours=Decimal('0.00'),
            overtime_hours=Decimal('0.00'),
        )

        self.assertEqual(result['base_pay'], Decimal('275.000'))
        self.assertEqual(result['total_earnings'], Decimal('275.000'))
        self.assertEqual(result['total_deductions'], Decimal('22.000'))
        self.assertEqual(result['net_pay'], Decimal('253.000'))

    def test_hourly_calculation_with_overtime(self):
        structure = SalaryStructure.objects.create(
            employee=self.employee,
            effective_from=datetime.date(2026, 1, 1),
            pay_type=SalaryStructure.PayType.HOURLY,
            currency='OMR',
            is_active=True,
        )
        SalaryComponent.objects.create(
            salary_structure=structure,
            component_type=SalaryComponent.ComponentType.EARNING,
            title='Hourly Wage',
            calculation_method=SalaryComponent.CalculationMethod.PER_HOUR,
            amount=Decimal('2.000'),
            is_active=True,
        )
        SalaryComponent.objects.create(
            salary_structure=structure,
            component_type=SalaryComponent.ComponentType.DEDUCTION,
            title='Service Fee',
            calculation_method=SalaryComponent.CalculationMethod.FIXED_MONTHLY,
            amount=Decimal('5.000'),
            is_active=True,
        )

        result = PayrollCalculator.calculate(
            employee=self.employee,
            period_start=datetime.date(2026, 3, 1),
            period_end=datetime.date(2026, 3, 31),
            worked_days=Decimal('0.00'),
            worked_hours=Decimal('100.00'),
            overtime_hours=Decimal('5.00'),
        )

        self.assertEqual(result['base_pay'], Decimal('210.000'))
        self.assertEqual(result['total_earnings'], Decimal('210.000'))
        self.assertEqual(result['total_deductions'], Decimal('5.000'))
        self.assertEqual(result['net_pay'], Decimal('205.000'))

    def test_validate_structure_requires_matching_earning_method(self):
        structure = SalaryStructure.objects.create(
            employee=self.employee,
            effective_from=datetime.date(2026, 1, 1),
            pay_type=SalaryStructure.PayType.MONTHLY,
            currency='OMR',
            is_active=True,
        )
        SalaryComponent.objects.create(
            salary_structure=structure,
            component_type=SalaryComponent.ComponentType.EARNING,
            title='Day-linked Only',
            calculation_method=SalaryComponent.CalculationMethod.PER_DAY,
            amount=Decimal('10.000'),
            is_active=True,
        )

        with self.assertRaises(ValidationError):
            PayrollCalculator.validate_structure_components(structure)


class SalaryStructureActiveReplacementTests(TestCase):
    def test_new_active_structure_deactivates_previous_one(self):
        employee = Employee.objects.create(first_name='Sara', last_name='HR')

        first = SalaryStructure.objects.create(
            employee=employee,
            effective_from=datetime.date(2026, 1, 1),
            pay_type=SalaryStructure.PayType.MONTHLY,
            is_active=True,
        )
        second = SalaryStructure.objects.create(
            employee=employee,
            effective_from=datetime.date(2026, 2, 1),
            pay_type=SalaryStructure.PayType.MONTHLY,
            is_active=True,
        )

        first.refresh_from_db()
        second.refresh_from_db()

        self.assertFalse(first.is_active)
        self.assertTrue(second.is_active)
