from django.db import models


class NotificationLog(models.Model):
    CHANNEL_CHOICES = [
        ('slack', 'Slack Incoming Webhook'),
        ('email', 'Email Service'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Delivered Successfully'),
        ('failed', 'Delivery Failed'),
    ]

    booking_reference = models.CharField(max_length=50, blank=True, default='')
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, default='slack')
    event_type = models.CharField(max_length=50, default='new_booking')
    idempotency_key = models.CharField(max_length=150, unique=True, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    attempts = models.PositiveIntegerField(default=1)
    last_error = models.TextField(blank=True, default='')
    payload_preview = models.TextField(blank=True, default='')
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.channel.upper()}] {self.event_type} - {self.booking_reference or 'General'} ({self.status})"
