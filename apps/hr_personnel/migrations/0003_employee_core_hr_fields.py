from django.db import migrations, models
import django.db.models.deletion
from django.db.utils import OperationalError


class AddFieldIfNotExists(migrations.AddField):
    """
    Handles drifted databases where some columns were added manually or by a
    previously interrupted migration run.
    """

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        try:
            super().database_forwards(app_label, schema_editor, from_state, to_state)
        except OperationalError as exc:
            if 'Duplicate column name' in str(exc):
                return
            raise


def add_employee_id_unique_index(apps, schema_editor):
    employee_model = apps.get_model('hr_personnel', 'Employee')
    table_name = schema_editor.quote_name(employee_model._meta.db_table)
    index_name = schema_editor.quote_name('hr_personnel_employee_employee_id_uniq')
    column_name = schema_editor.quote_name('employee_id')
    try:
        schema_editor.execute(
            f"ALTER TABLE {table_name} ADD UNIQUE INDEX {index_name} ({column_name})"
        )
    except OperationalError as exc:
        message = str(exc).lower()
        if (
            'duplicate key name' in message
            or 'already exists' in message
            or 'unsupported' in message
            or 'duplicate entry' in message
        ):
            return
        raise


def remove_employee_id_unique_index(apps, schema_editor):
    employee_model = apps.get_model('hr_personnel', 'Employee')
    table_name = schema_editor.quote_name(employee_model._meta.db_table)
    index_name = schema_editor.quote_name('hr_personnel_employee_employee_id_uniq')
    try:
        schema_editor.execute(
            f"ALTER TABLE {table_name} DROP INDEX {index_name}"
        )
    except OperationalError as exc:
        message = str(exc).lower()
        if 'check that column/key exists' in message or 'doesn\'t exist' in message:
            return
        raise


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ('hr_personnel', '0002_employee_user_link'),
    ]

    operations = [
        AddFieldIfNotExists(
            model_name='employee',
            name='basic_salary',
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=12, null=True, verbose_name='Basic Salary'),
        ),
        AddFieldIfNotExists(
            model_name='employee',
            name='bank_name',
            field=models.CharField(blank=True, max_length=120, null=True, verbose_name='Bank Name'),
        ),
        AddFieldIfNotExists(
            model_name='employee',
            name='branch_id',
            field=models.CharField(blank=True, max_length=50, null=True, verbose_name='Branch ID'),
        ),
        AddFieldIfNotExists(
            model_name='employee',
            name='company_id',
            field=models.CharField(blank=True, max_length=50, null=True, verbose_name='Company ID'),
        ),
        AddFieldIfNotExists(
            model_name='employee',
            name='contract_end',
            field=models.DateField(blank=True, null=True, verbose_name='Contract End Date'),
        ),
        AddFieldIfNotExists(
            model_name='employee',
            name='contract_start',
            field=models.DateField(blank=True, null=True, verbose_name='Contract Start Date'),
        ),
        AddFieldIfNotExists(
            model_name='employee',
            name='currency',
            field=models.CharField(blank=True, max_length=10, null=True, verbose_name='Currency'),
        ),
        AddFieldIfNotExists(
            model_name='employee',
            name='date_of_birth',
            field=models.DateField(blank=True, null=True, verbose_name='Date of Birth'),
        ),
        AddFieldIfNotExists(
            model_name='employee',
            name='department_id',
            field=models.CharField(blank=True, max_length=50, null=True, verbose_name='Department ID'),
        ),
        AddFieldIfNotExists(
            model_name='employee',
            name='employee_id',
            field=models.CharField(blank=True, max_length=50, null=True, verbose_name='Employee ID'),
        ),
        AddFieldIfNotExists(
            model_name='employee',
            name='employment_type',
            field=models.CharField(blank=True, choices=[('full_time', 'Full-time'), ('part_time', 'Part-time'), ('contract', 'Contract')], max_length=20, null=True, verbose_name='Employment Type'),
        ),
        AddFieldIfNotExists(
            model_name='employee',
            name='gender',
            field=models.CharField(blank=True, choices=[('male', 'Male'), ('female', 'Female'), ('other', 'Other')], max_length=20, null=True, verbose_name='Gender'),
        ),
        AddFieldIfNotExists(
            model_name='employee',
            name='iban',
            field=models.CharField(blank=True, max_length=64, null=True, verbose_name='IBAN'),
        ),
        AddFieldIfNotExists(
            model_name='employee',
            name='marital_status',
            field=models.CharField(blank=True, choices=[('single', 'Single'), ('married', 'Married'), ('divorced', 'Divorced'), ('widowed', 'Widowed')], max_length=20, null=True, verbose_name='Marital Status'),
        ),
        AddFieldIfNotExists(
            model_name='employee',
            name='nationality',
            field=models.CharField(blank=True, max_length=80, null=True, verbose_name='Nationality'),
        ),
        AddFieldIfNotExists(
            model_name='employee',
            name='omani_or_expat',
            field=models.CharField(blank=True, choices=[('omani', 'Omani'), ('expat', 'Expat')], max_length=10, null=True, verbose_name='Omani/Expat'),
        ),
        AddFieldIfNotExists(
            model_name='employee',
            name='pasi_registered',
            field=models.BooleanField(default=False, verbose_name='PASI Registered'),
        ),
        AddFieldIfNotExists(
            model_name='employee',
            name='passport_no',
            field=models.CharField(blank=True, max_length=50, null=True, verbose_name='Passport Number'),
        ),
        AddFieldIfNotExists(
            model_name='employee',
            name='payment_method',
            field=models.CharField(blank=True, choices=[('bank_transfer', 'Bank Transfer'), ('cash', 'Cash'), ('wps', 'WPS')], max_length=20, null=True, verbose_name='Payment Method'),
        ),
        AddFieldIfNotExists(
            model_name='employee',
            name='position_id',
            field=models.CharField(blank=True, max_length=50, null=True, verbose_name='Position ID'),
        ),
        AddFieldIfNotExists(
            model_name='employee',
            name='probation_end_date',
            field=models.DateField(blank=True, null=True, verbose_name='Probation End Date'),
        ),
        AddFieldIfNotExists(
            model_name='employee',
            name='reporting_manager',
            field=models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='direct_reports', to='hr_personnel.employee', verbose_name='Reporting Manager'),
        ),
        AddFieldIfNotExists(
            model_name='employee',
            name='wps_required',
            field=models.BooleanField(default=False, verbose_name='WPS Required'),
        ),
        migrations.RunPython(add_employee_id_unique_index, remove_employee_id_unique_index),
    ]
