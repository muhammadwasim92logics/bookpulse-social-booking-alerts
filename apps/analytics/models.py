from django.db import models
from django.utils import timezone


class TrackedLink(models.Model):
    PLATFORM_CHOICES = [
        ('youtube', 'YouTube'),
        ('instagram', 'Instagram'),
        ('tiktok', 'TikTok'),
        ('facebook', 'Facebook'),
        ('other', 'Other / General'),
    ]

    name = models.CharField(max_length=150, help_text="Descriptive campaign or post title")
    platform = models.CharField(max_length=30, choices=PLATFORM_CHOICES, default='instagram')
    campaign = models.CharField(max_length=100, help_text="e.g. London-Penthouse-Launch")
    content_identifier = models.CharField(max_length=100, unique=True, help_text="UTM content ID, e.g. reel_001")
    destination_url = models.CharField(max_length=255, default="/#booking")
    original_video_url = models.URLField(blank=True, null=True, help_text="Link to source post/video")
    is_active = models.BooleanField(default=True)
    clicks_count = models.PositiveIntegerField(default=0)
    bookings_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.platform} - {self.content_identifier})"

    def generate_full_url(self, base_url=""):
        url = f"{base_url}{self.destination_url}"
        sep = "&" if "?" in url else "?"
        return (
            f"{url}{sep}utm_source={self.platform}"
            f"&utm_medium=organic_social"
            f"&utm_campaign={self.campaign}"
            f"&utm_content={self.content_identifier}"
            f"&platform={self.platform}"
        )


class Attribution(models.Model):
    anonymous_session_id = models.CharField(max_length=100, db_index=True)
    landing_page = models.CharField(max_length=255, blank=True, default='')
    source = models.CharField(max_length=100, default='direct')
    medium = models.CharField(max_length=100, blank=True, default='')
    campaign = models.CharField(max_length=100, blank=True, default='')
    content = models.CharField(max_length=100, blank=True, default='')
    term = models.CharField(max_length=100, blank=True, default='')
    platform = models.CharField(max_length=50, blank=True, default='')
    social_account = models.CharField(max_length=100, blank=True, default='')
    video_id = models.CharField(max_length=100, blank=True, default='')
    tracked_link = models.ForeignKey(
        TrackedLink, on_delete=models.SET_NULL, null=True, blank=True, related_name='attributions'
    )
    first_seen_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-first_seen_at']

    def __str__(self):
        return f"Attribution {self.source} / {self.platform or 'N/A'} ({self.campaign or 'direct'})"


class SocialAccount(models.Model):
    PLATFORM_CHOICES = [
        ('youtube', 'YouTube'),
        ('instagram', 'Instagram'),
        ('tiktok', 'TikTok'),
    ]
    STATUS_CHOICES = [
        ('connected', 'Connected'),
        ('not_connected', 'Not Connected'),
        ('expired', 'Token Expired'),
        ('error', 'Error / Attention Needed'),
    ]

    platform = models.CharField(max_length=30, choices=PLATFORM_CHOICES, unique=True)
    platform_account_id = models.CharField(max_length=100, blank=True, default='')
    display_name = models.CharField(max_length=150, blank=True, default='Renowned Homes')
    connection_status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='not_connected')
    last_sync_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.get_platform_display()} - {self.display_name} ({self.connection_status})"


class SocialVideo(models.Model):
    social_account = models.ForeignKey(SocialAccount, on_delete=models.CASCADE, related_name='videos')
    platform_video_id = models.CharField(max_length=100)
    title_or_caption = models.CharField(max_length=500)
    video_url = models.URLField(max_length=500)
    thumbnail_url = models.URLField(max_length=500, blank=True, null=True)
    published_at = models.DateTimeField(null=True, blank=True)
    is_available = models.BooleanField(default=True)
    views = models.BigIntegerField(default=0)
    likes = models.PositiveIntegerField(default=0)
    comments = models.PositiveIntegerField(default=0)
    shares = models.PositiveIntegerField(default=0)
    attributed_visits = models.PositiveIntegerField(default=0)
    attributed_bookings = models.PositiveIntegerField(default=0)
    last_synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('social_account', 'platform_video_id')
        ordering = ['-published_at']

    def __str__(self):
        return f"{self.social_account.platform.upper()} - {self.title_or_caption[:40]}"


class SocialMetricSnapshot(models.Model):
    social_video = models.ForeignKey(SocialVideo, on_delete=models.CASCADE, related_name='snapshots')
    collected_at = models.DateTimeField(default=timezone.now)
    views = models.BigIntegerField(null=True, blank=True)
    likes = models.PositiveIntegerField(null=True, blank=True)
    comments = models.PositiveIntegerField(null=True, blank=True)
    shares = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ['-collected_at']

    def __str__(self):
        return f"Snapshot {self.social_video.platform_video_id} @ {self.collected_at.strftime('%Y-%m-%d %H:%M')}"
