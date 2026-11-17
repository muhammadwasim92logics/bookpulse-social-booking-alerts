import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.bookings.models import AvailabilityRule, Booking
from apps.analytics.models import SocialAccount, SocialVideo, SocialMetricSnapshot, TrackedLink, Attribution


class Command(BaseCommand):
    help = "Seeds sample availability, tracked links, social metrics, and bookings."

    def handle(self, *args, **options):
        self.stdout.write("Seeding sample data...")

        # Availability rules for Monday (0) through Saturday (5)
        for day in range(6):
            rule, created = AvailabilityRule.objects.get_or_create(
                weekday=day,
                defaults={
                    'start_time': datetime.time(9, 0),
                    'end_time': datetime.time(18, 0),
                    'slot_duration_minutes': 45,
                    'buffer_minutes': 15,
                    'minimum_notice_hours': 2,
                    'max_advance_days': 60,
                    'is_active': True,
                }
            )
            if created:
                self.stdout.write(f"Created rule for {rule.get_weekday_display()}")

        # Sample tracked links
        links_data = [
            {
                'name': 'Example Instagram Profile Link',
                'platform': 'instagram',
                'campaign': 'example-campaign',
                'content_identifier': 'demo_ig_link',
                'original_video_url': 'https://example.com/instagram-demo',
                'clicks_count': 142,
                'bookings_count': 18,
            },
            {
                'name': 'Example TikTok Video',
                'platform': 'tiktok',
                'campaign': 'example-campaign',
                'content_identifier': 'demo_tt_video',
                'original_video_url': 'https://example.com/tiktok-demo',
                'clicks_count': 380,
                'bookings_count': 34,
            },
            {
                'name': 'Example YouTube Video',
                'platform': 'youtube',
                'campaign': 'example-campaign',
                'content_identifier': 'demo_yt_video',
                'original_video_url': 'https://example.com/youtube-demo',
                'clicks_count': 210,
                'bookings_count': 22,
            },
            {
                'name': 'Example Facebook Post',
                'platform': 'facebook',
                'campaign': 'example-campaign',
                'content_identifier': 'demo_fb_post',
                'original_video_url': 'https://example.com/facebook-demo',
                'clicks_count': 95,
                'bookings_count': 9,
            },
        ]

        for ld in links_data:
            link, _ = TrackedLink.objects.get_or_create(
                content_identifier=ld['content_identifier'],
                defaults=ld
            )

        # Sample account labels and metrics. No real platform connection is made.
        ig_acc, _ = SocialAccount.objects.get_or_create(
            platform='instagram',
            defaults={
                'platform_account_id': 'demo-instagram-account',
                'display_name': 'Demo Instagram Account',
                'connection_status': 'not_connected',
            }
        )

        yt_acc, _ = SocialAccount.objects.get_or_create(
            platform='youtube',
            defaults={
                'platform_account_id': 'demo-youtube-account',
                'display_name': 'Demo YouTube Account',
                'connection_status': 'not_connected',
            }
        )

        tt_acc, _ = SocialAccount.objects.get_or_create(
            platform='tiktok',
            defaults={
                'platform_account_id': 'demo-tiktok-account',
                'display_name': 'Demo TikTok Account',
                'connection_status': 'not_connected',
            }
        )

        videos_data = [
            {
                'account': ig_acc,
                'vid_id': 'ig_reel_101',
                'title': 'Example property tour video',
                'url': 'https://example.com/instagram-demo-video-1',
                'views': 45200,
                'likes': 3120,
                'comments': 148,
                'shares': 420,
                'attributed_visits': 380,
                'attributed_bookings': 26,
            },
            {
                'account': yt_acc,
                'vid_id': 'yt_vid_201',
                'title': 'Example buyer information video',
                'url': 'https://example.com/youtube-demo-video-1',
                'views': 28900,
                'likes': 1950,
                'comments': 94,
                'shares': 180,
                'attributed_visits': 210,
                'attributed_bookings': 19,
            },
            {
                'account': tt_acc,
                'vid_id': 'tt_vid_301',
                'title': 'Example first-time buyer video',
                'url': 'https://example.com/tiktok-demo-video-1',
                'views': 89400,
                'likes': 7600,
                'comments': 380,
                'shares': 910,
                'attributed_visits': 450,
                'attributed_bookings': 31,
            },
            {
                'account': ig_acc,
                'vid_id': 'ig_reel_102',
                'title': 'Example property investment video',
                'url': 'https://example.com/instagram-demo-video-2',
                'views': 33100,
                'likes': 2400,
                'comments': 112,
                'shares': 290,
                'attributed_visits': 190,
                'attributed_bookings': 14,
            },
        ]

        for vd in videos_data:
            vid, created = SocialVideo.objects.get_or_create(
                social_account=vd['account'],
                platform_video_id=vd['vid_id'],
                defaults={
                    'title_or_caption': vd['title'],
                    'video_url': vd['url'],
                    'views': vd['views'],
                    'likes': vd['likes'],
                    'comments': vd['comments'],
                    'shares': vd['shares'],
                    'attributed_visits': vd['attributed_visits'],
                    'attributed_bookings': vd['attributed_bookings'],
                    'published_at': timezone.now() - datetime.timedelta(days=14),
                }
            )
            if created:
                SocialMetricSnapshot.objects.create(
                    social_video=vid,
                    views=vd['views'],
                    likes=vd['likes'],
                    comments=vd['comments'],
                    shares=vd['shares'],
                )

        # Synthetic example bookings for local dashboard previews.
        sample_bookings = [
            {
                'ref': 'DEMO-BOOKING-001',
                'name': 'Demo Contact One',
                'email': 'demo-contact-01@example.com',
                'phone': '+1 202-555-0101',
                'social': '@demo_contact_one',
                'enquiry': 'Property investment enquiry',
                'date': timezone.now().date() + datetime.timedelta(days=2),
                'time': datetime.time(10, 0),
                'status': 'confirmed',
                'verified': True,
                'platform': 'instagram',
                'campaign': 'example-campaign',
                'notes': 'Synthetic example record for local development only.',
            },
            {
                'ref': 'DEMO-BOOKING-002',
                'name': 'Demo Contact Two',
                'email': 'demo-contact-02@example.com',
                'phone': '+1 202-555-0102',
                'social': None,
                'enquiry': 'First-time buyer consultation',
                'date': timezone.now().date() + datetime.timedelta(days=3),
                'time': datetime.time(14, 0),
                'status': 'confirmed',
                'verified': True,
                'platform': 'tiktok',
                'campaign': 'example-campaign',
                'notes': 'Synthetic example record for local development only.',
            }
        ]

        for sb in sample_bookings:
            if not Booking.objects.filter(booking_reference=sb['ref']).exists():
                attr = Attribution.objects.create(
                    anonymous_session_id=f"demo_sess_{sb['ref']}",
                    source=sb['platform'],
                    platform=sb['platform'],
                    campaign=sb['campaign'],
                    content='demo_content',
                )
                Booking.objects.create(
                    booking_reference=sb['ref'],
                    full_name=sb['name'],
                    email=sb['email'],
                    phone=sb['phone'],
                    social_username=sb['social'],
                    enquiry_type=sb['enquiry'],
                    appointment_date=sb['date'],
                    appointment_time=sb['time'],
                    timezone='Europe/London',
                    status=sb['status'],
                    is_email_verified=sb['verified'],
                    verified_at=timezone.now(),
                    internal_notes=sb['notes'],
                    attribution=attr,
                )

        self.stdout.write(self.style.SUCCESS("Successfully seeded synthetic demo data."))

