import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hr_attendance', '0007_attendance_manual_time_sources'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AttendanceChangeLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('field_name', models.CharField(choices=[('clock_in', 'Clock In'), ('clock_out', 'Clock Out')], max_length=20, verbose_name='Field')),
                ('action_type', models.CharField(choices=[('set', 'Set'), ('edit', 'Edit'), ('delete', 'Delete')], max_length=20, verbose_name='Action')),
                ('old_value', models.DateTimeField(blank=True, null=True, verbose_name='Old Value')),
                ('new_value', models.DateTimeField(blank=True, null=True, verbose_name='New Value')),
                ('note', models.CharField(blank=True, max_length=255, verbose_name='Note')),
                ('performed_at', models.DateTimeField(auto_now_add=True, verbose_name='Performed At')),
                ('attendance', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='change_logs', to='hr_attendance.attendance', verbose_name='Attendance')),
                ('performed_by', models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='attendance_change_logs', to=settings.AUTH_USER_MODEL, verbose_name='Performed By')),
            ],
            options={
                'verbose_name': 'Attendance Change Log',
                'verbose_name_plural': 'Attendance Change Logs',
                'ordering': ['-performed_at'],
            },
        ),
    ]
