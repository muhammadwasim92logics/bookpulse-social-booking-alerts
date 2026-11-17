from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from unittest.mock import patch
from apps.bookings.models import Booking
from apps.notifications.models import NotificationLog
import datetime


class DashboardApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_superuser(
            username='adminuser',
            email='admin@example.com',
            password='Password123!'
        )
        self.client.login(username='adminuser', password='Password123!')
        
        self.booking = Booking.objects.create(
            booking_reference='RH-2026-TEST01',
            full_name='Demo Contact',
            email='client@example.com',
            phone='+1 202-555-0108',
            enquiry_type='New Developments Search',
            appointment_date=datetime.date(2026, 11, 20),
            appointment_time=datetime.time(14, 0),
            status='confirmed',
            is_email_verified=True,
            verification_code='123456'
        )

    def test_booking_detail_api(self):
        url = reverse('dashboard:api_booking_detail', kwargs={'pk': self.booking.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['booking']['reference'], 'RH-2026-TEST01')

    @patch('apps.notifications.services.SlackNotificationService.send_booking_notification')
    def test_resend_slack_notification_api(self, mock_slack):
        mock_slack.return_value = (True, "Notification delivered to Slack.")
        url = reverse('dashboard:api_resend_slack', kwargs={'pk': self.booking.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['reference'], 'RH-2026-TEST01')
        mock_slack.assert_called_once_with(self.booking, event_type="booking_confirmed", force=True)

    def test_update_booking_status(self):
        url = reverse('dashboard:api_update_booking', kwargs={'pk': self.booking.pk})
        response = self.client.post(url, data={'status': 'completed', 'internal_notes': 'Client consultation finished.'})
        self.assertEqual(response.status_code, 200)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, 'completed')
        self.assertEqual(self.booking.internal_notes, 'Client consultation finished.')
