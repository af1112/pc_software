import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.utils import OperationalError


class AddFieldIfNotExists(migrations.AddField):
    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        try:
            super().database_forwards(app_label, schema_editor, from_state, to_state)
        except OperationalError as exc:
            message = str(exc).lower()
            if 'duplicate column name' in message or ('column' in message and 'exists' in message):
                return
            raise


def backfill_attendance_employee(apps, schema_editor):
    Attendance = apps.get_model('hr_attendance', 'Attendance')

    rows = Attendance.objects.filter(employee__isnull=True, user__isnull=False).select_related('user')
    for row in rows.iterator():
        user = getattr(row, 'user', None)
        employee = getattr(user, 'employee', None) if user is not None else None
        if employee is None:
            continue
        row.employee_id = employee.id
        row.save(update_fields=['employee'])


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ('hr_attendance', '0009_attendance_lunch_flow'),
        ('hr_personnel', '0007_work_units_and_supply_company'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        AddFieldIfNotExists(
            model_name='attendance',
            name='employee',
            field=models.ForeignKey(
                blank=True,
                db_constraint=False,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='attendances',
                to='hr_personnel.employee',
                verbose_name='Employee',
            ),
        ),
        migrations.AlterField(
            model_name='attendance',
            name='user',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='attendances',
                to=settings.AUTH_USER_MODEL,
                verbose_name='User',
            ),
        ),
        migrations.RunPython(backfill_attendance_employee, migrations.RunPython.noop),
        migrations.AlterUniqueTogether(
            name='attendance',
            unique_together={('user', 'date'), ('employee', 'date')},
        ),
    ]
