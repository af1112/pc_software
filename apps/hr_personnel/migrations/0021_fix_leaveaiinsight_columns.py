from django.db import migrations, models
import uuid


def fix_leaveaiinsight_table(apps, schema_editor):
    """
    Fix the hr_personnel_leaveaiinsight table structure to match the model
    """
    with schema_editor.connection.cursor() as cursor:
        # Check if table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='hr_personnel_leaveaiinsight'
        """)
        if not cursor.fetchone():
            return  # Table doesn't exist
        
        # Get current columns
        cursor.execute("PRAGMA table_info(hr_personnel_leaveaiinsight)")
        columns = {row[1] for row in cursor.fetchall()}
        
        # Add missing columns
        if 'score' not in columns:
            cursor.execute("""
                ALTER TABLE hr_personnel_leaveaiinsight 
                ADD COLUMN score DECIMAL(5,2) DEFAULT 0
            """)
        
        if 'recommendation' not in columns:
            cursor.execute("""
                ALTER TABLE hr_personnel_leaveaiinsight 
                ADD COLUMN recommendation VARCHAR(255)
            """)
        
        if 'rationale' not in columns:
            cursor.execute("""
                ALTER TABLE hr_personnel_leaveaiinsight 
                ADD COLUMN rationale TEXT NULL
            """)
        
        if 'generated_at' not in columns:
            cursor.execute("""
                ALTER TABLE hr_personnel_leaveaiinsight 
                ADD COLUMN generated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            """)
        
        # Drop wrong columns if they exist
        if 'confidence_score' in columns:
            cursor.execute("""
                ALTER TABLE hr_personnel_leaveaiinsight 
                DROP COLUMN confidence_score
            """)
        
        if 'ai_summary' in columns:
            cursor.execute("""
                ALTER TABLE hr_personnel_leaveaiinsight 
                DROP COLUMN ai_summary
            """)
        
        if 'raw_data' in columns:
            cursor.execute("""
                ALTER TABLE hr_personnel_leaveaiinsight 
                DROP COLUMN raw_data
            """)
        
        if 'updated_at' in columns:
            cursor.execute("""
                ALTER TABLE hr_personnel_leaveaiinsight 
                DROP COLUMN updated_at
            """)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('hr_personnel', '0020_create_leaveaiinsight_table'),
    ]

    operations = [
        migrations.RunPython(fix_leaveaiinsight_table, noop_reverse),
    ]
