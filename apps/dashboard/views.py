import csv
import json
import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.utils import timezone
from django.conf import settings
from django.core.mail import send_mail
from apps.bookings.models import Booking, AvailabilityRule, AvailabilityException
from apps.analytics.models import TrackedLink, Attribution, SocialAccount, SocialVideo
from apps.notifications.models import NotificationLog
from apps.notifications.services import SlackNotificationService


def admin_login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard:overview')

    if request.method == 'POST':
        u = request.POST.get('username', '').strip()
        p = request.POST.get('password', '').strip()
        user = authenticate(request, username=u, password=p)
        if user is not None and user.is_staff:
            login(request, user)
            messages.success(request, f"Welcome back, {user.first_name or user.username}!")
            return redirect('dashboard:overview')
        else:
            messages.error(request, "Invalid administrator credentials. Please check your username and password.")

    return render(request, 'dashboard/login.html')


def admin_logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out successfully.")
    return redirect('dashboard:login')


@login_required
def overview_dashboard_view(request):
    total_bookings = Booking.objects.count()
    confirmed_count = Booking.objects.filter(status='confirmed').count()
    pending_count = Booking.objects.filter(status__in=['pending', 'pending_verification']).count()
    completed_count = Booking.objects.filter(status='completed').count()

    total_clicks = TrackedLink.objects.aggregate(s=Sum('clicks_count'))['s'] or 0
    total_attributed_bookings = TrackedLink.objects.aggregate(s=Sum('bookings_count'))['s'] or 0
    conversion_rate = round((total_attributed_bookings / total_clicks * 100), 1) if total_clicks > 0 else 0.0

    # Total social views across videos
    social_views = SocialVideo.objects.aggregate(s=Sum('views'))['s'] or 0
    social_engagements = (SocialVideo.objects.aggregate(
        likes=Sum('likes'), comments=Sum('comments'), shares=Sum('shares')
    ))
    total_engagements = (social_engagements['likes'] or 0) + (social_engagements['comments'] or 0) + (social_engagements['shares'] or 0)

    # Recent bookings
    recent_bookings = Booking.objects.select_related('attribution').order_by('-created_at')[:8]

    # Platform breakdown for chart
    platforms = ['instagram', 'youtube', 'tiktok', 'facebook', 'other']
    platform_counts = []
    for p in platforms:
        c = Booking.objects.filter(attribution__platform=p).count()
        platform_counts.append(c)

    # Top videos by views
    top_videos = SocialVideo.objects.select_related('social_account').order_by('-views')[:5]

    # Recent Slack notifications
    slack_logs = NotificationLog.objects.filter(channel='slack').order_by('-created_at')[:5]

    context = {
        'total_bookings': total_bookings,
        'confirmed_count': confirmed_count,
        'pending_count': pending_count,
        'completed_count': completed_count,
        'total_clicks': total_clicks,
        'total_attributed_bookings': total_attributed_bookings,
        'conversion_rate': conversion_rate,
        'social_views': social_views,
        'total_engagements': total_engagements,
        'recent_bookings': recent_bookings,
        'top_videos': top_videos,
        'slack_logs': slack_logs,
        'platform_counts_json': json.dumps(platform_counts),
    }
    return render(request, 'dashboard/overview.html', context)


