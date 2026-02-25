from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.hr_attendance.models import Attendance, AttendanceChangeLog
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
