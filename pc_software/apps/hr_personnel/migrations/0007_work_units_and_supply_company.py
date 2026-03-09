import django.db.models.deletion
from django.db import migrations, models
from django.db.utils import OperationalError


class AddFieldIfNotExists(migrations.AddField):
    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        try:
            super().database_forwards(app_label, schema_editor, from_state, to_state)
        except OperationalError as exc:
            message = str(exc).lower()
            if (
                'duplicate column name' in message
                or ('column' in message and 'exists' in message)
                or ('key column' in message and 'doesn\'t exist in table' in message)
            ):
                return
            raise


class CreateModelIfNotExists(migrations.CreateModel):
    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        try:
            super().database_forwards(app_label, schema_editor, from_state, to_state)
        except OperationalError as exc:
            message = str(exc).lower()
            if 'already exists' in message or ('table' in message and 'exists' in message):
                return
            raise


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ('hr_personnel', '0006_salary_structure_backfill'),
    ]

    operations = [
        CreateModelIfNotExists(
            name='LaborSupplyCompany',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=150, verbose_name='Company Name')),
                ('code', models.CharField(blank=True, max_length=50, null=True, verbose_name='Company Code')),
                ('is_active', models.BooleanField(default=True, verbose_name='Is Active')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='labor_supply_companies', to='organizations.organization', verbose_name='Organization')),
            ],
            options={
                'verbose_name': 'Labor Supply Company',
                'verbose_name_plural': 'Labor Supply Companies',
                'ordering': ['name'],
                'unique_together': {('organization', 'name')},
            },
        ),
        CreateModelIfNotExists(
            name='WorkUnit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=150, verbose_name='Unit Name')),
                ('code', models.CharField(blank=True, max_length=50, null=True, verbose_name='Unit Code')),
                ('unit_type', models.CharField(choices=[('project', 'Project'), ('office', 'Office'), ('site', 'Site'), ('department', 'Department')], default='project', max_length=20, verbose_name='Unit Type')),
                ('is_active', models.BooleanField(default=True, verbose_name='Is Active')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='work_units', to='organizations.organization', verbose_name='Organization')),
                ('parent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='children', to='hr_personnel.workunit')),
                ('supervisor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='supervised_work_units', to='hr_personnel.employee', verbose_name='Unit Supervisor')),
            ],
            options={
                'verbose_name': 'Work Unit',
                'verbose_name_plural': 'Work Units',
                'ordering': ['name'],
                'unique_together': {('organization', 'name')},
            },
        ),
        AddFieldIfNotExists(
            model_name='employee',
            name='supply_company',
            field=models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='employees', to='hr_personnel.laborsupplycompany', verbose_name='Labor Supply Company'),
        ),
        AddFieldIfNotExists(
            model_name='employee',
            name='work_unit',
            field=models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='employees', to='hr_personnel.workunit', verbose_name='Work Unit'),
        ),
    ]