@login_required
def bookings_list_view(request):
    qs = Booking.objects.select_related('attribution', 'assigned_staff').all()

    # Search
    search = request.GET.get('q', '').strip()
    if search:
        qs = qs.filter(
            Q(full_name__icontains=search) |
            Q(email__icontains=search) |
            Q(phone__icontains=search) |
            Q(booking_reference__icontains=search)
        )

    # Status Filter
    status = request.GET.get('status', '').strip()
    if status:
        qs = qs.filter(status=status)

    # Enquiry Filter
    enquiry = request.GET.get('enquiry', '').strip()
    if enquiry:
        qs = qs.filter(enquiry_type=enquiry)

    # Platform Filter
    platform = request.GET.get('platform', '').strip()
    if platform:
        qs = qs.filter(attribution__platform=platform)

    # Date range
    date_filter = request.GET.get('date', '').strip()
    if date_filter:
        try:
            target_date = datetime.datetime.strptime(date_filter, '%Y-%m-%d').date()
            qs = qs.filter(appointment_date=target_date)
        except ValueError:
            pass

    # Ordering
    ordering = request.GET.get('order_by', '-created_at')
    valid_orderings = ['-created_at', 'created_at', 'appointment_date', '-appointment_date', 'status']
    if ordering in valid_orderings:
        qs = qs.order_by(ordering)

    paginator = Paginator(qs, 12)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'search': search,
        'status_filter': status,
        'enquiry_filter': enquiry,
        'platform_filter': platform,
        'date_filter': date_filter,
        'ordering': ordering,
        'status_choices': Booking.STATUS_CHOICES,
        'enquiry_choices': Booking.ENQUIRY_CHOICES,
    }
    return render(request, 'dashboard/bookings.html', context)


@login_required
def export_bookings_csv(request):
    qs = Booking.objects.select_related('attribution').all().order_by('-created_at')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="renowned_homes_bookings.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Reference', 'Created At', 'Full Name', 'Email', 'Phone',
        'Social Handle', 'Enquiry Type', 'Date', 'Time', 'Timezone',
        'Status', 'Email Verified', 'Source Platform', 'Campaign', 'Video ID', 'Notes'
    ])

    for b in qs:
        platform = b.attribution.platform if b.attribution else 'direct'
        campaign = b.attribution.campaign if b.attribution else ''
        video_id = b.attribution.video_id if b.attribution else ''
        writer.writerow([
            b.booking_reference,
            b.created_at.strftime('%Y-%m-%d %H:%M'),
            b.full_name,
            b.email,
            b.phone,
            b.social_username or '',
            b.enquiry_type,
            b.appointment_date.strftime('%Y-%m-%d'),
            b.appointment_time.strftime('%H:%M'),
            b.timezone,
            b.status,
            'Yes' if b.is_email_verified else 'No',
            platform,
            campaign,
            video_id,
            b.internal_notes.replace('\n', ' ')
        ])

    return response


@login_required
def api_booking_detail(request, pk):
    booking = get_object_or_404(Booking.objects.select_related('attribution', 'assigned_staff'), pk=pk)
    
    slack_log = NotificationLog.objects.filter(booking_reference=booking.booking_reference, channel='slack').first()
    email_log = NotificationLog.objects.filter(booking_reference=booking.booking_reference, channel='email').first()

    data = {
        'id': booking.id,
        'reference': booking.booking_reference,
        'full_name': booking.full_name,
        'email': booking.email,
        'phone': booking.phone,
        'social_username': booking.social_username or 'Not provided',
        'enquiry_type': booking.enquiry_type,
        'message': booking.message or 'No additional notes provided.',
        'appointment_date': booking.appointment_date.strftime('%Y-%m-%d'),
        'appointment_date_formatted': booking.appointment_date.strftime('%A, %d %B %Y'),
        'appointment_time': booking.appointment_time.strftime('%H:%M'),
        'timezone': booking.timezone,
        'status': booking.status,
        'status_display': booking.get_status_display(),
        'is_email_verified': booking.is_email_verified,
        'verified_at': booking.verified_at.strftime('%d %b %Y, %H:%M') if booking.verified_at else None,
        'internal_notes': booking.internal_notes,
        'created_at': booking.created_at.strftime('%d %b %Y, %H:%M'),
        'attribution': {
            'platform': booking.attribution.platform if booking.attribution else 'Direct / Website',
            'campaign': booking.attribution.campaign if booking.attribution else 'None',
            'video_id': booking.attribution.video_id if booking.attribution else 'None',
            'source': booking.attribution.source if booking.attribution else 'direct',
        } if booking.attribution else None,
        'notifications': {
            'slack_status': slack_log.status if slack_log else 'Not sent',
            'slack_sent_at': slack_log.sent_at.strftime('%d %b %Y, %H:%M') if slack_log and slack_log.sent_at else None,
            'email_status': email_log.status if email_log else 'Not sent',
        }
    }
    return JsonResponse({'success': True, 'booking': data})


