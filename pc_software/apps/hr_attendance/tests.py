from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
import datetime

from apps.hr_attendance.models import Attendance, AttendanceChangeLog
from apps.hrms.models import Company, Employee as HrmsEmployee, EmployeeShiftAssignment, ShiftTemplate, ShiftVersion, WorkCalendar
from apps.hr_personnel.models import Employee
from apps.organizations.models import Organization
from apps.users.models import UserProfile


User = get_user_model()


class AttendanceFlowTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Test Org', slug='test-org')
        self.user = User.objects.create_user(username='employee', password='pass1234')
        profile = self.user.profile if hasattr(self.user, 'profile') else UserProfile(user=self.user)
        profile.organization = self.org
        profile.role = 'user'
        profile.save()

    def test_quick_clock_page_renders(self):
        self.client.login(username='employee', password='pass1234')
        resp = self.client.get(reverse('hr_attendance:quick_clock'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'quickAttendanceForm')

    def test_quick_clock_shows_both_lunch_and_end_day_actions_after_clock_in(self):
        self.client.login(username='employee', password='pass1234')
        self.client.post(reverse('hr_attendance:clock_in'), {'next': 'quick'})

        resp = self.client.get(reverse('hr_attendance:quick_clock'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Start Lunch Break')
        self.assertContains(resp, 'Clock Out (End Day)')

    def test_clock_out_end_day_mode_after_clock_in_records_clock_out_without_lunch(self):
        self.client.login(username='employee', password='pass1234')
        self.client.post(reverse('hr_attendance:clock_in'), {'next': 'quick'})

        resp = self.client.post(
            reverse('hr_attendance:clock_out'),
            {
                'next': 'quick',
                'out_mode': 'end_day',
            },
        )
        self.assertEqual(resp.status_code, 302)

        attendance = Attendance.objects.get(user=self.user, date=timezone.localtime(timezone.now()).date())
        self.assertIsNotNone(attendance.clock_out)
        self.assertIsNone(attendance.lunch_out)
        self.assertEqual(attendance.clock_out_by, self.user)

    def test_clock_in_saves_clock_in_location(self):
        self.client.login(username='employee', password='pass1234')
        resp = self.client.post(
            reverse('hr_attendance:clock_in'),
            {
                'latitude': '35.700000',
                'longitude': '51.400000',
                'next': 'quick',
            },
        )
        self.assertEqual(resp.status_code, 302)

        attendance = Attendance.objects.get(user=self.user)
        self.assertIsNotNone(attendance.clock_in)
        self.assertEqual(str(attendance.clock_in_latitude), '35.700000')
        self.assertEqual(str(attendance.clock_in_longitude), '51.400000')
        self.assertEqual(attendance.clock_in_by, self.user)

    def test_supervisor_clock_in_marks_actor(self):
        supervisor = User.objects.create_user(username='supervisor', password='pass1234')
        supervisor_profile = supervisor.profile if hasattr(supervisor, 'profile') else UserProfile(user=supervisor)
        supervisor_profile.organization = self.org
        supervisor_profile.role = 'supervisor'
        supervisor_profile.save()

        self.client.login(username='supervisor', password='pass1234')
        resp = self.client.post(
            reverse('hr_attendance:supervisor_clock_in', kwargs={'user_id': self.user.id}),
            {'date': '2026-02-18'},
        )
        self.assertEqual(resp.status_code, 302)

        attendance = Attendance.objects.get(user=self.user, date='2026-02-18')
        self.assertEqual(attendance.clock_in_by, supervisor)

    def test_supervisor_action_set_in_creates_change_log(self):
        supervisor = User.objects.create_user(username='supervisor2', password='pass1234')
        supervisor_profile = supervisor.profile if hasattr(supervisor, 'profile') else UserProfile(user=supervisor)
        supervisor_profile.organization = self.org
        supervisor_profile.role = 'supervisor'
        supervisor_profile.save()
        self.user.profile.supervisor = supervisor
        self.user.profile.save(update_fields=['supervisor'])

        self.client.login(username='supervisor2', password='pass1234')
        resp = self.client.post(
            reverse('hr_attendance:supervisor_attendance_action', kwargs={'user_id': self.user.id}),
            {'date': '2026-02-19', 'action': 'set_in', 'time_value': '08:30'},
        )
        self.assertEqual(resp.status_code, 302)

        attendance = Attendance.objects.get(user=self.user, date='2026-02-19')
        self.assertIsNotNone(attendance.clock_in)
        self.assertEqual(attendance.clock_in_by, supervisor)

        log = AttendanceChangeLog.objects.filter(attendance=attendance).latest('performed_at')
        self.assertEqual(log.field_name, 'clock_in')
        self.assertEqual(log.action_type, 'set')
        self.assertEqual(log.performed_by, supervisor)

    def test_supervisor_action_delete_out_creates_delete_log(self):
        supervisor = User.objects.create_user(username='supervisor3', password='pass1234')
        supervisor_profile = supervisor.profile if hasattr(supervisor, 'profile') else UserProfile(user=supervisor)
        supervisor_profile.organization = self.org
        supervisor_profile.role = 'supervisor'
        supervisor_profile.save()
        self.user.profile.supervisor = supervisor
        self.user.profile.save(update_fields=['supervisor'])

        self.client.login(username='supervisor3', password='pass1234')
        self.client.post(
            reverse('hr_attendance:supervisor_attendance_action', kwargs={'user_id': self.user.id}),
            {'date': '2026-02-20', 'action': 'set_out', 'time_value': '17:10'},
        )
        resp = self.client.post(
            reverse('hr_attendance:supervisor_attendance_action', kwargs={'user_id': self.user.id}),
            {'date': '2026-02-20', 'action': 'delete_out'},
        )
        self.assertEqual(resp.status_code, 302)

        attendance = Attendance.objects.get(user=self.user, date='2026-02-20')
        self.assertIsNone(attendance.clock_out)

        delete_log = AttendanceChangeLog.objects.filter(attendance=attendance, field_name='clock_out', action_type='delete').first()
        self.assertIsNotNone(delete_log)
        self.assertEqual(delete_log.performed_by, supervisor)

    def test_supervisor_action_set_in_for_employee_without_user(self):
        supervisor = User.objects.create_user(username='supervisor4', password='pass1234')
        supervisor_profile = supervisor.profile if hasattr(supervisor, 'profile') else UserProfile(user=supervisor)
        supervisor_profile.organization = self.org
        supervisor_profile.role = 'supervisor'
        supervisor_profile.save()

        supervisor_employee = Employee.objects.create(
            user=supervisor,
            organization=self.org,
            first_name='Supervisor',
            last_name='One',
            employee_id='SUP-01',
        )
        worker = Employee.objects.create(
            organization=self.org,
            first_name='Worker',
            last_name='NoUser',
            employee_id='EMP-NU-01',
            reporting_manager=supervisor_employee,
        )

        self.client.login(username='supervisor4', password='pass1234')
        resp = self.client.post(
            reverse('hr_attendance:supervisor_attendance_action_employee', kwargs={'employee_id': worker.id}),
            {'date': '2026-02-21', 'action': 'set_in', 'time_value': '08:15'},
        )
        self.assertEqual(resp.status_code, 302)

        attendance = Attendance.objects.get(employee=worker, date='2026-02-21')
        self.assertIsNone(attendance.user)
        self.assertIsNotNone(attendance.clock_in)
        self.assertEqual(attendance.clock_in_by, supervisor)

    def test_supervisor_bulk_range_entry_for_employee_without_user(self):
        supervisor = User.objects.create_user(username='supervisor5', password='pass1234')
        supervisor_profile = supervisor.profile if hasattr(supervisor, 'profile') else UserProfile(user=supervisor)
        supervisor_profile.organization = self.org
        supervisor_profile.role = 'supervisor'
        supervisor_profile.save()

        supervisor_employee = Employee.objects.create(
            user=supervisor,
            organization=self.org,
            first_name='Supervisor',
            last_name='Bulk',
            employee_id='SUP-BULK-01',
        )
        worker = Employee.objects.create(
            organization=self.org,
            first_name='Worker',
            last_name='BulkNoUser',
            employee_id='EMP-BULK-NU-01',
            reporting_manager=supervisor_employee,
        )

        self.client.login(username='supervisor5', password='pass1234')
        resp = self.client.post(
            reverse('hr_attendance:supervisor_bulk_range_entry'),
            {
                'employee_id': str(worker.id),
                'start_date': '2026-02-22',
                'end_date': '2026-02-24',
                'in_time': '08:00',
                'out_time': '17:00',
            },
        )
        self.assertEqual(resp.status_code, 302)

        records = Attendance.objects.filter(employee=worker, date__range=('2026-02-22', '2026-02-24')).order_by('date')
        self.assertEqual(records.count(), 3)
        for row in records:
            self.assertIsNotNone(row.clock_in)
            self.assertIsNotNone(row.clock_out)
            self.assertEqual(row.clock_in_by, supervisor)
            self.assertEqual(row.clock_out_by, supervisor)

    def test_supervisor_bulk_range_entry_saves_optional_lunch_times(self):
        supervisor = User.objects.create_user(username='supervisor7', password='pass1234')
        supervisor_profile = supervisor.profile if hasattr(supervisor, 'profile') else UserProfile(user=supervisor)
        supervisor_profile.organization = self.org
        supervisor_profile.role = 'supervisor'
        supervisor_profile.save()

        supervisor_employee = Employee.objects.create(
            user=supervisor,
            organization=self.org,
            first_name='Supervisor',
            last_name='Lunch',
            employee_id='SUP-BULK-02',
        )
        worker = Employee.objects.create(
            organization=self.org,
            first_name='Worker',
            last_name='LunchNoUser',
            employee_id='EMP-BULK-NU-02',
            reporting_manager=supervisor_employee,
        )

        self.client.login(username='supervisor7', password='pass1234')
        resp = self.client.post(
            reverse('hr_attendance:supervisor_bulk_range_entry'),
            {
                'employee_id': str(worker.id),
                'start_date': '2026-02-25',
                'end_date': '2026-02-26',
                'in_time': '08:00',
                'lunch_out_time': '12:30',
                'lunch_in_time': '13:15',
                'out_time': '17:00',
            },
        )
        self.assertEqual(resp.status_code, 302)

        records = Attendance.objects.filter(employee=worker, date__range=('2026-02-25', '2026-02-26')).order_by('date')
        self.assertEqual(records.count(), 2)
        for row in records:
            self.assertIsNotNone(row.lunch_out)
            self.assertIsNotNone(row.lunch_in)
            self.assertEqual(row.lunch_out_by, supervisor)
            self.assertEqual(row.lunch_in_by, supervisor)

    def test_attendance_card_connect_employee_without_user_to_supervisor(self):
        supervisor = User.objects.create_user(username='supervisor6', password='pass1234')
        supervisor_profile = supervisor.profile if hasattr(supervisor, 'profile') else UserProfile(user=supervisor)
        supervisor_profile.organization = self.org
        supervisor_profile.role = 'supervisor'
        supervisor_profile.save()

        supervisor_employee = Employee.objects.create(
            user=supervisor,
            organization=self.org,
            first_name='Supervisor',
            last_name='Connector',
            employee_id='SUP-CON-01',
        )
        worker = Employee.objects.create(
            organization=self.org,
            first_name='Worker',
            last_name='ConnectNoUser',
            employee_id='EMP-CON-NU-01',
            reporting_manager=None,
        )

        self.client.login(username='supervisor6', password='pass1234')
        resp = self.client.post(
            reverse('hr_attendance:attendance_card'),
            {
                'action': 'connect_supervisor',
                'employee_id': str(worker.id),
                'month': '2026-03',
            },
        )
        self.assertEqual(resp.status_code, 302)

        worker.refresh_from_db()
        self.assertEqual(worker.reporting_manager_id, supervisor_employee.id)

    def test_attendance_card_pdf_endpoint_is_reachable(self):
        supervisor = User.objects.create_user(username='supervisor8', password='pass1234')
        supervisor_profile = supervisor.profile if hasattr(supervisor, 'profile') else UserProfile(user=supervisor)
        supervisor_profile.organization = self.org
        supervisor_profile.role = 'supervisor'
        supervisor_profile.save()

        employee = Employee.objects.create(
            organization=self.org,
            first_name='Pdf',
            last_name='Worker',
            employee_id='EMP-PDF-01',
        )

        self.client.login(username='supervisor8', password='pass1234')
        resp = self.client.get(
            reverse('hr_attendance:attendance_card_pdf'),
            {'employee_id': str(employee.id), 'month': '2026-03'},
        )

        self.assertIn(resp.status_code, [200, 503])
        if resp.status_code == 200:
            self.assertEqual(resp['Content-Type'], 'application/pdf')
            self.assertIn('attachment; filename=', resp['Content-Disposition'])

    def test_supervisor_bulk_range_entry_skips_public_holiday_and_keeps_entered_clock_out(self):
        supervisor = User.objects.create_user(username='supervisor9', password='pass1234')
        supervisor_profile = supervisor.profile if hasattr(supervisor, 'profile') else UserProfile(user=supervisor)
        supervisor_profile.organization = self.org
        supervisor_profile.role = 'supervisor'
        supervisor_profile.save()

        supervisor_employee = Employee.objects.create(
            user=supervisor,
            organization=self.org,
            first_name='Supervisor',
            last_name='Policy',
            employee_id='SUP-POL-01',
        )
        worker = Employee.objects.create(
            organization=self.org,
            first_name='Worker',
            last_name='PolicyNoUser',
            employee_id='EMP-POL-NU-01',
            reporting_manager=supervisor_employee,
        )

        tenant, _ = Company.objects.get_or_create(
            organization=self.org,
            defaults={
                'name': 'Test Tenant',
                'country': 'OM',
            },
        )
        hrms_employee = HrmsEmployee.objects.create(
            tenant=tenant,
            personnel_employee=worker,
            employee_code='HRMS-EMP-01',
            first_name='Worker',
            last_name='PolicyNoUser',
            hire_date='2026-01-01',
        )
        shift = ShiftTemplate.objects.create(tenant=tenant, name='Morning Shift')
        ShiftVersion.objects.create(
            tenant=tenant,
            shift=shift,
            valid_from='2026-01-01',
            valid_to='2026-12-31',
            start_time='08:00',
            end_time='15:00',
            required_work_minutes=240,
        )
        EmployeeShiftAssignment.objects.create(
            tenant=tenant,
            employee=hrms_employee,
            shift=shift,
            effective_from='2026-01-01',
            is_active=True,
        )
        WorkCalendar.objects.create(
            tenant=tenant,
            date='2026-03-13',
            day_type=WorkCalendar.DayType.PUBLIC_HOLIDAY,
            holiday_name='National Holiday',
            standard_work_minutes=0,
        )
        WorkCalendar.objects.create(
            tenant=tenant,
            date='2026-03-14',
            day_type=WorkCalendar.DayType.WORKING,
            standard_work_minutes=240,
        )

        self.client.login(username='supervisor9', password='pass1234')
        resp = self.client.post(
            reverse('hr_attendance:supervisor_bulk_range_entry'),
            {
                'employee_id': str(worker.id),
                'start_date': '2026-03-13',
                'end_date': '2026-03-14',
                'in_time': '08:00',
                'out_time': '18:00',
            },
        )
        self.assertEqual(resp.status_code, 302)

        self.assertFalse(Attendance.objects.filter(employee=worker, date='2026-03-13').exists())
        working_day = Attendance.objects.get(employee=worker, date='2026-03-14')
        self.assertIsNotNone(working_day.clock_out)
        self.assertEqual(timezone.localtime(working_day.clock_out).strftime('%H:%M'), '18:00')

    def test_supervisor_bulk_range_requires_confirmation_before_replacing_existing_rows(self):
        supervisor = User.objects.create_user(username='supervisor10', password='pass1234')
        supervisor_profile = supervisor.profile if hasattr(supervisor, 'profile') else UserProfile(user=supervisor)
        supervisor_profile.organization = self.org
        supervisor_profile.role = 'supervisor'
        supervisor_profile.save()

        supervisor_employee = Employee.objects.create(
            user=supervisor,
            organization=self.org,
            first_name='Supervisor',
            last_name='Replace',
            employee_id='SUP-REP-01',
        )
        worker = Employee.objects.create(
            organization=self.org,
            first_name='Worker',
            last_name='Replace',
            employee_id='EMP-REP-01',
            reporting_manager=supervisor_employee,
        )

        tenant, _ = Company.objects.get_or_create(
            organization=self.org,
            defaults={
                'name': 'Replace Tenant',
                'country': 'OM',
            },
        )
        hrms_employee = HrmsEmployee.objects.create(
            tenant=tenant,
            personnel_employee=worker,
            employee_code='HRMS-EMP-REP-01',
            first_name='Worker',
            last_name='Replace',
            hire_date='2026-01-01',
        )
        shift = ShiftTemplate.objects.create(tenant=tenant, name='Replace Shift')
        ShiftVersion.objects.create(
            tenant=tenant,
            shift=shift,
            valid_from='2026-01-01',
            valid_to='2026-12-31',
            start_time='08:00',
            end_time='17:00',
            required_work_minutes=480,
        )
        EmployeeShiftAssignment.objects.create(
            tenant=tenant,
            employee=hrms_employee,
            shift=shift,
            effective_from='2026-01-01',
            is_active=True,
        )
        WorkCalendar.objects.create(
            tenant=tenant,
            date='2026-01-01',
            day_type=WorkCalendar.DayType.PUBLIC_HOLIDAY,
            holiday_name='Holiday',
            standard_work_minutes=0,
        )
        WorkCalendar.objects.create(
            tenant=tenant,
            date='2026-01-02',
            day_type=WorkCalendar.DayType.WORKING,
            standard_work_minutes=480,
        )

        self.client.login(username='supervisor10', password='pass1234')
        self.client.post(
            reverse('hr_attendance:supervisor_bulk_range_entry'),
            {
                'employee_id': str(worker.id),
                'start_date': '2026-01-01',
                'end_date': '2026-01-02',
                'in_time': '08:00',
                'out_time': '17:00',
                'confirm_replace': '1',
            },
        )
        self.assertEqual(Attendance.objects.filter(employee=worker, date__range=('2026-01-01', '2026-01-02')).count(), 1)

        pre_count = Attendance.objects.filter(employee=worker, date__range=('2026-01-01', '2026-01-02')).count()
        self.assertEqual(pre_count, 1)

        preview_resp = self.client.post(
            reverse('hr_attendance:supervisor_bulk_range_entry'),
            {
                'employee_id': str(worker.id),
                'start_date': '2026-01-01',
                'end_date': '2026-01-02',
                'in_time': '09:15',
                'out_time': '17:10',
            },
        )
        self.assertEqual(preview_resp.status_code, 200)
        self.assertContains(preview_resp, 'Confirm Replace Existing Records')
        self.assertEqual(Attendance.objects.filter(employee=worker, date__range=('2026-01-01', '2026-01-02')).count(), pre_count)

        confirm_resp = self.client.post(
            reverse('hr_attendance:supervisor_bulk_range_entry'),
            {
                'employee_id': str(worker.id),
                'start_date': '2026-01-01',
                'end_date': '2026-01-02',
                'in_time': '09:15',
                'out_time': '17:10',
                'confirm_replace': '1',
            },
        )
        self.assertEqual(confirm_resp.status_code, 302)
        self.assertFalse(Attendance.objects.filter(employee=worker, date='2026-01-01').exists())
        replaced_working = Attendance.objects.get(employee=worker, date='2026-01-02')
        self.assertEqual(timezone.localtime(replaced_working.clock_in).strftime('%H:%M'), '09:15')

    def test_supervisor_bulk_range_confirm_replace_accepts_duplicate_post_values(self):
        supervisor = User.objects.create_user(username='supervisor11', password='pass1234')
        supervisor_profile = supervisor.profile if hasattr(supervisor, 'profile') else UserProfile(user=supervisor)
        supervisor_profile.organization = self.org
        supervisor_profile.role = 'supervisor'
        supervisor_profile.save()

        supervisor_employee = Employee.objects.create(
            user=supervisor,
            organization=self.org,
            first_name='Supervisor',
            last_name='ReplaceDup',
            employee_id='SUP-REP-02',
        )
        worker = Employee.objects.create(
            organization=self.org,
            first_name='Worker',
            last_name='ReplaceDup',
            employee_id='EMP-REP-02',
            reporting_manager=supervisor_employee,
        )

        self.client.login(username='supervisor11', password='pass1234')

        Attendance.objects.create(
            employee=worker,
            date='2026-01-05',
            clock_in=timezone.make_aware(datetime.datetime(2026, 1, 5, 8, 0), timezone.get_current_timezone()),
            clock_out=timezone.make_aware(datetime.datetime(2026, 1, 5, 17, 0), timezone.get_current_timezone()),
        )

        confirm_resp = self.client.post(
            reverse('hr_attendance:supervisor_bulk_range_entry'),
            {
                'employee_id': str(worker.id),
                'start_date': '2026-01-05',
                'end_date': '2026-01-05',
                'in_time': '09:30',
                'out_time': '18:10',
                'confirm_replace': ['0', '1'],
            },
        )

        self.assertEqual(confirm_resp.status_code, 302)
        replaced = Attendance.objects.get(employee=worker, date='2026-01-05')
        self.assertEqual(timezone.localtime(replaced.clock_in).strftime('%H:%M'), '09:30')
        self.assertEqual(timezone.localtime(replaced.clock_out).strftime('%H:%M'), '18:10')

    def test_supervisor_bulk_range_confirm_replace_accepts_submit_action_list(self):
        supervisor = User.objects.create_user(username='supervisor12', password='pass1234')
        supervisor_profile = supervisor.profile if hasattr(supervisor, 'profile') else UserProfile(user=supervisor)
        supervisor_profile.organization = self.org
        supervisor_profile.role = 'supervisor'
        supervisor_profile.save()

        supervisor_employee = Employee.objects.create(
            user=supervisor,
            organization=self.org,
            first_name='Supervisor',
            last_name='SubmitAction',
            employee_id='SUP-REP-03',
        )
        worker = Employee.objects.create(
            organization=self.org,
            first_name='Worker',
            last_name='SubmitAction',
            employee_id='EMP-REP-03',
            reporting_manager=supervisor_employee,
        )

        self.client.login(username='supervisor12', password='pass1234')

        Attendance.objects.create(
            employee=worker,
            date='2026-01-06',
            clock_in=timezone.make_aware(datetime.datetime(2026, 1, 6, 8, 0), timezone.get_current_timezone()),
            clock_out=timezone.make_aware(datetime.datetime(2026, 1, 6, 17, 0), timezone.get_current_timezone()),
        )

        confirm_resp = self.client.post(
            reverse('hr_attendance:supervisor_bulk_range_entry'),
            {
                'employee_id': str(worker.id),
                'start_date': '2026-01-06',
                'end_date': '2026-01-06',
                'in_time': '09:40',
                'out_time': '18:20',
                'submit_action': ['apply', 'confirm_replace_apply'],
            },
        )

        self.assertEqual(confirm_resp.status_code, 302)
        replaced = Attendance.objects.get(employee=worker, date='2026-01-06')
        self.assertEqual(timezone.localtime(replaced.clock_in).strftime('%H:%M'), '09:40')
        self.assertEqual(timezone.localtime(replaced.clock_out).strftime('%H:%M'), '18:20')

    def test_supervisor_bulk_range_applies_selected_shift_schedule(self):
        supervisor = User.objects.create_user(username='supervisor13', password='pass1234')
        supervisor_profile = supervisor.profile if hasattr(supervisor, 'profile') else UserProfile(user=supervisor)
        supervisor_profile.organization = self.org
        supervisor_profile.role = 'supervisor'
        supervisor_profile.save()

        supervisor_employee = Employee.objects.create(
            user=supervisor,
            organization=self.org,
            first_name='Supervisor',
            last_name='ShiftRange',
            employee_id='SUP-SHIFT-01',
        )
        worker = Employee.objects.create(
            organization=self.org,
            first_name='Worker',
            last_name='ShiftRange',
            employee_id='EMP-SHIFT-01',
            reporting_manager=supervisor_employee,
        )

        tenant, _ = Company.objects.get_or_create(
            organization=self.org,
            defaults={
                'name': 'Shift Tenant',
                'country': 'OM',
            },
        )
        shift = ShiftTemplate.objects.create(tenant=tenant, name='Shift Apply')
        ShiftVersion.objects.create(
            tenant=tenant,
            shift=shift,
            valid_from='2026-04-01',
            valid_to='2026-04-30',
            start_time='06:15',
            end_time='17:45',
            required_work_minutes=480,
        )

        self.client.login(username='supervisor13', password='pass1234')
        resp = self.client.post(
            reverse('hr_attendance:supervisor_bulk_range_entry'),
            {
                'employee_id': str(worker.id),
                'start_date': '2026-04-01',
                'end_date': '2026-04-02',
                'use_shift_schedule': '1',
                'shift_id': str(shift.id),
                'submit_action': 'apply',
            },
        )

        self.assertEqual(resp.status_code, 302)
        records = Attendance.objects.filter(employee=worker, date__range=('2026-04-01', '2026-04-02')).order_by('date')
        self.assertEqual(records.count(), 2)
        for row in records:
            self.assertEqual(timezone.localtime(row.clock_in).strftime('%H:%M'), '06:15')
            self.assertEqual(timezone.localtime(row.clock_out).strftime('%H:%M'), '17:45')
