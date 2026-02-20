import django.db.models.deletion
import uuid
from decimal import Decimal

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hrms', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='employee',
            name='ai_attrition_risk_score',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True),
        ),
        migrations.CreateModel(
            name='LeaveType',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=120)),
                ('code', models.CharField(max_length=40)),
                ('leave_category', models.CharField(choices=[('annual', 'Annual'), ('sick', 'Sick'), ('unpaid', 'Unpaid'), ('emergency', 'Emergency'), ('maternity', 'Maternity'), ('haj', 'Haj'), ('other', 'Other')], default='annual', max_length=20)),
                ('accrual_method', models.CharField(choices=[('monthly', 'Monthly'), ('yearly', 'Yearly'), ('none', 'None')], default='none', max_length=10)),
                ('accrual_rate_per_month', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=6)),
                ('max_balance', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=8)),
                ('carry_forward_allowed', models.BooleanField(default=False)),
                ('max_carry_forward', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=8)),
                ('encashable', models.BooleanField(default=False)),
                ('requires_attachment', models.BooleanField(default=False)),
                ('requires_approval', models.BooleanField(default=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='leave_types', to='hrms.company')),
            ],
        ),
        migrations.CreateModel(
            name='PayrollPeriod',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=120)),
                ('start_date', models.DateField()),
                ('end_date', models.DateField()),
                ('pay_date', models.DateField()),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('processing', 'Processing'), ('closed', 'Closed')], default='draft', max_length=12)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payroll_periods', to='hrms.company')),
            ],
        ),
        migrations.CreateModel(
            name='SalaryStructure',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('basic_salary', models.DecimalField(decimal_places=3, default=Decimal('0.000'), max_digits=14)),
                ('housing_allowance', models.DecimalField(decimal_places=3, default=Decimal('0.000'), max_digits=14)),
                ('transport_allowance', models.DecimalField(decimal_places=3, default=Decimal('0.000'), max_digits=14)),
                ('other_allowances', models.DecimalField(decimal_places=3, default=Decimal('0.000'), max_digits=14)),
                ('effective_from', models.DateField()),
                ('effective_to', models.DateField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('employee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='salary_structures', to='hrms.employee')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='salary_structures', to='hrms.company')),
            ],
        ),
        migrations.CreateModel(
            name='LeaveBalance',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('balance_days', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=8)),
                ('last_accrual_date', models.DateField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('employee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='leave_balances', to='hrms.employee')),
                ('leave_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='balances', to='hrms.leavetype')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='leave_balances', to='hrms.company')),
            ],
        ),
        migrations.CreateModel(
            name='LeaveRequest',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('start_date', models.DateField()),
                ('end_date', models.DateField()),
                ('total_days', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=6)),
                ('reason', models.TextField(blank=True, null=True)),
                ('attachment', models.FileField(blank=True, null=True, upload_to='hrms/leave_attachments/%Y/%m/')),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected'), ('cancelled', 'Cancelled')], default='pending', max_length=10)),
                ('approved_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('approved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='hrms_approved_leave_requests', to=settings.AUTH_USER_MODEL)),
                ('employee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='leave_requests', to='hrms.employee')),
                ('leave_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='leave_requests', to='hrms.leavetype')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='leave_requests', to='hrms.company')),
            ],
        ),
        migrations.CreateModel(
            name='PayrollResult',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('basic_salary', models.DecimalField(decimal_places=3, default=Decimal('0.000'), max_digits=14)),
                ('total_allowances', models.DecimalField(decimal_places=3, default=Decimal('0.000'), max_digits=14)),
                ('overtime_pay', models.DecimalField(decimal_places=3, default=Decimal('0.000'), max_digits=14)),
                ('leave_deduction', models.DecimalField(decimal_places=3, default=Decimal('0.000'), max_digits=14)),
                ('other_deductions', models.DecimalField(decimal_places=3, default=Decimal('0.000'), max_digits=14)),
                ('gross_salary', models.DecimalField(decimal_places=3, default=Decimal('0.000'), max_digits=14)),
                ('net_salary', models.DecimalField(decimal_places=3, default=Decimal('0.000'), max_digits=14)),
                ('currency', models.CharField(default='OMR', max_length=8)),
                ('wps_ready', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('employee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payroll_results', to='hrms.employee')),
                ('period', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='results', to='hrms.payrollperiod')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payroll_results', to='hrms.company')),
            ],
        ),
        migrations.AddField(
            model_name='overtimeprediction',
            name='model_version',
            field=models.CharField(default='v1', max_length=64),
        ),
        migrations.AddField(
            model_name='overtimeprediction',
            name='predicted_overtime_minutes',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='overtimeprediction',
            name='prediction_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddIndex(
            model_name='leavetype',
            index=models.Index(fields=['tenant', 'is_active'], name='hrms_leavet_tenant__a1f3d6_idx'),
        ),
        migrations.AddIndex(
            model_name='leavetype',
            index=models.Index(fields=['tenant', 'leave_category'], name='hrms_leavet_tenant__2480d8_idx'),
        ),
        migrations.AddConstraint(
            model_name='leavetype',
            constraint=models.UniqueConstraint(fields=('tenant', 'code'), name='uq_hrms_leavetype_tenant_code'),
        ),
        migrations.AddIndex(
            model_name='payrollperiod',
            index=models.Index(fields=['tenant', 'status'], name='hrms_payrol_tenant__5fb8dc_idx'),
        ),
        migrations.AddIndex(
            model_name='payrollperiod',
            index=models.Index(fields=['tenant', 'start_date', 'end_date'], name='hrms_payrol_tenant__ef0382_idx'),
        ),
        migrations.AddConstraint(
            model_name='payrollperiod',
            constraint=models.CheckConstraint(condition=models.Q(end_date__gte=models.F('start_date')), name='ck_hrms_payroll_period_date_range'),
        ),
        migrations.AddConstraint(
            model_name='payrollperiod',
            constraint=models.UniqueConstraint(fields=('tenant', 'name'), name='uq_hrms_payroll_period_tenant_name'),
        ),
        migrations.AddIndex(
            model_name='salarystructure',
            index=models.Index(fields=['tenant', 'employee', 'effective_from'], name='hrms_salary_tenant__817ca4_idx'),
        ),
        migrations.AddConstraint(
            model_name='salarystructure',
            constraint=models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True) | models.Q(effective_to__gte=models.F('effective_from')),
                name='ck_hrms_salary_structure_effective_range',
            ),
        ),
        migrations.AddIndex(
            model_name='leavebalance',
            index=models.Index(fields=['tenant', 'employee'], name='hrms_leaveb_tenant__13aa0c_idx'),
        ),
        migrations.AddConstraint(
            model_name='leavebalance',
            constraint=models.UniqueConstraint(fields=('tenant', 'employee', 'leave_type'), name='uq_hrms_leavebalance_tenant_employee_type'),
        ),
        migrations.AddIndex(
            model_name='leaverequest',
            index=models.Index(fields=['tenant', 'employee', 'status'], name='hrms_leaver_tenant__14100a_idx'),
        ),
        migrations.AddIndex(
            model_name='leaverequest',
            index=models.Index(fields=['tenant', 'start_date', 'end_date'], name='hrms_leaver_tenant__f22793_idx'),
        ),
        migrations.AddIndex(
            model_name='payrollresult',
            index=models.Index(fields=['tenant', 'period'], name='hrms_payrol_tenant__5fbc8d_idx'),
        ),
        migrations.AddConstraint(
            model_name='payrollresult',
            constraint=models.UniqueConstraint(fields=('tenant', 'employee', 'period'), name='uq_hrms_payroll_result_tenant_employee_period'),
        ),
        migrations.AddIndex(
            model_name='overtimeprediction',
            index=models.Index(fields=['tenant', 'prediction_date'], name='hrms_overti_tenant__4b0fb5_idx'),
        ),
    ]
