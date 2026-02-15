from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('organizations', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='organization',
            name='representative_name',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='Representative Name'),
        ),
        migrations.AddField(
            model_name='organization',
            name='representative_phone',
            field=models.CharField(blank=True, max_length=50, null=True, verbose_name='Representative Phone'),
        ),
        migrations.AddField(
            model_name='organization',
            name='company_email',
            field=models.EmailField(blank=True, max_length=254, null=True, verbose_name='Company Email'),
        ),
    ]

