from django.db import migrations, models
from django.db.utils import OperationalError, ProgrammingError


def _safe(exc):
    msg = str(exc).lower()
    return (
        'already exists' in msg
        or ('table' in msg and 'exists' in msg)
        or 'duplicate column name' in msg
        or ('column' in msg and 'exists' in msg)
    )


def _table_exists(schema_editor, table_name):
    with schema_editor.connection.cursor() as cursor:
        tables = schema_editor.connection.introspection.table_names(cursor)
        return table_name in tables


def _table_columns(schema_editor, table_name):
    with schema_editor.connection.cursor() as cursor:
        description = schema_editor.connection.introspection.get_table_description(cursor, table_name)
    return {col.name for col in description}


def _add_column_if_missing(schema_editor, table_name, column_name, column_sql):
    if not _table_exists(schema_editor, table_name):
        return
    columns = _table_columns(schema_editor, table_name)
    if column_name in columns:
        return
    try:
        schema_editor.execute(column_sql)
    except (OperationalError, ProgrammingError) as exc:
        if not _safe(exc):
            raise


def repair_employee_supply_company(apps, schema_editor):
    """
    Ensure supply_company_id and work_unit_id columns exist in employee table
    and that the related tables exist.
    """
    
    # 1. Ensure related tables exist
    if not _table_exists(schema_editor, 'hr_personnel_laborsupplycompany'):
        schema_editor.execute("""
            CREATE TABLE hr_personnel_laborsupplycompany (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(150) NOT NULL,
                code VARCHAR(50) NULL,
                is_active BOOL NOT NULL DEFAULT 1,
                created_at DATETIME NOT NULL,
                organization_id INTEGER NOT NULL REFERENCES organizations_organization(id)
            )
        """)

    if not _table_exists(schema_editor, 'hr_personnel_workunit'):
        schema_editor.execute("""
            CREATE TABLE hr_personnel_workunit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(150) NOT NULL,
                code VARCHAR(50) NULL,
                unit_type VARCHAR(20) NOT NULL DEFAULT 'project',
                is_active BOOL NOT NULL DEFAULT 1,
                created_at DATETIME NOT NULL,
                organization_id INTEGER NOT NULL REFERENCES organizations_organization(id),
                parent_id INTEGER NULL REFERENCES hr_personnel_workunit(id),
                supervisor_id INTEGER NULL REFERENCES hr_personnel_employee(id)
            )
        """)

    # 2. Ensure employee table has the foreign key columns
    employee_table = 'hr_personnel_employee'
    
    # Add supply_company_id column
    _add_column_if_missing(
        schema_editor, 
        employee_table, 
        'supply_company_id',
        """
        ALTER TABLE hr_personnel_employee 
        ADD COLUMN supply_company_id INTEGER NULL 
        REFERENCES hr_personnel_laborsupplycompany(id)
        """
    )
    
    # Add work_unit_id column
    _add_column_if_missing(
        schema_editor, 
        employee_table, 
        'work_unit_id',
        """
        ALTER TABLE hr_personnel_employee 
        ADD COLUMN work_unit_id INTEGER NULL 
        REFERENCES hr_personnel_workunit(id)
        """
    )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('hr_personnel', '0016_hr_personnel_structure_repair'),
    ]

    operations = [
        migrations.RunPython(repair_employee_supply_company, noop_reverse),
    ]
