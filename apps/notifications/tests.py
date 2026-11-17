import datetime
from django.test import TestCase
from django.utils import timezone
from unittest.mock import patch, MagicMock
from apps.bookings.models import Booking
from apps.notifications.models import NotificationLog
from apps.notifications.services import SlackNotificationService, EmailNotificationService


class NotificationServiceTests(TestCase):
    def setUp(self):
        self.booking = Booking.objects.create(
            booking_reference="RH-2026-TESTNOTIF",
            full_name="Demo Contact",
            email="demo-contact@example.com",
            phone="+1 202-555-0103",
            appointment_date=timezone.now().date() + datetime.timedelta(days=3),
            appointment_time=datetime.time(15, 30),
            timezone="Europe/London",
            enquiry_type="Property investment enquiry",
            social_username="@charlotte_b",
            status="confirmed",
            is_email_verified=True
        )

    @patch('apps.notifications.services.requests.post')
    def test_slack_notification_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "ok"
        mock_post.return_value = mock_resp

        success, msg = SlackNotificationService.send_booking_notification(self.booking)
        self.assertTrue(success)
        self.assertIn("Notification delivered", msg)

        # Check log
        log = NotificationLog.objects.filter(booking_reference=self.booking.booking_reference, channel='slack').first()
        self.assertIsNotNone(log)
        self.assertEqual(log.status, 'sent')
        self.assertIn("RH-2026-TESTNOTIF", log.payload_preview)

    @patch('apps.notifications.services.requests.post')
    def test_slack_notification_idempotency(self, mock_post):
        """Second call with same event should be skipped as already delivered."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        # First call
        SlackNotificationService.send_booking_notification(self.booking)
        self.assertEqual(mock_post.call_count, 1)

        # Second call
        success, msg = SlackNotificationService.send_booking_notification(self.booking)
        self.assertTrue(success)
        self.assertIn("previously delivered", msg)
        self.assertEqual(mock_post.call_count, 1)  # Was not called again!

    @patch('apps.notifications.services.send_mail')
    def test_email_verification_sending(self, mock_send_mail):
        mock_send_mail.return_value = 1
        success, msg = EmailNotificationService.send_verification_email(self.booking, "582914")
        self.assertTrue(success)
        mock_send_mail.assert_called_once()
        
        log = NotificationLog.objects.filter(booking_reference=self.booking.booking_reference, channel='email').first()
        self.assertIsNotNone(log)
        self.assertEqual(log.status, 'sent')
