from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0004_userprofile_organization'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='userprofile',
            options={
                'permissions': [
                    ('can_access_expenses', 'Can access Expense Manager'),
                    ('can_access_ticketing', 'Can access Ticketing System'),
                    ('can_access_attendance', 'Can access Presence & Attendance'),
                    ('can_access_personnel', 'Can access Personnel & Payroll'),
                    ('can_access_projects', 'Can access Project Control'),
                    ('can_access_dms', 'Can access Document DMS'),
                    ('can_access_ai', 'Can access AI Engine'),
                    ('can_access_menu', 'Can access Digital Menu'),
                    ('can_access_club', 'Can access Customer Club'),
                ]
            },
        ),
    ]
