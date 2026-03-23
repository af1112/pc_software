from __future__ import annotations

import datetime

try:
    from celery import shared_task
except Exception:  # pragma: no cover
    def shared_task(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

from apps.hrms.models import Employee
from apps.hrms.services import OvertimePayService, TimesheetEngine


@shared_task(name='hrms.rebuild_timesheet')
def rebuild_timesheet_task(tenant_id: str, employee_id: str, work_date_iso: str) -> dict:
    from apps.hrms.models import Company

    tenant = Company.objects.get(id=tenant_id)
    employee = Employee.objects.get(id=employee_id, tenant=tenant)
    work_date = datetime.date.fromisoformat(work_date_iso)

    result = TimesheetEngine.build_for_date(tenant=tenant, employee=employee, work_date=work_date)
    return {
        'timesheet_id': str(result.timesheet.id),
        'created': result.created,
    }


@shared_task(name='hrms.generate_monthly_overtime')
def generate_monthly_overtime_task(tenant_id: str, employee_id: str, year: int, month: int) -> dict:
    from apps.hrms.models import Company

    tenant = Company.objects.get(id=tenant_id)
    employee = Employee.objects.get(id=employee_id, tenant=tenant)

    entry = OvertimePayService.generate_monthly_entry(tenant, employee, int(year), int(month))
    return {
        'entry_id': str(entry.id),
        'total_minutes': entry.total_overtime_minutes,
        'total_pay': str(entry.total_overtime_pay),
    }
