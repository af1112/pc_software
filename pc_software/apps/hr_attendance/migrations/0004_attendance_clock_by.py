from django.db import migrations, models
from django.conf import settings
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('hr_attendance', '0003_alter_attendance_photo_in_alter_attendance_photo_out'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='attendance',
            name='clock_in_by',
            field=models.ForeignKey(null=True, blank=True, on_delete=django.db.models.deletion.SET_NULL, related_name='attendance_clockins_recorded', to=settings.AUTH_USER_MODEL, verbose_name='Clock-in By', db_constraint=False),
        ),
        migrations.AddField(
            model_name='attendance',
            name='clock_out_by',
            field=models.ForeignKey(null=True, blank=True, on_delete=django.db.models.deletion.SET_NULL, related_name='attendance_clockouts_recorded', to=settings.AUTH_USER_MODEL, verbose_name='Clock-out By', db_constraint=False),
        ),
    ]
