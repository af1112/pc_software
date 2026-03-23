from django.db import migrations


def migrate_legacy_ticket_categories(apps, schema_editor):
    Ticket = apps.get_model('ticketing', 'Ticket')

    mapping = {
        'support': 'support_request',
        'bug': 'problem_report',
        'feature': 'feedback_suggestions',
        'other': 'management_contact',
    }

    for old_value, new_value in mapping.items():
        Ticket.objects.filter(category=old_value).update(category=new_value)


def reverse_migrate_legacy_ticket_categories(apps, schema_editor):
    Ticket = apps.get_model('ticketing', 'Ticket')

    reverse_mapping = {
        'support_request': 'support',
        'problem_report': 'bug',
        'feedback_suggestions': 'feature',
        'management_contact': 'other',
    }

    for new_value, old_value in reverse_mapping.items():
        Ticket.objects.filter(category=new_value).update(category=old_value)


class Migration(migrations.Migration):

    dependencies = [
        ('ticketing', '0006_alter_ticket_category'),
    ]

    operations = [
        migrations.RunPython(
            migrate_legacy_ticket_categories,
            reverse_migrate_legacy_ticket_categories,
        ),
    ]
