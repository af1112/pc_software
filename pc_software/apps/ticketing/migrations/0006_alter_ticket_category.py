from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ticketing', '0005_ticket_issuer_serial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ticket',
            name='category',
            field=models.CharField(
                choices=[
                    ('support_request', 'Request from Support Unit'),
                    ('problem_report', 'Problem Report'),
                    ('finance_unit', 'Finance Unit'),
                    ('management_contact', 'Contact Management'),
                    ('training_unit', 'Training Unit'),
                    ('feedback_suggestions', 'Criticism and Suggestions'),
                ],
                default='support_request',
                max_length=20,
                verbose_name='Category',
            ),
        ),
    ]
