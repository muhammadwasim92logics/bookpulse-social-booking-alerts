import logging
import requests
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from .models import NotificationLog

logger = logging.getLogger(__name__)


class SlackNotificationService:
    @classmethod
    def send_booking_notification(cls, booking, event_type="booking_confirmed", force=False):
        """
        Sends Slack Incoming Webhook notification when a booking is confirmed or created.
        """
        if not getattr(settings, 'SLACK_ENABLED', True):
            logger.info("Slack notifications are disabled via SLACK_ENABLED setting.")
            return False, "Slack notifications are disabled."

        webhook_url = getattr(settings, 'SLACK_WEBHOOK_URL', '').strip()
        if not webhook_url:
            logger.warning("SLACK_WEBHOOK_URL is not configured.")
            return False, "SLACK_WEBHOOK_URL is not configured."

        idempotency_key = f"slack_{booking.booking_reference}_{event_type}"
        
        # Check idempotency: avoid duplicate deliveries for the exact same event unless forced
        if not force:
            existing_log = NotificationLog.objects.filter(
                idempotency_key=idempotency_key,
                status='sent'
            ).first()
            if existing_log:
                logger.info(f"Slack notification for {idempotency_key} already sent.")
                return True, "Notification previously delivered."
        else:
            idempotency_key = f"slack_{booking.booking_reference}_{event_type}_{int(timezone.now().timestamp())}"

        # Prepare details
        date_str = booking.appointment_date.strftime("%d %B %Y")
        time_str = booking.appointment_time.strftime("%H:%M")
        timezone_str = booking.timezone or "Europe/London"

        # Extract attribution details if present
        source_str = "Direct / Website"
        campaign_str = "None"
        video_str = "None"

        if booking.attribution:
            attr = booking.attribution
            source_str = attr.platform or attr.source or "Direct"
            campaign_str = attr.campaign or "None"
            video_str = attr.video_id or attr.content or "None"

        social_user = f"@{booking.social_username.lstrip('@')}" if booking.social_username else "Not provided"

        # Format exact message as specified in README.md (with <!here> mention for active push alerts)
        fallback_text = (
            f"<!here> *New Appointment Request*\n\n"
            f"*Booking reference:* `{booking.booking_reference}`\n"
            f"*Name:* {booking.full_name}\n"
            f"*Email:* {booking.email}\n"
            f"*Phone:* {booking.phone}\n"
            f"*Enquiry type:* {booking.enquiry_type}\n"
            f"*Requested date:* {date_str}\n"
            f"*Requested time:* {time_str} ({timezone_str})\n"
            f"*Social username:* {social_user}\n"
            f"*Source:* {source_str.capitalize()}\n"
            f"*Campaign:* {campaign_str}\n"
            f"*Video:* {video_str}\n"
            f"*Status:* Confirmed (Email Verified)"
        )

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🏠 New Appointment Confirmed — Renowned Homes",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"<!here> *New confirmed consultation request from {booking.full_name}*"
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Reference:*\n`{booking.booking_reference}`"},
                    {"type": "mrkdwn", "text": f"*Status:*\n✅ *Confirmed (Verified)*"},
                    {"type": "mrkdwn", "text": f"*Client Name:*\n{booking.full_name}"},
                    {"type": "mrkdwn", "text": f"*Contact:*\n{booking.phone}\n<{booking.email}>"},
                    {"type": "mrkdwn", "text": f"*Appointment:*\n📅 {date_str}\n⏰ {time_str} ({timezone_str})"},
                    {"type": "mrkdwn", "text": f"*Enquiry Type:*\n{booking.enquiry_type}"},
                    {"type": "mrkdwn", "text": f"*Social Handle:*\n{social_user}"},
                    {"type": "mrkdwn", "text": f"*Attribution:*\nSource: *{source_str.capitalize()}*\nCampaign: {campaign_str}\nVideo ID: `{video_str}`"},
                ]
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"📍 Renowned Homes System | Logged at {timezone.now().strftime('%Y-%m-%d %H:%M:%S UTC')}"
                    }
                ]
            }
        ]

        target_channel = getattr(settings, 'SLACK_CHANNEL', 'new-bookings').strip()
        if not target_channel.startswith('#') and not target_channel.startswith('@'):
            target_channel = f"#{target_channel}"

        payload = {
            "channel": target_channel,
            "text": fallback_text,
            "blocks": blocks,
        }

        # Create or update log entry
        log_entry, _ = NotificationLog.objects.get_or_create(
            idempotency_key=idempotency_key,
            defaults={
                'booking_reference': booking.booking_reference,
                'channel': 'slack',
                'event_type': event_type,
                'payload_preview': fallback_text,
            }
        )

        timeout = getattr(settings, 'SLACK_NOTIFICATION_TIMEOUT', 15)
        try:
            response = requests.post(webhook_url, json=payload, timeout=timeout)
            if response.status_code == 200:
                log_entry.status = 'sent'
                log_entry.sent_at = timezone.now()
                log_entry.last_error = ''
                log_entry.save(update_fields=['status', 'sent_at', 'last_error'])
                logger.info(f"Slack notification sent successfully for {booking.booking_reference}")
                return True, "Notification delivered to Slack."
            else:
                log_entry.status = 'failed'
                log_entry.attempts += 1
                log_entry.last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                log_entry.save(update_fields=['status', 'attempts', 'last_error'])
                logger.error(f"Slack webhook returned HTTP {response.status_code}: {response.text}")
                return False, f"Slack error HTTP {response.status_code}"
        except Exception as e:
            log_entry.status = 'failed'
            log_entry.attempts += 1
            log_entry.last_error = str(e)[:300]
            log_entry.save(update_fields=['status', 'attempts', 'last_error'])
            logger.exception("Failed to send Slack webhook notification")
            return False, f"Slack delivery failed: {str(e)}"

    @classmethod
    def send_test_notification(cls):
        """
        Admin action: sends a test notification to Slack to verify webhook connectivity.
        """
        webhook_url = getattr(settings, 'SLACK_WEBHOOK_URL', '').strip()
        if not webhook_url:
            return False, "SLACK_WEBHOOK_URL is not set in environment."

        payload = {
            "channel": getattr(settings, 'SLACK_CHANNEL', 'new-bookings'),
            "text": "🧪 *Renowned Homes System Test*\nSlack integration is active and operating normally.",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "🧪 Renowned Homes — Slack Integration Test",
                        "emoji": True
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "✅ *Connection verified!* Your incoming webhook is functioning properly. Incoming booking alerts will be posted here automatically."
                    }
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"Timestamp: {timezone.now().strftime('%Y-%m-%d %H:%M:%S UTC')}"
                        }
                    ]
                }
            ]
        }

        idempotency_key = f"slack_test_{int(timezone.now().timestamp())}"
        log_entry = NotificationLog.objects.create(
            booking_reference="TEST-000",
            channel='slack',
            event_type='test_webhook',
            idempotency_key=idempotency_key,
            payload_preview="Test Slack Webhook ping"
        )

        timeout = getattr(settings, 'SLACK_NOTIFICATION_TIMEOUT', 15)
        try:
            resp = requests.post(webhook_url, json=payload, timeout=timeout)
            if resp.status_code == 200:
                log_entry.status = 'sent'
                log_entry.sent_at = timezone.now()
                log_entry.save(update_fields=['status', 'sent_at'])
                return True, "Test message successfully sent to Slack channel!"
            else:
                log_entry.status = 'failed'
                log_entry.last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
                log_entry.save(update_fields=['status', 'last_error'])
                return False, f"Slack error HTTP {resp.status_code}"
        except Exception as e:
            log_entry.status = 'failed'
            log_entry.last_error = str(e)[:300]
            log_entry.save(update_fields=['status', 'last_error'])
            return False, f"Network error sending test: {str(e)}"


