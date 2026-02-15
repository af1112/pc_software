from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0004_userprofile_organization'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='timezone',
            field=models.CharField(
                max_length=50,
                default='UTC',
                help_text='IANA timezone name (e.g. Asia/Tehran, Europe/London)',
            ),
        ),
    ]

