from django.db import migrations
from django.db.utils import OperationalError, ProgrammingError


def _safe_db_error(exc):
    message = str(exc).lower()
    return (
        'duplicate column name' in message
        or ('column' in message and 'exists' in message)
        or ('table' in message and 'exists' in message)
        or 'already exists' in message
    )


def _table_exists(schema_editor, table_name):
    with schema_editor.connection.cursor() as cursor:
        return table_name in schema_editor.connection.introspection.table_names(cursor)


def _table_columns(schema_editor, table_name):
    with schema_editor.connection.cursor() as cursor:
        description = schema_editor.connection.introspection.get_table_description(cursor, table_name)
    return {col.name for col in description}


def _ensure_model_table(schema_editor, model):
    table_name = model._meta.db_table
    if _table_exists(schema_editor, table_name):
        return
    try:
        schema_editor.create_model(model)
    except (OperationalError, ProgrammingError) as exc:
        if not _safe_db_error(exc):
            raise


def _ensure_column(schema_editor, model, field_name):
    table_name = model._meta.db_table
    if not _table_exists(schema_editor, table_name):
        return

    field = model._meta.get_field(field_name)
    columns = _table_columns(schema_editor, table_name)
    if field.column in columns:
        return

    try:
        schema_editor.add_field(model, field)
    except (OperationalError, ProgrammingError) as exc:
        if not _safe_db_error(exc):
            raise


def repair_payroll_schema(apps, schema_editor):
    PayrollPeriod = apps.get_model('hr_personnel', 'PayrollPeriod')
    PayrollRun = apps.get_model('hr_personnel', 'PayrollRun')
    PayrollSlip = apps.get_model('hr_personnel', 'PayrollSlip')
    PayrollItem = apps.get_model('hr_personnel', 'PayrollItem')

    # Ensure core payroll tables exist first.
    _ensure_model_table(schema_editor, PayrollPeriod)
    _ensure_model_table(schema_editor, PayrollRun)

    # Repair known missing columns in partially-applied databases.
    _ensure_column(schema_editor, PayrollSlip, 'period')
    _ensure_column(schema_editor, PayrollSlip, 'generated_at')
    _ensure_column(schema_editor, PayrollSlip, 'gross_salary')
    _ensure_column(schema_editor, PayrollSlip, 'net_salary')
    _ensure_column(schema_editor, PayrollSlip, 'overtime_amount')

    _ensure_column(schema_editor, PayrollItem, 'component_name')
    _ensure_column(schema_editor, PayrollItem, 'component_type')

    _ensure_column(schema_editor, PayrollRun, 'period')
    _ensure_column(schema_editor, PayrollRun, 'created_by')
    _ensure_column(schema_editor, PayrollRun, 'execution_ms')


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('hr_personnel', '0009_alter_salarystructure_options_and_more'),
    ]

    operations = [
        migrations.RunPython(repair_payroll_schema, noop_reverse),
    ]
