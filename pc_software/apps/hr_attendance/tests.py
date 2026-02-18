from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.hr_attendance.models import Attendance
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
