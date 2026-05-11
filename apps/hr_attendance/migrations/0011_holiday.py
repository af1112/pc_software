from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hr_attendance', '0010_attendance_employee_target'),
        ('organizations', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Holiday',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, verbose_name='Name')),
                ('date', models.DateField(verbose_name='Date')),
                ('holiday_type', models.CharField(choices=[('weekend', 'Weekend'), ('public_holiday', 'Public Holiday'), ('company_holiday', 'Company Holiday')], default='public_holiday', max_length=20, verbose_name='Holiday Type')),
                ('is_recurring', models.BooleanField(default=False, verbose_name='Recurring Yearly')),
                ('notes', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('organization', models.ForeignKey(blank=True, null=True, on_delete=models.CASCADE, related_name='holidays', to='organizations.organization', verbose_name='Organization', db_constraint=False)),
            ],
            options={
                'verbose_name': 'Holiday',
                'verbose_name_plural': 'Holidays',
                'ordering': ['-date'],
            },
        ),
    ]