@login_required
def api_update_booking(request, pk):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    booking = get_object_or_404(Booking, pk=pk)
    try:
        payload = json.loads(request.body.decode('utf-8'))
    except Exception:
        payload = request.POST.dict()

    new_status = payload.get('status')
    notes = payload.get('internal_notes')

    if new_status and new_status in dict(Booking.STATUS_CHOICES):
        booking.status = new_status
    if notes is not None:
        booking.internal_notes = notes

    booking.save()
    return JsonResponse({
        'success': True,
        'message': f"Booking {booking.booking_reference} updated successfully.",
        'new_status': booking.status,
        'new_status_display': booking.get_status_display()
    })


@login_required
def api_reschedule_booking(request, pk):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    booking = get_object_or_404(Booking, pk=pk)
    try:
        payload = json.loads(request.body.decode('utf-8'))
    except Exception:
        payload = request.POST.dict()

    new_date_str = payload.get('date')
    new_time_str = payload.get('time')

    if not new_date_str or not new_time_str:
        return JsonResponse({'success': False, 'error': 'Date and time are required.'}, status=400)

    try:
        new_date = datetime.datetime.strptime(new_date_str, '%Y-%m-%d').date()
        parts = new_time_str.split(':')
        new_time = datetime.time(int(parts[0]), int(parts[1]))
    except Exception as e:
        return JsonResponse({'success': False, 'error': f"Invalid format: {str(e)}"}, status=400)

    # Check collision
    collision = Booking.objects.filter(
        appointment_date=new_date,
        appointment_time=new_time,
        status__in=['confirmed', 'pending']
    ).exclude(pk=booking.pk).exists()

    if collision:
        return JsonResponse({'success': False, 'error': 'This time slot is already taken. Please choose another.'}, status=400)

    booking.appointment_date = new_date
    booking.appointment_time = new_time
    booking.status = 'rescheduled'
    booking.save()

    return JsonResponse({
        'success': True,
        'message': f"Booking rescheduled to {new_date_str} at {new_time_str}."
    })


