from django.db import migrations
from django.db.utils import OperationalError, ProgrammingError


def _table_names(schema_editor):
    with schema_editor.connection.cursor() as cursor:
        return set(schema_editor.connection.introspection.table_names(cursor))


def _table_columns(schema_editor, table_name):
    with schema_editor.connection.cursor() as cursor:
        description = schema_editor.connection.introspection.get_table_description(cursor, table_name)
    return {col.name for col in description}


def _safe(exc):
    message = str(exc).lower()
    return (
        'already exists' in message
        or ('table' in message and 'exists' in message)
        or 'duplicate column name' in message
        or ('column' in message and 'exists' in message)
    )


def repair_hr_personnel_structure(apps, schema_editor):
    LaborSupplyCompany = apps.get_model('hr_personnel', 'LaborSupplyCompany')
    WorkUnit = apps.get_model('hr_personnel', 'WorkUnit')
    Employee = apps.get_model('hr_personnel', 'Employee')

    existing_tables = _table_names(schema_editor)

    if LaborSupplyCompany._meta.db_table not in existing_tables:
        try:
            schema_editor.create_model(LaborSupplyCompany)
        except (OperationalError, ProgrammingError) as exc:
            if not _safe(exc):
                raise
        existing_tables = _table_names(schema_editor)

    if WorkUnit._meta.db_table not in existing_tables:
        try:
            schema_editor.create_model(WorkUnit)
        except (OperationalError, ProgrammingError) as exc:
            if not _safe(exc):
                raise
        existing_tables = _table_names(schema_editor)

    employee_table = Employee._meta.db_table
    if employee_table not in existing_tables:
        return

    employee_columns = _table_columns(schema_editor, employee_table)

    for field_name in ['supply_company', 'work_unit', 'attendance_card_number', 'attendance_tag_uid']:
        field = Employee._meta.get_field(field_name)
        column_name = field.column
        if column_name in employee_columns:
            continue
        try:
            schema_editor.add_field(Employee, field)
        except (OperationalError, ProgrammingError) as exc:
            if not _safe(exc):
                raise
        employee_columns = _table_columns(schema_editor, employee_table)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('hr_personnel', '0015_rename_hr_personne_salary__8de176_idx_hr_personne_salary__0d794b_idx_and_more'),
    ]

    operations = [
        migrations.RunPython(repair_hr_personnel_structure, noop_reverse),
    ]
