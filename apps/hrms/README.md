# HRMS Module

This app provides:
- Multi-tenant HRMS domain models (company, employee, shifts, calendars, attendance logs, timesheets, overtime policies)
- Timesheet engine and overtime payroll services
- DRF API endpoints under `/api/hrms/` when `djangorestframework` is installed
- Celery tasks for asynchronous recalculation
- Seed command: `py manage.py seed_hrms --organization-slug <slug> [--country OM|IR] [--year YYYY]`

## Notes
- API URLs are conditionally loaded if DRF is installed.
- JWT auth is conditionally enabled if `rest_framework_simplejwt` is installed.
- Celery settings are declared in `core.settings` and Celery app in `core/celery.py`.
