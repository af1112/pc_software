from decimal import Decimal

from django.db import migrations, models


def _normalize_amount(value):
    amount = Decimal(str(value or 0))
    if amount <= 0:
        return Decimal('0.001')
    return amount


def backfill_salary_components(apps, schema_editor):
    SalaryProfile = apps.get_model('hr_personnel', 'SalaryProfile')
    SalaryComponent = apps.get_model('hr_personnel', 'SalaryComponent')

    type_map = {
        'allowance': 'earning',
        'benefit': 'earning',
        'deduction': 'deduction',
        'earning': 'earning',
    }
    method_map = {
        'monthly': 'fixed_monthly',
        'daily': 'per_day',
        'hourly': 'per_hour',
        'one_time': 'fixed_monthly',
        'fixed_monthly': 'fixed_monthly',
        'per_day': 'per_day',
        'per_hour': 'per_hour',
    }

    for component in SalaryComponent.objects.all().iterator():
        updated = False

        mapped_type = type_map.get(component.component_type)
        if mapped_type and mapped_type != component.component_type:
            component.component_type = mapped_type
            updated = True

        mapped_method = method_map.get(component.calculation_frequency)
        if mapped_method and mapped_method != component.calculation_frequency:
            component.calculation_frequency = mapped_method
            updated = True

        if updated:
            component.save(update_fields=['component_type', 'calculation_frequency'])

    for profile in SalaryProfile.objects.all().iterator():
        earning_components = SalaryComponent.objects.filter(
            salary_profile=profile,
            is_active=True,
            component_type='earning',
        )
        if earning_components.exists():
            continue

        pay_type = getattr(profile, 'compensation_basis', 'monthly') or 'monthly'
        if pay_type == 'daily':
            rate = Decimal(str(profile.daily_rate or 0))
            if rate <= 0:
                standard_days = Decimal(str(profile.standard_working_days or 0))
                base_salary = Decimal(str(profile.base_salary or 0))
                if standard_days > 0:
                    rate = base_salary / standard_days
            calculation_frequency = 'per_day'
            amount = _normalize_amount(rate)
        elif pay_type == 'hourly':
            rate = Decimal(str(profile.hourly_rate or 0))
            if rate <= 0:
                standard_days = Decimal(str(profile.standard_working_days or 0))
                standard_hours = Decimal(str(profile.standard_working_hours_per_day or 0))
                base_salary = Decimal(str(profile.base_salary or 0))
                monthly_hours = standard_days * standard_hours
                if monthly_hours > 0:
                    rate = base_salary / monthly_hours
            calculation_frequency = 'per_hour'
            amount = _normalize_amount(rate)
        else:
            calculation_frequency = 'fixed_monthly'
            amount = _normalize_amount(profile.base_salary)

        SalaryComponent.objects.create(
            salary_profile=profile,
            component_type='earning',
            title='Basic Salary',
            calculation_frequency=calculation_frequency,
            amount=amount,
            is_active=True,
        )


def noop_reverse(apps, schema_editor):
    return


class Migration(migrations.Migration):

    dependencies = [
        ('hr_personnel', '0005_salaryprofile_compensation_updates'),
    ]

    operations = [
        migrations.AddField(
            model_name='salaryprofile',
            name='effective_to',
            field=models.DateField(blank=True, null=True, verbose_name='Effective To'),
        ),
        migrations.AddField(
            model_name='salaryprofile',
            name='is_active',
            field=models.BooleanField(default=True, verbose_name='Is Active'),
        ),
        migrations.AddField(
            model_name='salaryprofile',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
            preserve_default=False,
        ),
        migrations.RunPython(backfill_salary_components, noop_reverse),
    ]
