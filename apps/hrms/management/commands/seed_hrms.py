import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.hrms.models import (
    AttendanceLog,
    Company,
    Employee,
    EmployeeShiftAssignment,
    OvertimePolicy,
    OvertimeRateRule,
    ShiftTemplate,
    ShiftVersion,
    WorkCalendar,
)
from apps.organizations.models import Organization


User = get_user_model()


class Command(BaseCommand):
    help = 'Seed minimal HRMS data for a target organization/company.'

    def add_arguments(self, parser):
        parser.add_argument('--organization-slug', type=str, required=True)
        parser.add_argument('--country', type=str, default='OM', choices=['OM', 'IR'])
        parser.add_argument('--year', type=int, default=timezone.now().year)

    def handle(self, *args, **options):
        org_slug = options['organization_slug']
        country = options['country']
        year = options['year']

        organization = Organization.objects.filter(slug=org_slug).first()
        if organization is None:
            raise CommandError(f'Organization with slug={org_slug!r} was not found.')

        company, _ = Company.objects.get_or_create(
            organization=organization,
            defaults={
                'name': organization.name,
                'country': country,
                'timezone': organization.timezone or 'UTC',
                'default_currency': 'OMR' if country == 'OM' else 'IRR',
                'wps_enabled': country == 'OM',
            },
        )

        user, _ = User.objects.get_or_create(
            username=f'hrms-demo-{organization.slug}',
            defaults={
                'first_name': 'HRMS',
                'last_name': 'Demo',
                'email': f'hrms-demo-{organization.slug}@example.com',
            },
        )

        employee, _ = Employee.objects.get_or_create(
            tenant=company,
            employee_code='E-0001',
            defaults={
                'user': user,
                'first_name': 'Ali',
                'last_name': 'Rahimi',
                'nationality': 'IR',
                'hire_date': datetime.date(year - 1, 1, 10),
                'employment_type': Employee.EmploymentType.FULL_TIME,
                'basic_salary': Decimal('450.000') if country == 'OM' else Decimal('120000000.000'),
            },
        )

        shift, _ = ShiftTemplate.objects.get_or_create(
            tenant=company,
            name='General Shift',
            defaults={'description': 'Default day shift for office staff.'},
        )

        ShiftVersion.objects.get_or_create(
            tenant=company,
            shift=shift,
            valid_from=datetime.date(year, 1, 1),
            valid_to=datetime.date(year, 12, 31),
            defaults={
                'start_time': datetime.time(8, 0),
                'end_time': datetime.time(17, 0),
                'break_minutes': 60,
                'required_work_minutes': 480,
                'grace_in_minutes': 10,
                'grace_out_minutes': 10,
                'overtime_after_minutes': 0,
            },
        )

        EmployeeShiftAssignment.objects.get_or_create(
            tenant=company,
            employee=employee,
            shift=shift,
            effective_from=datetime.date(year, 1, 1),
            defaults={'is_active': True},
        )

        OvertimePolicy.objects.get_or_create(
            tenant=company,
            name=f'{country} Standard Overtime Policy',
            country=country,
            effective_from=datetime.date(year, 1, 1),
            defaults={'is_active': True},
        )
        policy = OvertimePolicy.objects.filter(tenant=company, country=country, is_active=True).order_by('-effective_from').first()

        if policy is not None:
            OvertimeRateRule.objects.get_or_create(
                policy=policy,
                day_type=OvertimeRateRule.DayType.WORKING_DAY,
                overtime_type=OvertimeRateRule.OvertimeType.NORMAL,
                defaults={'rate_multiplier': Decimal('1.25')},
            )
            OvertimeRateRule.objects.get_or_create(
                policy=policy,
                day_type=OvertimeRateRule.DayType.WEEKEND,
                overtime_type=OvertimeRateRule.OvertimeType.NORMAL,
                defaults={'rate_multiplier': Decimal('1.50')},
            )
            OvertimeRateRule.objects.get_or_create(
                policy=policy,
                day_type=OvertimeRateRule.DayType.PUBLIC_HOLIDAY,
                overtime_type=OvertimeRateRule.OvertimeType.NORMAL,
                defaults={'rate_multiplier': Decimal('2.00')},
            )

        jan_first = datetime.date(year, 1, 1)
        WorkCalendar.objects.get_or_create(
            tenant=company,
            date=jan_first,
            defaults={
                'day_type': WorkCalendar.DayType.PUBLIC_HOLIDAY,
                'holiday_name': 'New Year',
                'standard_work_minutes': 0,
            },
        )

        sample_day = datetime.date(year, 1, 2)
        WorkCalendar.objects.get_or_create(
            tenant=company,
            date=sample_day,
            defaults={
                'day_type': WorkCalendar.DayType.WORKING,
                'standard_work_minutes': 480,
            },
        )

        tz = ZoneInfo(company.timezone or 'UTC')
        sample_in = timezone.make_aware(datetime.datetime.combine(sample_day, datetime.time(8, 5)), tz)
        sample_out = timezone.make_aware(datetime.datetime.combine(sample_day, datetime.time(18, 30)), tz)

        AttendanceLog.objects.get_or_create(
            tenant=company,
            employee=employee,
            check_in=sample_in,
            defaults={
                'check_out': sample_out,
                'source': AttendanceLog.Source.WEB,
                'device_id': 'seed-device-001',
            },
        )

        self.stdout.write(self.style.SUCCESS(f'HRMS seed completed for organization={org_slug} company={company.id}'))
