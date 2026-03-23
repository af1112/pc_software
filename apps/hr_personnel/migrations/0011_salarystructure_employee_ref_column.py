import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hr_personnel', '0010_payroll_schema_repair'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name='salarystructure',
                    name='employee',
                    field=models.ForeignKey(
                        db_column='employee_ref_id',
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='salary_structures',
                        to='hr_personnel.employee',
                    ),
                ),
            ],
            database_operations=[],
        ),
    ]
