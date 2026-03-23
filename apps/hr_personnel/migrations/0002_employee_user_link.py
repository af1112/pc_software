from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('hr_personnel', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                # TiDB/MySQL limitation: adding a UNIQUE constraint on ADD COLUMN can fail.
                # Add the column first WITHOUT unique, then add unique index separately.
                migrations.AddField(
                    model_name='employee',
                    name='user',
                    field=models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='+',
                        to=settings.AUTH_USER_MODEL,
                        db_constraint=False,
                    ),
                ),
                migrations.RunSQL(
                    sql='CREATE UNIQUE INDEX hr_personnel_employee_user_id_uniq ON hr_personnel_employee (user_id);',
                    reverse_sql='DROP INDEX hr_personnel_employee_user_id_uniq ON hr_personnel_employee;'
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='employee',
                    name='user',
                    field=models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='employee',
                        to=settings.AUTH_USER_MODEL,
                        verbose_name='User Account',
                        db_constraint=False,
                    ),
                ),
            ],
        )
    ]
