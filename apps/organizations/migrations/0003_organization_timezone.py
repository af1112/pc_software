from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('organizations', '0002_organization_contact_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='organization',
            name='timezone',
            field=models.CharField(default='UTC', help_text='e.g., Asia/Tehran, Europe/London', max_length=64, verbose_name='Time Zone'),
        ),
    ]

