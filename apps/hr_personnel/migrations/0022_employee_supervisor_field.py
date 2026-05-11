from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('hr_personnel', '0021_fix_leaveaiinsight_columns'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='employee',
            name='supervisor',
            field=models.ForeignKey(
                blank=True,
                db_constraint=False,
                help_text='Used for personnel without their own user account, to assign a supervising user.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='supervised_employees',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Supervisor',
            ),
        ),
    ]
