import datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from .models import Employee, PayrollPeriod, PayrollSlip, SalaryComponent, SalaryStructure
from .services import PayrollCalculator, PayrollProcessingService


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


class PayrollWorkflowServiceTests(TestCase):
    def setUp(self):
        self.employee = Employee.objects.create(first_name='Reza', last_name='Payroll')
        self.structure = SalaryStructure.objects.create(
            employee=self.employee,
            effective_from=datetime.date(2026, 1, 1),
            pay_type=SalaryStructure.PayType.MONTHLY,
            currency='OMR',
            is_active=True,
        )
        SalaryComponent.objects.create(
            salary_structure=self.structure,
            component_type=SalaryComponent.ComponentType.EARNING,
            title='Basic Salary',
            calculation_method=SalaryComponent.CalculationMethod.FIXED_MONTHLY,
            amount=Decimal('500.000'),
            is_active=True,
        )

    def test_run_period_creates_slip_and_items(self):
        period = PayrollPeriod.objects.create(
            name='2026-01',
            start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 1, 31),
        )

        payroll_run, slips = PayrollProcessingService.run_period(period=period, employees_qs=Employee.objects.all())

        self.assertEqual(payroll_run.status, 'completed')
        self.assertEqual(len(slips), 1)
        slip = PayrollSlip.objects.get(employee=self.employee, period=period)
        self.assertEqual(slip.net_amount, Decimal('500.000'))
        self.assertTrue(slip.items.exists())

    def test_finalized_period_slip_is_locked(self):
        period = PayrollPeriod.objects.create(
            name='2026-02',
            start_date=datetime.date(2026, 2, 1),
            end_date=datetime.date(2026, 2, 28),
            status=PayrollPeriod.Status.FINALIZED,
        )
        slip = PayrollSlip.objects.create(
            employee=self.employee,
            period=period,
            salary_profile=self.structure,
            period_year=2026,
            period_month=2,
            base_salary=Decimal('500.000'),
            gross_amount=Decimal('500.000'),
            net_amount=Decimal('500.000'),
        )

        slip.net_amount = Decimal('490.000')
        with self.assertRaises(ValidationError):
            slip.save()
