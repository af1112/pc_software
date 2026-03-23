from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hr_attendance', '0006_shift_attendance_capture_mode_attendance_device_id_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='attendance',
            name='supervisor_clock_in',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Supervisor Clock In'),
        ),
        migrations.AddField(
            model_name='attendance',
            name='supervisor_clock_out',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Supervisor Clock Out'),
        ),
        migrations.AddField(
            model_name='attendance',
            name='user_clock_in',
            field=models.DateTimeField(blank=True, null=True, verbose_name='User Clock In'),
        ),
        migrations.AddField(
            model_name='attendance',
            name='user_clock_out',
            field=models.DateTimeField(blank=True, null=True, verbose_name='User Clock Out'),
        ),
    ]
