from django.contrib import admin
from .models import TrackedLink, Attribution, SocialAccount, SocialVideo, SocialMetricSnapshot


@admin.register(TrackedLink)
class TrackedLinkAdmin(admin.ModelAdmin):
    list_display = ('name', 'platform', 'campaign', 'content_identifier', 'clicks_count', 'bookings_count', 'is_active')
    list_filter = ('platform', 'is_active')
    search_fields = ('name', 'campaign', 'content_identifier')


@admin.register(Attribution)
class AttributionAdmin(admin.ModelAdmin):
    list_display = ('source', 'platform', 'campaign', 'content', 'first_seen_at')
    list_filter = ('platform', 'source')


@admin.register(SocialAccount)
class SocialAccountAdmin(admin.ModelAdmin):
    list_display = ('platform', 'display_name', 'connection_status', 'last_sync_at')


@admin.register(SocialVideo)
class SocialVideoAdmin(admin.ModelAdmin):
    list_display = ('title_or_caption', 'social_account', 'views', 'likes', 'comments', 'shares', 'attributed_bookings')
    list_filter = ('social_account__platform',)
