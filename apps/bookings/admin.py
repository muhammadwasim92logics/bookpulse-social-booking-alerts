from django.contrib import admin
from .models import Booking, AvailabilityRule, AvailabilityException


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('booking_reference', 'full_name', 'email', 'phone', 'appointment_date', 'appointment_time', 'status', 'is_email_verified', 'created_at')
    list_filter = ('status', 'is_email_verified', 'appointment_date', 'enquiry_type')
    search_fields = ('booking_reference', 'full_name', 'email', 'phone', 'social_username')
    readonly_fields = ('booking_reference', 'created_at', 'updated_at', 'verified_at')


@admin.register(AvailabilityRule)
class AvailabilityRuleAdmin(admin.ModelAdmin):
    list_display = ('get_weekday_display', 'start_time', 'end_time', 'slot_duration_minutes', 'buffer_minutes', 'is_active')
    list_filter = ('is_active',)


@admin.register(AvailabilityException)
class AvailabilityExceptionAdmin(admin.ModelAdmin):
    list_display = ('date', 'reason', 'is_blocked', 'start_time', 'end_time')
    list_filter = ('is_blocked',)
