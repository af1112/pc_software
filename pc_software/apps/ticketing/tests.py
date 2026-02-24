from datetime import datetime, timezone as dt_timezone

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.utils import timezone

from apps.ticketing.models import Ticket
from apps.users.templatetags.local_dates import localized_date


User = get_user_model()


class TicketSerialTests(TestCase):
    def test_issuer_serial_is_sequential_per_creator(self):
        creator_a = User.objects.create_user(username="issuer_a", password="x")
        creator_b = User.objects.create_user(username="issuer_b", password="x")

        t1 = Ticket.objects.create(title="A-1", description="d", created_by=creator_a)
        t2 = Ticket.objects.create(title="A-2", description="d", created_by=creator_a)
        t3 = Ticket.objects.create(title="B-1", description="d", created_by=creator_b)

        self.assertEqual(t1.issuer_serial, 1)
        self.assertEqual(t2.issuer_serial, 2)
        self.assertEqual(t3.issuer_serial, 1)

        self.assertEqual(t1.serial_display, f"{creator_a.id}0001")
        self.assertEqual(t2.serial_display, f"{creator_a.id}0002")
        self.assertEqual(t3.serial_display, f"{creator_b.id}0001")


class LocalizedDateTimezoneTests(TestCase):
    def test_localized_date_uses_active_timezone_for_aware_datetime(self):
        request = RequestFactory().get("/")
        request.LANGUAGE_CODE = "en"

        value = datetime(2026, 1, 1, 12, 0, tzinfo=dt_timezone.utc)

        with timezone.override("Asia/Tehran"):
            rendered = localized_date({"request": request}, value, "H:i")

        self.assertEqual(rendered, "15:30")
