from django.db import migrations, models
import uuid


def create_leaveaiinsight_table(apps, schema_editor):
    """
    Create the hr_personnel_leaveaiinsight table if it doesn't exist
    """
    with schema_editor.connection.cursor() as cursor:
        # Check if table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='hr_personnel_leaveaiinsight'
        """)
        if cursor.fetchone():
            return  # Table already exists
        
        # Create the table
        cursor.execute("""
            CREATE TABLE hr_personnel_leaveaiinsight (
                id CHAR(32) PRIMARY KEY,
                employee_id CHAR(32) NOT NULL REFERENCES hr_personnel_employee(id),
                leave_request_id CHAR(32) NULL REFERENCES hr_personnel_leaverequest(id),
                insight_type VARCHAR(50) NOT NULL,
                confidence_score REAL NULL,
                ai_summary TEXT NULL,
                raw_data TEXT NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
        """)
        
        # Create indexes
        cursor.execute("""
            CREATE INDEX hr_personnel_leaveaiinsight_employee_id 
            ON hr_personnel_leaveaiinsight(employee_id)
        """)
        cursor.execute("""
            CREATE INDEX hr_personnel_leaveaiinsight_leave_request_id 
            ON hr_personnel_leaveaiinsight(leave_request_id)
        """)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('hr_personnel', '0019_create_leaverequest_table'),
    ]

    operations = [
        migrations.RunPython(create_leaveaiinsight_table, noop_reverse),
    ]