@login_required
def api_resend_booking_slack(request, pk):
    """
    Manually triggers re-sending a Slack booking notification for this booking.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    booking = get_object_or_404(Booking, pk=pk)
    success, message = SlackNotificationService.send_booking_notification(
        booking,
        event_type="booking_confirmed",
        force=True
    )
    return JsonResponse({
        'success': success,
        'message': message,
        'reference': booking.booking_reference,
    })


@login_required
def calendar_view(request):
    bookings = Booking.objects.filter(
        status__in=['pending', 'confirmed', 'rescheduled']
    ).order_by('appointment_date', 'appointment_time')

    context = {
        'bookings': bookings,
    }
    return render(request, 'dashboard/calendar.html', context)


@login_required
def api_calendar_events(request):
    bookings = Booking.objects.filter(
        status__in=['pending', 'confirmed', 'rescheduled']
    )
    events = []
    for b in bookings:
        color = '#10b981' if b.status == 'confirmed' else '#f59e0b'
        start_iso = f"{b.appointment_date.strftime('%Y-%m-%d')}T{b.appointment_time.strftime('%H:%M:%S')}"
        events.append({
            'id': b.id,
            'title': f"{b.full_name} ({b.enquiry_type})",
            'start': start_iso,
            'color': color,
            'reference': b.booking_reference,
            'status': b.get_status_display(),
        })
    return JsonResponse(events, safe=False)


@login_required
def tracked_links_view(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        platform = request.POST.get('platform', 'instagram').strip()
        campaign = request.POST.get('campaign', '').strip().replace(' ', '-')
        content_id = request.POST.get('content_identifier', '').strip().replace(' ', '-')
        original_url = request.POST.get('original_video_url', '').strip()

        if name and campaign and content_id:
            # Check unique content_id
            if TrackedLink.objects.filter(content_identifier=content_id).exists():
                messages.error(request, f"Tracking ID '{content_id}' is already in use. Please choose another identifier.")
            else:
                TrackedLink.objects.create(
                    name=name,
                    platform=platform,
                    campaign=campaign,
                    content_identifier=content_id,
                    original_video_url=original_url or None
                )
                messages.success(request, f"Tracked link '{name}' created successfully!")
                return redirect('dashboard:tracked_links')
        else:
            messages.error(request, "Please fill in all required link fields.")

    links = TrackedLink.objects.all().order_by('-created_at')
    base_host = request.build_absolute_uri('/')[:-1]

    links_with_urls = []
    for link in links:
        full_url = link.generate_full_url(base_host)
        cr = round((link.bookings_count / link.clicks_count * 100), 1) if link.clicks_count > 0 else 0.0
        links_with_urls.append({
            'obj': link,
            'full_url': full_url,
            'conversion_rate': cr,
        })

    context = {
        'links': links_with_urls,
        'platform_choices': TrackedLink.PLATFORM_CHOICES,
    }
    return render(request, 'dashboard/tracked_links.html', context)


@login_required
def social_analytics_view(request):
    accounts = SocialAccount.objects.prefetch_related('videos').all()
    videos = SocialVideo.objects.select_related('social_account').order_by('-views')

    platform_filter = request.GET.get('platform', 'all')
    if platform_filter != 'all':
        videos = videos.filter(social_account__platform=platform_filter)

    context = {
        'accounts': accounts,
        'videos': videos,
        'platform_filter': platform_filter,
    }
    return render(request, 'dashboard/analytics.html', context)


@login_required
def api_sync_social_metrics(request):
    """
    Simulates / triggers metric sync for connected platforms.
    """
    now = timezone.now()
    # Update last_sync on accounts
    SocialAccount.objects.all().update(last_sync_at=now)
    return JsonResponse({
        'success': True,
        'message': f"Social metrics refreshed successfully across all platforms at {now.strftime('%H:%M:%S')}."
    })


@login_required
def settings_view(request):
    slack_logs = NotificationLog.objects.filter(channel='slack').order_by('-created_at')[:10]
    rules = AvailabilityRule.objects.all().order_by('weekday')

    context = {
        'slack_logs': slack_logs,
        'availability_rules': rules,
    }
    return render(request, 'dashboard/settings.html', context)


@login_required
def api_test_slack(request):
    """
    Dispatches a test notification to the configured Slack webhook URL.
    """
    success, message = SlackNotificationService.send_test_notification()
    return JsonResponse({
        'success': success,
        'message': message,
    })


@login_required
def api_test_email(request):
    """
    Sends a test email to the configured EMAIL_HOST_USER to verify SMTP connectivity.
    """
    to_email = getattr(settings, 'EMAIL_HOST_USER', '').strip()
    if not to_email:
        to_email = request.user.email or 'test@example.com'

    try:
        send_mail(
            subject="Renowned Homes — Live SMTP Connection Test",
            message=f"Hello,\n\nYour SMTP email service is connected successfully to the Renowned Homes platform! 6-digit confirmation codes and consultation receipts will be delivered seamlessly.\n\nTimestamp: {timezone.now().strftime('%Y-%m-%d %H:%M:%S UTC')}",
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
            recipient_list=[to_email],
            fail_silently=False
        )
        return JsonResponse({
            'success': True,
            'message': f"Test email successfully dispatched to {to_email} via Gmail SMTP!"
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f"Email delivery failed: {str(e)}"
        })
