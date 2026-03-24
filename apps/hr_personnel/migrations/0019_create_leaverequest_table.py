from django.db import migrations, models
import django.db.models.deletion
import uuid


def create_leaverequest_table(apps, schema_editor):
    """
    Create the hr_personnel_leaverequest table if it doesn't exist
    """
    with schema_editor.connection.cursor() as cursor:
        # Check if table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='hr_personnel_leaverequest'
        """)
        if cursor.fetchone():
            return  # Table already exists
        
        # Create the table
        cursor.execute("""
            CREATE TABLE hr_personnel_leaverequest (
                id CHAR(32) PRIMARY KEY,
                employee_id CHAR(32) NOT NULL REFERENCES hr_personnel_employee(id),
                leave_type VARCHAR(50) NOT NULL,
                start_date DATE NOT NULL,
                end_date DATE NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                reason TEXT NULL,
                approved_by_id CHAR(32) NULL REFERENCES hr_personnel_employee(id),
                approved_at DATETIME NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
        """)
        
        # Create indexes
        cursor.execute("""
            CREATE INDEX hr_personnel_leaverequest_employee_id 
            ON hr_personnel_leaverequest(employee_id)
        """)
        cursor.execute("""
            CREATE INDEX hr_personnel_leaverequest_status 
            ON hr_personnel_leaverequest(status)
        """)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('hr_personnel', '0018_rename_hr_personne_salary__8de176_idx_hr_personne_salary__0d794b_idx_and_more'),
    ]

    operations = [
        migrations.RunPython(create_leaverequest_table, noop_reverse),
    ]
