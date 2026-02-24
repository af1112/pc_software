from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hr_personnel', '0004_leaverequest_leaveaiinsight_leavepolicy'),
    ]

    operations = [
        migrations.AddField(
            model_name='payrollslip',
            name='payable_days',
            field=models.DecimalField(decimal_places=2, default=30, max_digits=6, verbose_name='Payable Days'),
        ),
        migrations.AddField(
            model_name='payrollslip',
            name='payable_hours',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=8, verbose_name='Payable Hours'),
        ),
        migrations.AddField(
            model_name='payrollslip',
            name='total_allowances',
            field=models.DecimalField(decimal_places=3, default=0, max_digits=12, verbose_name='Total Allowances'),
        ),
        migrations.AddField(
            model_name='payrollslip',
            name='total_benefits',
            field=models.DecimalField(decimal_places=3, default=0, max_digits=12, verbose_name='Total Benefits'),
        ),
        migrations.AddField(
            model_name='payrollslip',
            name='total_deductions',
            field=models.DecimalField(decimal_places=3, default=0, max_digits=12, verbose_name='Total Deductions'),
        ),
        migrations.AddField(
            model_name='salarycomponent',
            name='affects_net_pay',
            field=models.BooleanField(default=True, verbose_name='Affects Net Pay'),
        ),
        migrations.AddField(
            model_name='salarycomponent',
            name='calculation_frequency',
            field=models.CharField(choices=[('monthly', 'Monthly'), ('daily', 'Per Day'), ('hourly', 'Per Hour'), ('one_time', 'One-time')], default='monthly', max_length=20, verbose_name='Calculation Frequency'),
        ),
        migrations.AddField(
            model_name='salarycomponent',
            name='is_active',
            field=models.BooleanField(default=True, verbose_name='Is Active'),
        ),
        migrations.AddField(
            model_name='salarycomponent',
            name='taxable',
            field=models.BooleanField(default=True, verbose_name='Taxable'),
        ),
        migrations.AddField(
            model_name='salaryprofile',
            name='accommodation_provided',
            field=models.BooleanField(default=False, verbose_name='Accommodation Provided'),
        ),
        migrations.AddField(
            model_name='salaryprofile',
            name='compensation_basis',
            field=models.CharField(choices=[('monthly', 'Monthly Salary'), ('daily', 'Daily Wage'), ('hourly', 'Hourly Wage')], default='monthly', max_length=20, verbose_name='Compensation Basis'),
        ),
        migrations.AddField(
            model_name='salaryprofile',
            name='daily_rate',
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=12, null=True, verbose_name='Daily Rate'),
        ),
        migrations.AddField(
            model_name='salaryprofile',
            name='food_provided',
            field=models.BooleanField(default=False, verbose_name='Food Provided'),
        ),
        migrations.AddField(
            model_name='salaryprofile',
            name='hourly_rate',
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=12, null=True, verbose_name='Hourly Rate'),
        ),
        migrations.AddField(
            model_name='salaryprofile',
            name='in_kind_benefits_notes',
            field=models.TextField(blank=True, null=True, verbose_name='In-kind Benefits Notes'),
        ),
        migrations.AddField(
            model_name='salaryprofile',
            name='standard_working_days',
            field=models.DecimalField(decimal_places=2, default=30, max_digits=6, verbose_name='Standard Working Days / Month'),
        ),
        migrations.AddField(
            model_name='salaryprofile',
            name='standard_working_hours_per_day',
            field=models.DecimalField(decimal_places=2, default=8, max_digits=6, verbose_name='Standard Working Hours / Day'),
        ),
        migrations.AddField(
            model_name='salaryprofile',
            name='transport_provided',
            field=models.BooleanField(default=False, verbose_name='Transport Provided'),
        ),
    ]
