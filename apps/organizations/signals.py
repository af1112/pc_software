from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.hrms.models import Company
from apps.organizations.models import Organization


def _default_country_for_org(organization: Organization) -> str:
    tz = (organization.timezone or '').lower()
    if 'tehran' in tz or tz.endswith('/iran'):
        return Company.Country.IRAN
    return Company.Country.OMAN


@receiver(post_save, sender=Organization)
def ensure_hrms_company_for_organization(sender, instance: Organization, created: bool, **kwargs):
    if not created:
        return

    country = _default_country_for_org(instance)
    Company.objects.get_or_create(
        organization=instance,
        defaults={
            'name': instance.name,
            'country': country,
            'timezone': instance.timezone or 'UTC',
            'default_currency': 'IRR' if country == Company.Country.IRAN else 'OMR',
            'wps_enabled': country == Company.Country.OMAN,
        },
    )
