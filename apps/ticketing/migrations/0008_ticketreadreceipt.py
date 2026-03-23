from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ticketing', '0007_migrate_legacy_ticket_categories'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='TicketReadReceipt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('first_read_at', models.DateTimeField(auto_now_add=True)),
                ('last_read_at', models.DateTimeField(auto_now=True)),
                ('ticket', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='read_receipts', to='ticketing.ticket')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ticket_read_receipts', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Ticket Read Receipt',
                'verbose_name_plural': 'Ticket Read Receipts',
            },
        ),
        migrations.AddConstraint(
            model_name='ticketreadreceipt',
            constraint=models.UniqueConstraint(fields=('ticket', 'user'), name='uniq_ticket_read_receipt_per_user'),
        ),
    ]