class EmailNotificationService:
    @classmethod
    def send_verification_email(cls, booking, code):
        """
        Sends the 6-digit confirmation code to the user's provided email.
        """
        subject = f"Your Renowned Homes Confirmation Code: {code}"
        
        plain_message = (
            f"Dear {booking.full_name},\n\n"
            f"Thank you for requesting a consultation with Renowned Homes.\n\n"
            f"Your 6-digit confirmation code is: {code}\n\n"
            f"Please enter this code on the website to confirm your appointment for:\n"
            f"Date: {booking.appointment_date.strftime('%A, %d %B %Y')}\n"
            f"Time: {booking.appointment_time.strftime('%H:%M')} ({booking.timezone})\n"
            f"Reference: {booking.booking_reference}\n\n"
            f"This code will expire in 15 minutes.\n\n"
            f"Warm regards,\n"
            f"Renowned Homes Advisory Team\n"
            f"77 Marsh Wall, London E14 9SH\n"
            f"Phone: 020 3278 5855\n"
            f"Website: https://www.renowned-homes.co.uk/"
        )

        html_message = f"""
        <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 580px; margin: 0 auto; background: #ffffff; border: 1px solid #d4ded8; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 14px rgba(27,55,41,0.08);">
            <div style="background: #1b3729; padding: 28px 32px; text-align: center; border-bottom: 3px solid #c4962a;">
                <h1 style="color: #ffffff; margin: 0; font-size: 24px; letter-spacing: 0.5px; font-weight: 600;">Renowned Homes</h1>
                <p style="color: #c4962a; margin: 6px 0 0 0; font-size: 13px; text-transform: uppercase; letter-spacing: 1.5px;">London & South East New Homes Specialists</p>
            </div>
            
            <div style="padding: 32px; background: #fdfbf7;">
                <h2 style="color: #1b3729; font-size: 20px; margin-top: 0; font-weight: 600;">Confirm Your Appointment Request</h2>
                <p style="color: #485f53; font-size: 15px; line-height: 1.6;">Dear {booking.full_name},</p>
                <p style="color: #485f53; font-size: 15px; line-height: 1.6;">Thank you for requesting a property consultation with our advisory team. To verify your email and confirm your booking, please enter the confirmation code below on our website:</p>
                
                <div style="background: #f8f4ee; border: 2px dashed #c4962a; border-radius: 10px; padding: 22px; text-align: center; margin: 26px 0;">
                    <div style="font-size: 12px; color: #485f53; text-transform: uppercase; letter-spacing: 1.2px; margin-bottom: 6px;">Your 6-Digit Confirmation Code</div>
                    <div style="font-size: 38px; font-weight: 700; color: #1b3729; letter-spacing: 8px; font-family: monospace;">{code}</div>
                    <div style="font-size: 13px; color: #616366; margin-top: 6px;">Valid for 15 minutes</div>
                </div>

                <div style="background: #ffffff; border: 1px solid #d4ded8; border-radius: 8px; padding: 16px 20px; margin-bottom: 24px;">
                    <div style="font-weight: 600; color: #1b3729; font-size: 14px; margin-bottom: 6px;">Requested Consultation Details:</div>
                    <div style="font-size: 14px; color: #485f53; line-height: 1.6;">
                        • <strong>Reference:</strong> {booking.booking_reference}<br>
                        • <strong>Date:</strong> {booking.appointment_date.strftime('%A, %d %B %Y')}<br>
                        • <strong>Time:</strong> {booking.appointment_time.strftime('%H:%M')} ({booking.timezone})<br>
                        • <strong>Service:</strong> {booking.enquiry_type}
                    </div>
                </div>

                <p style="color: #616366; font-size: 13px; line-height: 1.5; margin-bottom: 0;">
                    If you did not request this booking, you can safely ignore this email.
                </p>
            </div>

            <div style="background: #f8f4ee; padding: 20px 32px; border-top: 1px solid #d4ded8; font-size: 12px; color: #616366; text-align: center;">
                <p style="margin: 0 0 6px 0;">Renowned Homes • 77 Marsh Wall, London E14 9SH • 020 3278 5855</p>
                <p style="margin: 0;">Independent buyer-side advisory across London and the South East.</p>
            </div>
        </div>
        """

        idempotency_key = f"email_verify_{booking.booking_reference}_{code}"
        log_entry = NotificationLog.objects.create(
            booking_reference=booking.booking_reference,
            channel='email',
            event_type='verification_code',
            idempotency_key=idempotency_key,
            payload_preview=f"Code {code} sent to {booking.email}"
        )

        try:
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'info@renownedhomes.co.uk'),
                recipient_list=[booking.email],
                html_message=html_message,
                fail_silently=False
            )
            log_entry.status = 'sent'
            log_entry.sent_at = timezone.now()
            log_entry.save(update_fields=['status', 'sent_at'])
            return True, "Verification email sent."
        except Exception as e:
            log_entry.status = 'failed'
            log_entry.last_error = str(e)[:300]
            log_entry.save(update_fields=['status', 'last_error'])
            logger.exception("Failed to send verification email")
            return False, str(e)

    @classmethod
    def send_confirmation_receipt_email(cls, booking):
        """
        Sends final booking confirmation email once the code is entered and verified.
        """
        subject = f"Appointment Confirmed — Renowned Homes ({booking.booking_reference})"
        date_str = booking.appointment_date.strftime('%A, %d %B %Y')
        time_str = booking.appointment_time.strftime('%H:%M')

        plain_message = (
            f"Dear {booking.full_name},\n\n"
            f"Your appointment with Renowned Homes has been confirmed!\n\n"
            f"Booking Reference: {booking.booking_reference}\n"
            f"Date: {date_str}\n"
            f"Time: {time_str} ({booking.timezone})\n"
            f"Consultation: {booking.enquiry_type}\n\n"
            f"One of our London & South East property specialists will connect with you at your chosen time.\n"
            f"If you need to make changes or have questions beforehand, please contact us at 020 3278 5855 or reply to this email.\n\n"
            f"Warm regards,\n"
            f"The Renowned Homes Team\n"
            f"77 Marsh Wall, London E14 9SH\n"
        )

        html_message = f"""
        <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 580px; margin: 0 auto; background: #ffffff; border: 1px solid #d4ded8; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 14px rgba(27,55,41,0.08);">
            <div style="background: #1b3729; padding: 28px 32px; text-align: center; border-bottom: 3px solid #c4962a;">
                <h1 style="color: #ffffff; margin: 0; font-size: 24px; font-weight: 600;">Renowned Homes</h1>
                <p style="color: #c4962a; margin: 6px 0 0 0; font-size: 13px; text-transform: uppercase; letter-spacing: 1.5px;">London & South East New Homes Specialists</p>
            </div>
            
            <div style="padding: 32px; background: #fdfbf7;">
                <div style="display: inline-block; background: #ecfdf5; color: #1b3729; font-weight: 600; padding: 6px 14px; border-radius: 9999px; font-size: 13px; margin-bottom: 16px; border: 1px solid rgba(27,55,41,0.2);">
                    ✅ Appointment Confirmed
                </div>
                <h2 style="color: #1b3729; font-size: 22px; margin-top: 0; font-weight: 600;">We're looking forward to speaking with you!</h2>
                <p style="color: #485f53; font-size: 15px; line-height: 1.6;">Dear {booking.full_name},</p>
                <p style="color: #485f53; font-size: 15px; line-height: 1.6;">Your property consultation has been confirmed. Below are your booking details:</p>
                
                <div style="background: #f8f4ee; border: 1px solid #d4ded8; border-radius: 10px; padding: 22px; margin: 22px 0;">
                    <table style="width: 100%; border-collapse: collapse; font-size: 14px; color: #1b3729;">
                        <tr>
                            <td style="padding: 8px 0; color: #616366; width: 40%;">Booking Reference:</td>
                            <td style="padding: 8px 0; font-weight: 700; color: #1b3729;">{booking.booking_reference}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0; color: #616366;">Date:</td>
                            <td style="padding: 8px 0; font-weight: 600;">{date_str}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0; color: #616366;">Time:</td>
                            <td style="padding: 8px 0; font-weight: 600;">{time_str} ({booking.timezone})</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0; color: #616366;">Enquiry:</td>
                            <td style="padding: 8px 0; font-weight: 600;">{booking.enquiry_type}</td>
                        </tr>
                    </table>
                </div>

                <p style="color: #485f53; font-size: 14px; line-height: 1.6;">
                    Our independent advisers will walk you through prime developments, market pricing, reservation steps, and help coordinate any mortgage or solicitor introductions if desired.
                </p>
            </div>

            <div style="background: #f8f4ee; padding: 20px 32px; border-top: 1px solid #d4ded8; font-size: 12px; color: #616366; text-align: center;">
                <p style="margin: 0 0 6px 0;">Renowned Homes • 77 Marsh Wall, London E14 9SH • 020 3278 5855</p>
                <p style="margin: 0;">Independent buyer-side advisory across London and the South East.</p>
            </div>
        </div>
        """

        try:
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'info@renownedhomes.co.uk'),
                recipient_list=[booking.email],
                html_message=html_message,
                fail_silently=True
            )
            return True, "Confirmation receipt sent."
        except Exception as e:
            logger.exception("Failed to send confirmation receipt")
            return False, str(e)

