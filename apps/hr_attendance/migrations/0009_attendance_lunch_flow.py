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


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ('hr_attendance', '0008_attendancechangelog'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        AddFieldIfNotExists(
            model_name='attendance',
            name='lunch_in',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Lunch In'),
        ),
        AddFieldIfNotExists(
            model_name='attendance',
            name='lunch_in_by',
            field=models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='attendance_lunchins_recorded', to=settings.AUTH_USER_MODEL, verbose_name='Lunch-in By'),
        ),
        AddFieldIfNotExists(
            model_name='attendance',
            name='lunch_in_latitude',
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True, verbose_name='Lunch-in Latitude'),
        ),
        AddFieldIfNotExists(
            model_name='attendance',
            name='lunch_in_longitude',
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True, verbose_name='Lunch-in Longitude'),
        ),
        AddFieldIfNotExists(
            model_name='attendance',
            name='lunch_out',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Lunch Out'),
        ),
        AddFieldIfNotExists(
            model_name='attendance',
            name='lunch_out_by',
            field=models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='attendance_lunchouts_recorded', to=settings.AUTH_USER_MODEL, verbose_name='Lunch-out By'),
        ),
        AddFieldIfNotExists(
            model_name='attendance',
            name='lunch_out_latitude',
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True, verbose_name='Lunch-out Latitude'),
        ),
        AddFieldIfNotExists(
            model_name='attendance',
            name='lunch_out_longitude',
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True, verbose_name='Lunch-out Longitude'),
        ),
        AddFieldIfNotExists(
            model_name='attendance',
            name='supervisor_lunch_in',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Supervisor Lunch In'),
        ),
        AddFieldIfNotExists(
            model_name='attendance',
            name='supervisor_lunch_out',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Supervisor Lunch Out'),
        ),
        AddFieldIfNotExists(
            model_name='attendance',
            name='user_lunch_in',
            field=models.DateTimeField(blank=True, null=True, verbose_name='User Lunch In'),
        ),
        AddFieldIfNotExists(
            model_name='attendance',
            name='user_lunch_out',
            field=models.DateTimeField(blank=True, null=True, verbose_name='User Lunch Out'),
        ),
        migrations.AlterField(
            model_name='attendancechangelog',
            name='field_name',
            field=models.CharField(choices=[('clock_in', 'Clock In'), ('lunch_out', 'Lunch Out'), ('lunch_in', 'Lunch In'), ('clock_out', 'Clock Out')], max_length=20, verbose_name='Field'),
        ),
    ]
