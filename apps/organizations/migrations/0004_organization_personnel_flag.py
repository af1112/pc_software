from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('organizations', '0003_organization_timezone'),
    ]

    operations = [
        migrations.AddField(
            model_name='organization',
            name='can_use_personnel',
            field=models.BooleanField(default=False, verbose_name='Enable Personnel & Payroll'),
        ),
    ]
