import datetime
from django.db import transaction, models
from django.utils import timezone
from .models import Booking, AvailabilityRule, AvailabilityException
from apps.notifications.services import SlackNotificationService, EmailNotificationService
from apps.analytics.models import Attribution, TrackedLink


class AvailabilityService:
    @classmethod
    def get_available_slots_for_date(cls, target_date):
        """
        Calculates time slots for a given date based on AvailabilityRules and existing bookings.
        """
        # Ensure target_date is a datetime.date
        if isinstance(target_date, str):
            target_date = datetime.datetime.strptime(target_date, "%Y-%m-%d").date()

        now = timezone.localtime()
        today = now.date()

        # Reject past dates
        if target_date < today:
            return {"date": str(target_date), "slots": [], "is_open": False, "message": "Cannot book past dates"}

        # Check for blackout/exceptions
        exception = AvailabilityException.objects.filter(date=target_date).first()
        if exception and exception.is_blocked:
            return {
                "date": str(target_date),
                "slots": [],
                "is_open": False,
                "message": f"Closed: {exception.reason}"
            }

        weekday = target_date.weekday()
        rule = AvailabilityRule.objects.filter(weekday=weekday, is_active=True).first()
        if not rule:
            # If no rule defined, provide standard business defaults (Monday-Saturday 09:00 - 18:00)
            if weekday == 6:  # Sunday closed by default
                return {"date": str(target_date), "slots": [], "is_open": False, "message": "Closed on Sundays"}
            start_time = datetime.time(9, 0)
            end_time = datetime.time(18, 0)
            slot_duration = 45
            buffer_minutes = 15
            minimum_notice_hours = 2
        else:
            start_time = rule.start_time
            end_time = rule.end_time
            slot_duration = rule.slot_duration_minutes
            buffer_minutes = rule.buffer_minutes
            minimum_notice_hours = rule.minimum_notice_hours

        # Existing bookings for that date
        booked_times = set(
            Booking.objects.filter(
                appointment_date=target_date,
                status__in=['pending', 'confirmed', 'pending_verification']
            ).values_list('appointment_time', flat=True)
        )

        slots = []
        step_minutes = slot_duration + buffer_minutes
        current_dt = datetime.datetime.combine(target_date, start_time)
        end_dt = datetime.datetime.combine(target_date, end_time)

        min_notice_delta = datetime.timedelta(hours=minimum_notice_hours)
        min_allowed_dt = now.replace(tzinfo=None) + min_notice_delta

        while current_dt + datetime.timedelta(minutes=slot_duration) <= end_dt:
            t = current_dt.time()
            is_past_or_too_soon = (current_dt < min_allowed_dt)
            is_taken = t in booked_times

            is_available = (not is_past_or_too_soon) and (not is_taken)

            slots.append({
                "time": t.strftime("%H:%M"),
                "display": t.strftime("%I:%M %p"),
                "is_available": is_available,
                "reason": "Already Booked" if is_taken else ("Past slot" if is_past_or_too_soon else "Available")
            })

            current_dt += datetime.timedelta(minutes=step_minutes)

        return {
            "date": str(target_date),
            "slots": slots,
            "is_open": len(slots) > 0,
            "message": "Slots loaded" if slots else "No slots available for this day"
        }


