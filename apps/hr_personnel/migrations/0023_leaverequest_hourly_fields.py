from decimal import Decimal
from django.db import migrations, models


def _has_column(cursor, table_name, column_name):
    vendor = cursor.db.vendor if hasattr(cursor, 'db') else None
    # Fallback: detect via PRAGMA (sqlite) or information_schema (mysql/postgres)
    try:
        cursor.execute(f"PRAGMA table_info({table_name})")
        rows = cursor.fetchall()
        if rows:
            return any((row[1] == column_name) for row in rows)
    except Exception:
        pass
    try:
        cursor.execute(
            "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_NAME = %s AND COLUMN_NAME = %s",
            [table_name, column_name],
        )
        return cursor.fetchone() is not None
    except Exception:
        return False


def add_missing_columns(apps, schema_editor):
    """Defensive raw-SQL addition to cover DBs where the prior schema diverged from models."""
    table = 'hr_personnel_leaverequest'
    with schema_editor.connection.cursor() as cursor:
        adds = [
            ('is_hourly', "ADD COLUMN is_hourly BOOL NOT NULL DEFAULT 0"),
            ('start_time', "ADD COLUMN start_time TIME NULL"),
            ('end_time', "ADD COLUMN end_time TIME NULL"),
            ('total_hours', "ADD COLUMN total_hours DECIMAL(6,2) NOT NULL DEFAULT 0.00"),
            ('rejection_reason', "ADD COLUMN rejection_reason TEXT NULL"),
        ]
        for col, ddl in adds:
            if not _has_column(cursor, table, col):
                try:
                    cursor.execute(f"ALTER TABLE {table} {ddl}")
                except Exception:
                    # column may already exist or DB may not allow; ignore silently
                    pass


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('hr_personnel', '0022_employee_supervisor_field'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(add_missing_columns, noop_reverse),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='leaverequest',
                    name='is_hourly',
                    field=models.BooleanField(default=False, verbose_name='Hourly Leave'),
                ),
                migrations.AddField(
                    model_name='leaverequest',
                    name='start_time',
                    field=models.TimeField(blank=True, null=True, verbose_name='Start Time'),
                ),
                migrations.AddField(
                    model_name='leaverequest',
                    name='end_time',
                    field=models.TimeField(blank=True, null=True, verbose_name='End Time'),
                ),
                migrations.AddField(
                    model_name='leaverequest',
                    name='total_hours',
                    field=models.DecimalField(
                        decimal_places=2,
                        default=Decimal('0.00'),
                        max_digits=6,
                        verbose_name='Total Hours',
                    ),
                ),
                migrations.AddField(
                    model_name='leaverequest',
                    name='rejection_reason',
                    field=models.TextField(blank=True, null=True, verbose_name='Rejection Reason'),
                ),
            ],
        ),
    ]
