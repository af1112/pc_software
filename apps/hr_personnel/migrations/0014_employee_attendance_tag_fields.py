from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('hr_personnel', '0013_salary_schema_columns_repair'),
    ]

    operations = [
        migrations.AddField(
            model_name='employee',
            name='attendance_card_number',
            field=models.CharField(blank=True, max_length=64, null=True, verbose_name='Attendance Card Number'),
        ),
        migrations.AddField(
            model_name='employee',
            name='attendance_tag_uid',
            field=models.CharField(blank=True, max_length=128, null=True, verbose_name='Attendance Tag UID (RFID/NFC)'),
        ),
    ]
