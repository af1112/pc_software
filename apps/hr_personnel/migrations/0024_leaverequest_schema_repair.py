"""Defensive schema repair for hr_personnel_leaverequest.

Older production DBs created the table via migration 0019 with columns
`start_date` / `end_date` and without `total_days` / `attachment`.
The current model expects `from_date` / `to_date` / `total_days` / `attachment`.

This migration adds the missing columns (idempotent) and back-fills
`from_date`/`to_date` from any legacy `start_date`/`end_date` values.
It applies only to the database; Django state already has these fields
defined by earlier migrations / model.
"""
from decimal import Decimal
from django.db import migrations


TABLE = 'hr_personnel_leaverequest'


def _columns(cursor, table):
    cols = set()
    try:
        cursor.execute(f"PRAGMA table_info({table})")
        rows = cursor.fetchall()
        for row in rows:
            cols.add(row[1])
        if cols:
            return cols
    except Exception:
        pass
    try:
        cursor.execute(
            "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = %s",
            [table],
        )
        for row in cursor.fetchall():
            cols.add(row[0])
    except Exception:
        pass
    return cols


def repair(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cols = _columns(cursor, TABLE)
        if not cols:
            # Table not present (fresh DB) — nothing to repair; CreateModel/0019 handles it.
            return

        add_statements = []
        if 'from_date' not in cols:
            add_statements.append(("from_date", "ADD COLUMN from_date DATE NULL"))
        if 'to_date' not in cols:
            add_statements.append(("to_date", "ADD COLUMN to_date DATE NULL"))
        if 'total_days' not in cols:
            add_statements.append(("total_days", "ADD COLUMN total_days DECIMAL(6,2) NOT NULL DEFAULT 0.00"))
        if 'attachment' not in cols:
            add_statements.append(("attachment", "ADD COLUMN attachment VARCHAR(255) NULL"))
        # Safety: also re-check 0023 columns in case that migration was skipped
        if 'is_hourly' not in cols:
            add_statements.append(("is_hourly", "ADD COLUMN is_hourly BOOL NOT NULL DEFAULT 0"))
        if 'start_time' not in cols:
            add_statements.append(("start_time", "ADD COLUMN start_time TIME NULL"))
        if 'end_time' not in cols:
            add_statements.append(("end_time", "ADD COLUMN end_time TIME NULL"))
        if 'total_hours' not in cols:
            add_statements.append(("total_hours", "ADD COLUMN total_hours DECIMAL(6,2) NOT NULL DEFAULT 0.00"))
        if 'rejection_reason' not in cols:
            add_statements.append(("rejection_reason", "ADD COLUMN rejection_reason TEXT NULL"))

        for _col, ddl in add_statements:
            try:
                cursor.execute(f"ALTER TABLE {TABLE} {ddl}")
            except Exception:
                pass

        # Re-read columns and back-fill from legacy start_date/end_date if present
        cols = _columns(cursor, TABLE)
        if 'start_date' in cols and 'from_date' in cols:
            try:
                cursor.execute(
                    f"UPDATE {TABLE} SET from_date = start_date WHERE from_date IS NULL AND start_date IS NOT NULL"
                )
            except Exception:
                pass
        if 'end_date' in cols and 'to_date' in cols:
            try:
                cursor.execute(
                    f"UPDATE {TABLE} SET to_date = end_date WHERE to_date IS NULL AND end_date IS NOT NULL"
                )
            except Exception:
                pass


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('hr_personnel', '0023_leaverequest_hourly_fields'),
    ]

    operations = [
        migrations.RunPython(repair, noop_reverse),
    ]
