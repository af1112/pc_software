from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('hr_attendance', '0004_attendance_clock_by'),
    ]

    operations = [
        migrations.AddField(
            model_name='attendance',
            name='clock_in_latitude',
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True, verbose_name='Clock-in Latitude'),
        ),
        migrations.AddField(
            model_name='attendance',
            name='clock_in_longitude',
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True, verbose_name='Clock-in Longitude'),
        ),
        migrations.AddField(
            model_name='attendance',
            name='clock_out_latitude',
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True, verbose_name='Clock-out Latitude'),
        ),
        migrations.AddField(
            model_name='attendance',
            name='clock_out_longitude',
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True, verbose_name='Clock-out Longitude'),
        ),
    ]
