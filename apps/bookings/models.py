import random
import string
from datetime import timedelta
from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()


class AvailabilityRule(models.Model):
    WEEKDAY_CHOICES = [
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    ]

    weekday = models.IntegerField(choices=WEEKDAY_CHOICES, unique=True)
    start_time = models.TimeField(default='09:00:00')
    end_time = models.TimeField(default='18:00:00')
    slot_duration_minutes = models.PositiveIntegerField(default=45)
    buffer_minutes = models.PositiveIntegerField(default=15)
    minimum_notice_hours = models.PositiveIntegerField(default=2)
    max_advance_days = models.PositiveIntegerField(default=60)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['weekday']

    def __str__(self):
        status = "Active" if self.is_active else "Off"
        return f"{self.get_weekday_display()} ({self.start_time.strftime('%H:%M')} - {self.end_time.strftime('%H:%M')}) [{status}]"


class AvailabilityException(models.Model):
    date = models.DateField(unique=True)
    is_blocked = models.BooleanField(default=True, help_text="True = entire day is blocked / holiday")
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    reason = models.CharField(max_length=200, default='Holiday / Closed')

    class Meta:
        ordering = ['date']

    def __str__(self):
        return f"Exception on {self.date}: {self.reason} ({'Blocked' if self.is_blocked else 'Partial'})"


class Booking(models.Model):
    STATUS_CHOICES = [
        ('pending_verification', 'Awaiting Email Verification'),
        ('pending', 'Pending Staff Review'),
        ('confirmed', 'Confirmed Appointment'),
        ('rescheduled', 'Rescheduled'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('no_show', 'No-Show'),
    ]

    ENQUIRY_CHOICES = [
        ('New-build home purchase', 'New-build home purchase'),
        ('First-time buyer consultation', 'First-time buyer consultation'),
        ('Property investment enquiry', 'Property investment enquiry'),
        ('Family move / upsizing', 'Family move / upsizing'),
        ('International buyer enquiry', 'International buyer enquiry'),
        ('Property viewing / development enquiry', 'Property viewing / development enquiry'),
        ('Other', 'Other guidance'),
    ]

    booking_reference = models.CharField(max_length=30, unique=True, db_index=True)
    full_name = models.CharField(max_length=150)
    email = models.EmailField(db_index=True)
    phone = models.CharField(max_length=40)
    social_username = models.CharField(max_length=100, blank=True, null=True, help_text="Instagram, TikTok or other handle")
    enquiry_type = models.CharField(max_length=100, choices=ENQUIRY_CHOICES, default='New-build home purchase')
    message = models.TextField(blank=True, default='')

    appointment_date = models.DateField(db_index=True)
    appointment_time = models.TimeField()
    timezone = models.CharField(max_length=60, default='Europe/London')

    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending_verification')

    # Verification Code Workflow
    verification_code = models.CharField(max_length=6, blank=True, default='')
    verification_code_expires_at = models.DateTimeField(null=True, blank=True)
    is_email_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)

    # Consents
    consent_to_contact = models.BooleanField(default=True)
    marketing_consent = models.BooleanField(default=False)

    # Attribution connection
    attribution = models.ForeignKey(
        'analytics.Attribution',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bookings'
    )

    # Staff Admin
    internal_notes = models.TextField(blank=True, default='')
    assigned_staff = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_bookings')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['appointment_date', 'appointment_time']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.booking_reference} - {self.full_name} ({self.status})"

    @classmethod
    def generate_unique_reference(cls):
        year = timezone.now().year
        while True:
            rand_digits = "".join(random.choices(string.digits, k=6))
            ref = f"RH-{year}-{rand_digits}"
            if not cls.objects.filter(booking_reference=ref).exists():
                return ref

    def generate_verification_code(self):
        code = "".join(random.choices(string.digits, k=6))
        self.verification_code = code
        self.verification_code_expires_at = timezone.now() + timedelta(minutes=15)
        return code

    def verify_code(self, submitted_code):
        if not self.verification_code or not submitted_code:
            return False, "No verification code exists for this booking."
        
        if str(submitted_code).strip() != self.verification_code.strip():
            return False, "The confirmation code entered is incorrect. Please try again."

        if self.verification_code_expires_at and timezone.now() > self.verification_code_expires_at:
            return False, "This confirmation code has expired. Please request a new code."

        self.is_email_verified = True
        self.verified_at = timezone.now()
        self.status = 'confirmed'
        self.save(update_fields=['is_email_verified', 'verified_at', 'status', 'updated_at'])
        return True, "Your appointment has been successfully verified and confirmed!"
