from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def backfill_ticket_issuer_serial(apps, schema_editor):
    Ticket = apps.get_model('ticketing', 'Ticket')
    TicketIssuerSequence = apps.get_model('ticketing', 'TicketIssuerSequence')

    for row in TicketIssuerSequence.objects.all():
        row.last_serial = 0
        row.save(update_fields=['last_serial'])

    issuer_last = {}
    tickets = Ticket.objects.all().order_by('created_by_id', 'created_at', 'id')
    for ticket in tickets.iterator():
        key = ticket.created_by_id
        issuer_last[key] = issuer_last.get(key, 0) + 1
        ticket.issuer_serial = issuer_last[key]
        ticket.save(update_fields=['issuer_serial'])

    for user_id, last_serial in issuer_last.items():
        TicketIssuerSequence.objects.update_or_create(
            user_id=user_id,
            defaults={'last_serial': last_serial},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('ticketing', '0004_update_ticket_status_and_assignment'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='TicketIssuerSequence',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('last_serial', models.PositiveIntegerField(default=0)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='ticket_sequence', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Ticket Issuer Sequence',
                'verbose_name_plural': 'Ticket Issuer Sequences',
            },
        ),
        migrations.AddField(
            model_name='ticket',
            name='issuer_serial',
            field=models.PositiveIntegerField(blank=True, db_index=True, editable=False, null=True, verbose_name='Issuer Serial'),
        ),
        migrations.RunPython(backfill_ticket_issuer_serial, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='ticket',
            constraint=models.UniqueConstraint(fields=('created_by', 'issuer_serial'), name='uniq_ticket_serial_per_issuer'),
        ),
    ]
