from __future__ import annotations

from typing import Optional

from apps.hrms.models import Company


class TenantResolutionError(Exception):
    pass


def resolve_company_for_request(request) -> Optional[Company]:
    organization = getattr(request, 'organization', None)
    if organization is None:
        return None
    return Company.objects.filter(organization=organization).first()


def require_company_for_request(request) -> Company:
    company = resolve_company_for_request(request)
    if company is None:
        raise TenantResolutionError('No HRMS company is configured for this organization.')
    return company
