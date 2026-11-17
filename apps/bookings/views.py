import json
import uuid
import datetime
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db.models import F
from .models import Booking, AvailabilityRule
from .services import AvailabilityService, BookingService
from apps.analytics.models import TrackedLink, Attribution
from apps.notifications.services import EmailNotificationService


@ensure_csrf_cookie
def landing_page_view(request):
    """
    Renders the public Renowned Homes landing page and consultation booking portal.
    Captures attribution parameters and preserves them in session.
    """
    # Capture UTM / Tracking query params
    utm_source = request.GET.get('utm_source', '').strip()
    utm_medium = request.GET.get('utm_medium', '').strip()
    utm_campaign = request.GET.get('utm_campaign', '').strip()
    utm_content = request.GET.get('utm_content', '').strip()
    utm_term = request.GET.get('utm_term', '').strip()
    platform = request.GET.get('platform', utm_source).strip()
    video_id = request.GET.get('video_id', utm_content).strip()

    # Tracked link matching
    tracked_link = None
    if utm_content:
        tracked_link = TrackedLink.objects.filter(content_identifier=utm_content, is_active=True).first()
        if tracked_link:
            # Increment clicks atomically
            TrackedLink.objects.filter(id=tracked_link.id).update(clicks_count=F('clicks_count') + 1)

    # Initialize or preserve anonymous session ID
    if 'anon_id' not in request.session:
        request.session['anon_id'] = str(uuid.uuid4())[:18]

    # Store attribution in session if present
    if utm_source or platform or tracked_link:
        request.session['attribution'] = {
            'anonymous_session_id': request.session['anon_id'],
            'landing_page': request.path,
            'utm_source': utm_source or platform or 'direct',
            'utm_medium': utm_medium,
            'utm_campaign': utm_campaign,
            'utm_content': utm_content,
            'utm_term': utm_term,
            'platform': platform,
            'video_id': video_id,
            'tracked_link_id': tracked_link.id if tracked_link else None,
        }

    # Prepare default date for the booking selector (Tomorrow or next working day)
    now = timezone.localtime()
    tomorrow = (now + datetime.timedelta(days=1)).date()
    # If tomorrow is Sunday, suggest Monday
    if tomorrow.weekday() == 6:
        tomorrow = tomorrow + datetime.timedelta(days=1)

    initial_slots_data = AvailabilityService.get_available_slots_for_date(tomorrow)

    context = {
        'default_date': tomorrow.strftime('%Y-%m-%d'),
        'initial_slots': initial_slots_data.get('slots', []),
        'initial_is_open': initial_slots_data.get('is_open', True),
        'min_date': now.date().strftime('%Y-%m-%d'),
        'max_date': (now.date() + datetime.timedelta(days=60)).strftime('%Y-%m-%d'),
        'enquiry_choices': Booking.ENQUIRY_CHOICES,
        'attribution_info': request.session.get('attribution', {}),
    }
    return render(request, 'public/index.html', context)


@require_http_methods(["GET"])
def api_get_availability(request):
    """
    GET /api/availability/?date=YYYY-MM-DD
    Returns real-time slots availability for date.
    """
    date_str = request.GET.get('date', '').strip()
    if not date_str:
        return JsonResponse({'error': 'Missing date parameter.'}, status=400)

    try:
        data = AvailabilityService.get_available_slots_for_date(date_str)
        return JsonResponse(data)
    except Exception as e:
        return JsonResponse({'error': f"Failed to retrieve slots: {str(e)}"}, status=400)