class BookingService:
    @classmethod
    def create_booking(cls, data, attribution_data=None):
        """
        Atomically validates and creates a new booking.
        Generates reference and 6-digit confirmation code, then sends verification email.
        """
        full_name = data.get('full_name', '').strip()
        email = data.get('email', '').strip().lower()
        phone = data.get('phone', '').strip()
        enquiry_type = data.get('enquiry_type', 'New-build home purchase').strip()
        appointment_date_str = data.get('appointment_date', '').strip()
        appointment_time_str = data.get('appointment_time', '').strip()
        social_username = data.get('social_username', '').strip()
        message = data.get('message', '').strip()
        consent_to_contact = data.get('consent_to_contact', True)
        marketing_consent = data.get('marketing_consent', False)

        if not full_name:
            raise ValueError("Please provide your full name.")
        if not email or "@" not in email:
            raise ValueError("Please provide a valid email address.")
        if not phone:
            raise ValueError("Please provide a contact phone number.")
        if not appointment_date_str or not appointment_time_str:
            raise ValueError("Please select a preferred date and time slot.")

        try:
            appointment_date = datetime.datetime.strptime(appointment_date_str, "%Y-%m-%d").date()
        except ValueError:
            raise ValueError("Invalid appointment date format.")

        try:
            # Support either HH:MM or HH:MM:SS
            parts = appointment_time_str.split(":")
            appointment_time = datetime.time(int(parts[0]), int(parts[1]))
        except Exception:
            raise ValueError("Invalid appointment time format.")

        # Check atomic slot availability inside transaction
        with transaction.atomic():
            slot_exists = Booking.objects.select_for_update().filter(
                appointment_date=appointment_date,
                appointment_time=appointment_time,
                status__in=['confirmed', 'pending']
            ).exists()

            if slot_exists:
                raise ValueError("The selected appointment slot has just been booked. Please choose another time.")

            # Resolve attribution
            attr_record = None
            if attribution_data:
                anon_id = attribution_data.get('anonymous_session_id', 'anon')
                tracked_link_id = attribution_data.get('tracked_link_id')
                tracked_link = None
                if tracked_link_id:
                    tracked_link = TrackedLink.objects.filter(id=tracked_link_id).first()

                attr_record = Attribution.objects.create(
                    anonymous_session_id=anon_id,
                    landing_page=attribution_data.get('landing_page', '/'),
                    source=attribution_data.get('utm_source', 'direct'),
                    medium=attribution_data.get('utm_medium', ''),
                    campaign=attribution_data.get('utm_campaign', ''),
                    content=attribution_data.get('utm_content', ''),
                    term=attribution_data.get('utm_term', ''),
                    platform=attribution_data.get('platform', attribution_data.get('utm_source', '')),
                    video_id=attribution_data.get('video_id', attribution_data.get('utm_content', '')),
                    tracked_link=tracked_link
                )

            reference = Booking.generate_unique_reference()
            booking = Booking(
                booking_reference=reference,
                full_name=full_name,
                email=email,
                phone=phone,
                social_username=social_username or None,
                enquiry_type=enquiry_type,
                message=message,
                appointment_date=appointment_date,
                appointment_time=appointment_time,
                timezone='Europe/London',
                status='pending_verification',
                consent_to_contact=bool(consent_to_contact),
                marketing_consent=bool(marketing_consent),
                attribution=attr_record,
            )
            code = booking.generate_verification_code()
            booking.save()

            # Send verification email with 6-digit code
            EmailNotificationService.send_verification_email(booking, code)

            return booking, code

    @classmethod
    def verify_booking_code(cls, booking_reference, submitted_code):
        """
        Verifies the 6-digit code for a booking.
        Once confirmed:
        - Changes status to 'confirmed'
        - Triggers Slack notification
        - Sends confirmation receipt email
        - Updates attribution conversions
        """
        booking = Booking.objects.filter(booking_reference=booking_reference.strip()).first()
        if not booking:
            return False, "Booking reference not found.", None

        success, message = booking.verify_code(submitted_code)
        if not success:
            return False, message, booking

        # Trigger Slack webhook notification
        slack_success, slack_msg = SlackNotificationService.send_booking_notification(booking, event_type="booking_confirmed")

        # Send confirmation email
        EmailNotificationService.send_confirmation_receipt_email(booking)

        # Increment tracked link conversion if linked
        if booking.attribution and booking.attribution.tracked_link:
            TrackedLink.objects.filter(id=booking.attribution.tracked_link_id).update(
                bookings_count=models.F('bookings_count') + 1
            )

        return True, "Your appointment has been verified and confirmed! A notification has been dispatched.", booking
