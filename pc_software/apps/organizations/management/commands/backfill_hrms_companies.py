from django.core.management.base import BaseCommand

from apps.hrms.models import Company
from apps.organizations.models import Organization


class Command(BaseCommand):
    help = 'Create missing HRMS Company records for existing organizations.'

    def handle(self, *args, **options):
        created_count = 0
        for org in Organization.objects.all().order_by('id'):
            tz = (org.timezone or '').lower()
            country = Company.Country.IRAN if ('tehran' in tz or tz.endswith('/iran')) else Company.Country.OMAN
            _, created = Company.objects.get_or_create(
                organization=org,
                defaults={
                    'name': org.name,
                    'country': country,
                    'timezone': org.timezone or 'UTC',
                    'default_currency': 'IRR' if country == Company.Country.IRAN else 'OMR',
                    'wps_enabled': country == Company.Country.OMAN,
                },
            )
            if created:
                created_count += 1

        self.stdout.write(self.style.SUCCESS(f'HRMS backfill completed. Created {created_count} company records.'))
