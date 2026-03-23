from django.db import migrations
from django.db.utils import OperationalError, ProgrammingError


def _safe_db_error(exc):
    message = str(exc).lower()
    return (
        'duplicate column name' in message
        or ('column' in message and 'exists' in message)
        or ('table' in message and 'exists' in message)
        or 'already exists' in message
        or ('duplicate key name' in message)
    )


def _table_exists(schema_editor, table_name):
    with schema_editor.connection.cursor() as cursor:
        return table_name in schema_editor.connection.introspection.table_names(cursor)


def _table_columns(schema_editor, table_name):
    with schema_editor.connection.cursor() as cursor:
        description = schema_editor.connection.introspection.get_table_description(cursor, table_name)
    return {col.name for col in description}


def _ensure_uuid_fk_column(schema_editor, table_name, column_name):
    if not _table_exists(schema_editor, table_name):
        return
    columns = _table_columns(schema_editor, table_name)
    if column_name in columns:
        return

    quoted_table = schema_editor.quote_name(table_name)
    quoted_column = schema_editor.quote_name(column_name)
    # UUIDField is stored as CHAR(32) in this project.
    sql = f"ALTER TABLE {quoted_table} ADD COLUMN {quoted_column} char(32) NULL"
    try:
        schema_editor.execute(sql)
    except (OperationalError, ProgrammingError) as exc:
        if not _safe_db_error(exc):
            raise


def _copy_if_columns_exist(schema_editor, table_name, from_column, to_column):
    if not _table_exists(schema_editor, table_name):
        return

    columns = _table_columns(schema_editor, table_name)
    if from_column not in columns or to_column not in columns:
        return

    quoted_table = schema_editor.quote_name(table_name)
    quoted_from = schema_editor.quote_name(from_column)
    quoted_to = schema_editor.quote_name(to_column)
    sql = (
        f"UPDATE {quoted_table} "
        f"SET {quoted_to} = {quoted_from} "
        f"WHERE {quoted_to} IS NULL AND {quoted_from} IS NOT NULL"
    )
    try:
        schema_editor.execute(sql)
    except (OperationalError, ProgrammingError) as exc:
        if not _safe_db_error(exc):
            raise


def repair_salary_schema_columns(apps, schema_editor):
    _ensure_uuid_fk_column(schema_editor, 'hr_personnel_salaryprofile', 'employee_ref_id')
    _ensure_uuid_fk_column(schema_editor, 'hr_personnel_salarycomponent', 'salary_structure_id')

    # Backfill from legacy columns when available.
    _copy_if_columns_exist(schema_editor, 'hr_personnel_salaryprofile', 'employee_id', 'employee_ref_id')
    _copy_if_columns_exist(schema_editor, 'hr_personnel_salarycomponent', 'salary_profile_id', 'salary_structure_id')


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('hr_personnel', '0012_salarycomponent_fk_column_repair'),
    ]

    operations = [
        migrations.RunPython(repair_salary_schema_columns, noop_reverse),
    ]
