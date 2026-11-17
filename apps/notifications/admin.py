from django.contrib import admin
from .models import NotificationLog


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ('channel', 'event_type', 'booking_reference', 'status', 'attempts', 'sent_at', 'created_at')
    list_filter = ('channel', 'status', 'event_type')
    search_fields = ('booking_reference', 'idempotency_key', 'last_error')
