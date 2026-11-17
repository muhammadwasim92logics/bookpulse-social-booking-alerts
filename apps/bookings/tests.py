import json
import datetime
from django.test import TestCase, Client
from django.utils import timezone
from django.contrib.auth import get_user_model
from unittest.mock import patch
from apps.bookings.models import Booking, AvailabilityRule
from apps.analytics.models import TrackedLink, Attribution
from apps.notifications.models import NotificationLog

User = get_user_model()


class RenownedHomesBookingTests(TestCase):
    def setUp(self):
        self.client = Client()
        
        # Create availability rule for all weekdays
        for day in range(7):
            AvailabilityRule.objects.create(
                weekday=day,
                start_time=datetime.time(9, 0),
                end_time=datetime.time(18, 0),
                slot_duration_minutes=45,
                buffer_minutes=15,
                minimum_notice_hours=0,
                max_advance_days=60,
                is_active=True
            )

        # Create admin staff user
        self.staff_user = User.objects.create_superuser(
            username="testadmin",
            email="admin@example.com",
            password="testpassword123"
        )

        # Tracked Link
        self.tracked_link = TrackedLink.objects.create(
            name="Instagram Test Reel",
            platform="instagram",
            campaign="spring-consultations",
            content_identifier="reel_test_99",
            clicks_count=10,
            bookings_count=1
        )

    def test_landing_page_renders_with_attribution(self):
        """Landing page should capture UTM attribution in session."""
        response = self.client.get('/?utm_source=instagram&utm_campaign=spring-consultations&utm_content=reel_test_99')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Renowned Homes")
        self.assertContains(response, "Book Your Consultation")
        
        # Verify tracked link click was incremented
        self.tracked_link.refresh_from_db()
        self.assertEqual(self.tracked_link.clicks_count, 11)

    def test_availability_api(self):
        """Test API slot generation for tomorrow."""
        tomorrow = (timezone.now() + datetime.timedelta(days=1)).date()
        response = self.client.get(f'/api/availability/?date={tomorrow.strftime("%Y-%m-%d")}')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get('is_open'))
        self.assertGreater(len(data.get('slots', [])), 0)

    @patch('apps.notifications.services.requests.post')
    def test_full_booking_and_verification_flow(self, mock_slack_post):
        """
        End-to-end test:
        1. User submits booking request
        2. System generates code & reference with status 'pending_verification'
        3. User verifies with 6-digit code
        4. Booking is confirmed & Slack notification is dispatched!
        """
        # Mock successful Slack webhook delivery
        mock_slack_post.return_value.status_code = 200
        mock_slack_post.return_value.text = "ok"

        appt_date = (timezone.now() + datetime.timedelta(days=2)).date().strftime("%Y-%m-%d")

        payload = {
            "full_name": "Demo Booking Contact",
            "email": "booking-contact@example.com",
            "phone": "+1 202-555-0104",
            "appointment_date": appt_date,
            "appointment_time": "10:00",
            "enquiry_type": "New-build home purchase",
            "social_username": "@demo_contact",
            "message": "Synthetic test message.",
            "consent_to_contact": True
        }

        # Step 1: Submit Booking
        res = self.client.post('/api/bookings/', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data.get('success'))
        self.assertIn('RH-', data.get('booking_reference'))
        
        ref = data.get('booking_reference')
        code = data.get('demo_code')
        self.assertEqual(len(code), 6)

        # Verify DB state before verification
        booking = Booking.objects.get(booking_reference=ref)
        self.assertEqual(booking.status, 'pending_verification')
        self.assertFalse(booking.is_email_verified)

        # Step 2: Test Invalid Code rejection
        bad_res = self.client.post('/api/bookings/verify/', data=json.dumps({
            "booking_reference": ref,
            "verification_code": "000000"
        }), content_type='application/json')
        self.assertEqual(bad_res.status_code, 400)
        self.assertFalse(bad_res.json().get('success'))

        # Step 3: Enter correct 6-digit confirmation code
        good_res = self.client.post('/api/bookings/verify/', data=json.dumps({
            "booking_reference": ref,
            "verification_code": code
        }), content_type='application/json')
        self.assertEqual(good_res.status_code, 200)
        good_data = good_res.json()
        self.assertTrue(good_data.get('success'))

        # Verify DB state after verification
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'confirmed')
        self.assertTrue(booking.is_email_verified)
        self.assertIsNotNone(booking.verified_at)

        # Step 4: Verify Slack webhook was invoked
        mock_slack_post.assert_called()
        log = NotificationLog.objects.filter(booking_reference=ref, channel='slack').first()
        self.assertIsNotNone(log)
        self.assertEqual(log.status, 'sent')

    def test_prevent_double_booking(self):
        """System must prevent two bookings for the exact same date and time slot."""
        target_date = (timezone.now() + datetime.timedelta(days=4)).date()
        target_time = datetime.time(11, 0)

        # Create an existing confirmed booking
        Booking.objects.create(
            booking_reference="RH-2026-TEST01",
            full_name="Existing Client",
            email="existing@example.com",
            phone="+1 202-555-0105",
            appointment_date=target_date,
            appointment_time=target_time,
            status='confirmed',
            is_email_verified=True
        )

        # Attempt to book the same slot
        payload = {
            "full_name": "New Client",
            "email": "new@example.com",
            "phone": "+1 202-555-0106",
            "appointment_date": target_date.strftime("%Y-%m-%d"),
            "appointment_time": "11:00",
            "enquiry_type": "Property investment enquiry",
            "consent_to_contact": True
        }

        res = self.client.post('/api/bookings/', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(res.status_code, 400)
        self.assertIn("just been booked", res.json().get('error'))

    def test_calendar_ics_generation(self):
        """Calendar ICS endpoint should return text/calendar RFC format."""
        booking = Booking.objects.create(
            booking_reference="RH-2026-ICS001",
            full_name="Demo Calendar Contact",
            email="marcus@example.com",
            phone="+1 202-555-0107",
            appointment_date=(timezone.now() + datetime.timedelta(days=5)).date(),
            appointment_time=datetime.time(14, 0),
            status='confirmed',
            is_email_verified=True
        )

        response = self.client.get(f'/api/bookings/{booking.booking_reference}/calendar.ics')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/calendar')
        self.assertIn(b'BEGIN:VCALENDAR', response.content)
        self.assertIn(b'RH-2026-ICS001', response.content)

    def test_admin_dashboard_auth_and_views(self):
        """Admin dashboard must be protected by login and render KPI metrics."""
        # Anonymous should redirect to login
        res = self.client.get('/dashboard/')
        self.assertEqual(res.status_code, 302)
        self.assertIn('/dashboard/login/', res.url)

        # Login as staff
        self.client.force_login(self.staff_user)
        res = self.client.get('/dashboard/')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Operations Overview")
        self.assertContains(res, "Total Bookings")

        # Bookings management list
        res_bookings = self.client.get('/dashboard/bookings/')
        self.assertEqual(res_bookings.status_code, 200)
        self.assertContains(res_bookings, "Bookings Management")

        # CSV export
        res_csv = self.client.get('/dashboard/bookings/export-csv/')
        self.assertEqual(res_csv.status_code, 200)
        self.assertEqual(res_csv['Content-Type'], 'text/csv')
