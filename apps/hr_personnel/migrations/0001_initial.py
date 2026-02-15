# Generated manually for this repository

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ('organizations', '0003_organization_timezone'),
    ]

    operations = [
        migrations.CreateModel(
            name='Employee',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('first_name', models.CharField(max_length=100, verbose_name='First Name')),
                ('last_name', models.CharField(max_length=100, verbose_name='Last Name')),
                ('national_id', models.CharField(blank=True, max_length=50, null=True, verbose_name='National ID')),
                ('phone', models.CharField(blank=True, max_length=50, null=True, verbose_name='Phone')),
                ('email', models.EmailField(blank=True, max_length=254, null=True, verbose_name='Email')),
                ('department', models.CharField(blank=True, max_length=100, null=True, verbose_name='Department')),
                ('position_title', models.CharField(blank=True, max_length=120, null=True, verbose_name='Position Title')),
                ('hire_date', models.DateField(blank=True, null=True, verbose_name='Hire Date')),
                ('is_active', models.BooleanField(default=True, verbose_name='Is Active')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('organization', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='employees', to='organizations.organization', verbose_name='Organization')),
            ],
            options={
                'verbose_name': 'Employee',
                'verbose_name_plural': 'Employees',
                'ordering': ['last_name', 'first_name'],
            },
        ),
        migrations.CreateModel(
            name='SalaryProfile',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('effective_from', models.DateField(verbose_name='Effective From')),
                ('base_salary', models.DecimalField(decimal_places=3, default=0, max_digits=12, verbose_name='Base Salary')),
                ('currency', models.CharField(default='OMR', max_length=10, verbose_name='Currency')),
                ('notes', models.TextField(blank=True, null=True, verbose_name='Notes')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('employee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='salary_profiles', to='hr_personnel.employee')),
            ],
            options={
                'verbose_name': 'Salary Profile',
                'verbose_name_plural': 'Salary Profiles',
                'ordering': ['-effective_from'],
            },
        ),
        migrations.CreateModel(
            name='SalaryComponent',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('component_type', models.CharField(choices=[('allowance', 'Allowance'), ('deduction', 'Deduction'), ('benefit', 'Benefit')], max_length=20, verbose_name='Type')),
                ('title', models.CharField(max_length=120, verbose_name='Title')),
                ('is_percentage', models.BooleanField(default=False, verbose_name='Is Percentage')),
                ('percentage', models.DecimalField(blank=True, decimal_places=3, max_digits=6, null=True, verbose_name='Percentage')),
                ('amount', models.DecimalField(decimal_places=3, default=0, max_digits=12, verbose_name='Amount')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('salary_profile', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='components', to='hr_personnel.salaryprofile')),
            ],
            options={
                'verbose_name': 'Salary Component',
                'verbose_name_plural': 'Salary Components',
                'ordering': ['component_type', 'title'],
            },
        ),
        migrations.CreateModel(
            name='BankAccount',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('bank_name', models.CharField(max_length=120, verbose_name='Bank Name')),
                ('account_holder', models.CharField(blank=True, max_length=120, null=True, verbose_name='Account Holder')),
                ('account_number', models.CharField(blank=True, max_length=100, null=True, verbose_name='Account Number')),
                ('iban', models.CharField(blank=True, max_length=64, null=True, verbose_name='IBAN')),
                ('is_primary', models.BooleanField(default=False, verbose_name='Is Primary')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('employee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bank_accounts', to='hr_personnel.employee')),
            ],
            options={
                'verbose_name': 'Bank Account',
                'verbose_name_plural': 'Bank Accounts',
                'ordering': ['-is_primary', '-created_at'],
            },
        ),
        migrations.CreateModel(
            name='PayrollSlip',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('period_year', models.IntegerField(verbose_name='Year')),
                ('period_month', models.IntegerField(verbose_name='Month')),
                ('base_salary', models.DecimalField(decimal_places=3, default=0, max_digits=12, verbose_name='Base Salary')),
                ('currency', models.CharField(default='OMR', max_length=10, verbose_name='Currency')),
                ('gross_amount', models.DecimalField(decimal_places=3, default=0, max_digits=12, verbose_name='Gross Amount')),
                ('net_amount', models.DecimalField(decimal_places=3, default=0, max_digits=12, verbose_name='Net Amount')),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('paid', 'Paid')], default='draft', max_length=10, verbose_name='Status')),
                ('paid_at', models.DateTimeField(blank=True, null=True, verbose_name='Paid At')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('bank_account', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='payroll_slips', to='hr_personnel.bankaccount')),
                ('employee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payroll_slips', to='hr_personnel.employee')),
                ('salary_profile', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='payroll_slips', to='hr_personnel.salaryprofile')),
            ],
            options={
                'verbose_name': 'Payroll Slip',
                'verbose_name_plural': 'Payroll Slips',
                'ordering': ['-period_year', '-period_month', '-created_at'],
                'unique_together': {('employee', 'period_year', 'period_month')},
            },
        ),
        migrations.CreateModel(
            name='PayrollItem',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('item_type', models.CharField(choices=[('allowance', 'Allowance'), ('deduction', 'Deduction'), ('benefit', 'Benefit')], max_length=20, verbose_name='Type')),
                ('title', models.CharField(max_length=120, verbose_name='Title')),
                ('amount', models.DecimalField(decimal_places=3, default=0, max_digits=12, verbose_name='Amount')),
                ('payroll_slip', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='hr_personnel.payrollslip')),
            ],
            options={
                'verbose_name': 'Payroll Item',
                'verbose_name_plural': 'Payroll Items',
                'ordering': ['item_type', 'title'],
            },
        ),
    ]