@require_http_methods(["POST"])
def api_create_booking(request):
    """
    POST /api/bookings/
    Accepts booking submission, validates inputs, performs atomic slot reservation,
    generates 6-digit confirmation code, dispatches verification email, and returns reference.
    """
    try:
        if request.content_type == 'application/json':
            payload = json.loads(request.body.decode('utf-8'))
        else:
            payload = request.POST.dict()
    except Exception as e:
        return JsonResponse({'success': False, 'error': f"Invalid request body: {str(e)}"}, status=400)

    attribution_data = request.session.get('attribution')

    try:
        booking, code = BookingService.create_booking(payload, attribution_data=attribution_data)
        
        # Mask email for display security (e.g. j***e@example.com)
        parts = booking.email.split('@')
        name_part = parts[0]
        masked_name = name_part[0] + '***' + (name_part[-1] if len(name_part) > 1 else '')
        masked_email = f"{masked_name}@{parts[1]}"

        return JsonResponse({
            'success': True,
            'message': f"A 6-digit confirmation code has been dispatched to {masked_email}.",
            'booking_reference': booking.booking_reference,
            'email_masked': masked_email,
            'full_name': booking.full_name,
            'appointment_date': booking.appointment_date.strftime('%Y-%m-%d'),
            'appointment_date_formatted': booking.appointment_date.strftime('%A, %d %B %Y'),
            'appointment_time': booking.appointment_time.strftime('%H:%M'),
            'demo_code': code,  # Invaluable for testing & live preview without checking console
        })
    except ValueError as ve:
        return JsonResponse({'success': False, 'error': str(ve)}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': f"Server error: {str(e)}"}, status=500)


@require_http_methods(["POST"])
def api_verify_booking(request):
    """
    POST /api/bookings/verify/
    Verifies the 6-digit code entered by user in the pop-up modal.
    Confirms appointment and immediately fires Slack notification!
    """
    try:
        if request.content_type == 'application/json':
            payload = json.loads(request.body.decode('utf-8'))
        else:
            payload = request.POST.dict()
    except Exception:
        return JsonResponse({'success': False, 'error': 'Invalid request.'}, status=400)

    reference = payload.get('booking_reference', '').strip()
    code = payload.get('verification_code', '').strip()

    if not reference or not code:
        return JsonResponse({'success': False, 'error': 'Please provide the booking reference and 6-digit code.'}, status=400)

    success, message, booking = BookingService.verify_booking_code(reference, code)
    if not success:
        return JsonResponse({'success': False, 'error': message}, status=400)

    return JsonResponse({
        'success': True,
        'message': message,
        'booking': {
            'booking_reference': booking.booking_reference,
            'full_name': booking.full_name,
            'email': booking.email,
            'date_formatted': booking.appointment_date.strftime('%A, %d %B %Y'),
            'time_formatted': f"{booking.appointment_time.strftime('%H:%M')} ({booking.timezone})",
            'enquiry_type': booking.enquiry_type,
            'status': booking.status,
            'status_display': booking.get_status_display(),
        }
    })


@require_http_methods(["POST"])
def api_resend_code(request):
    """
    POST /api/bookings/resend-code/
    Resends code for a pending booking.
    """
    try:
        if request.content_type == 'application/json':
            payload = json.loads(request.body.decode('utf-8'))
        else:
            payload = request.POST.dict()
    except Exception:
        return JsonResponse({'success': False, 'error': 'Invalid request.'}, status=400)

    reference = payload.get('booking_reference', '').strip()
    booking = Booking.objects.filter(booking_reference=reference).first()
    if not booking:
        return JsonResponse({'success': False, 'error': 'Booking not found.'}, status=404)

    if booking.is_email_verified or booking.status == 'confirmed':
        return JsonResponse({'success': False, 'error': 'This booking is already confirmed!'}, status=400)

    new_code = booking.generate_verification_code()
    booking.save(update_fields=['verification_code', 'verification_code_expires_at'])

    EmailNotificationService.send_verification_email(booking, new_code)

    return JsonResponse({
        'success': True,
        'message': 'A fresh confirmation code has been sent to your email.',
        'demo_code': new_code,
    })


def booking_confirmed_view(request, reference):
    """
    Confirmation detail / receipt view for public visitor.
    """
    booking = get_object_or_404(Booking, booking_reference=reference)
    return render(request, 'public/confirmed.html', {'booking': booking})


def generate_calendar_ics(request, reference):
    """
    Generates an iCalendar (.ics) file so users can add the appointment to their calendar.
    """
    booking = get_object_or_404(Booking, booking_reference=reference)
    
    start_dt = datetime.datetime.combine(booking.appointment_date, booking.appointment_time)
    end_dt = start_dt + datetime.timedelta(minutes=45)
    
    dt_stamp = timezone.now().strftime('%Y%m%dT%H%M%SZ')
    dt_start = start_dt.strftime('%Y%m%dT%H%M%S')
    dt_end = end_dt.strftime('%Y%m%dT%H%M%S')

    ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Renowned Homes//Booking System//EN
CALSCALE:GREGORIAN
METHOD:PUBLISH
BEGIN:VEVENT
UID:{booking.booking_reference}@renownedhomes.co.uk
DTSTAMP:{dt_stamp}
DTSTART:{dt_start}
DTEND:{dt_end}
SUMMARY:Renowned Homes Property Consultation ({booking.booking_reference})
DESCRIPTION:Property consultation with Renowned Homes specialist.\\nEnquiry: {booking.enquiry_type}\\nContact: 020 3278 5855 / info@renownedhomes.co.uk
LOCATION:Renowned Homes, 77 Marsh Wall, London E14 9SH / Remote
STATUS:CONFIRMED
END:VEVENT
END:VCALENDAR"""

    response = HttpResponse(ics_content, content_type='text/calendar')
    response['Content-Disposition'] = f'attachment; filename="Renowned_Homes_{booking.booking_reference}.ics"'
    return response
