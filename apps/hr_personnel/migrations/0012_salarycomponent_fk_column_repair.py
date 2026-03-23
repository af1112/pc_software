import django.db.models.deletion
from django.db import migrations, models
from django.db.utils import OperationalError, ProgrammingError


def _table_exists(schema_editor, table_name):
    with schema_editor.connection.cursor() as cursor:
        return table_name in schema_editor.connection.introspection.table_names(cursor)


def _table_columns(schema_editor, table_name):
    with schema_editor.connection.cursor() as cursor:
        description = schema_editor.connection.introspection.get_table_description(cursor, table_name)
    return {col.name for col in description}


def repair_salary_component_fk_column(apps, schema_editor):
    SalaryComponent = apps.get_model('hr_personnel', 'SalaryComponent')
    table_name = SalaryComponent._meta.db_table
    if not _table_exists(schema_editor, table_name):
        return

    columns = _table_columns(schema_editor, table_name)
    new_col = 'salary_structure_id'
    old_col = 'salary_profile_id'

    if new_col not in columns:
        if old_col not in columns:
            return

        relation_field = SalaryComponent._meta.get_field('salary_structure')
        target_pk = relation_field.target_field
        db_type = target_pk.db_type(schema_editor.connection) or 'char(32)'

        quoted_table = schema_editor.quote_name(table_name)
        quoted_new_col = schema_editor.quote_name(new_col)
        schema_editor.execute(
            f"ALTER TABLE {quoted_table} ADD COLUMN {quoted_new_col} {db_type} NULL"
        )
        columns = _table_columns(schema_editor, table_name)

    if old_col in columns:
        quoted_table = schema_editor.quote_name(table_name)
        quoted_new_col = schema_editor.quote_name(new_col)
        quoted_old_col = schema_editor.quote_name(old_col)
        schema_editor.execute(
            f"UPDATE {quoted_table} SET {quoted_new_col} = {quoted_old_col} "
            f"WHERE {quoted_new_col} IS NULL AND {quoted_old_col} IS NOT NULL"
        )


def safe_repair_salary_component_fk_column(apps, schema_editor):
    try:
        repair_salary_component_fk_column(apps, schema_editor)
    except (OperationalError, ProgrammingError):
        # Keep migration idempotent across partial legacy schemas.
        return


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('hr_personnel', '0011_salarystructure_employee_ref_column'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name='salarycomponent',
                    name='salary_structure',
                    field=models.ForeignKey(
                        db_column='salary_structure_id',
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='components',
                        to='hr_personnel.salarystructure',
                    ),
                ),
            ],
            database_operations=[],
        ),
        migrations.RunPython(safe_repair_salary_component_fk_column, noop_reverse),
    ]
