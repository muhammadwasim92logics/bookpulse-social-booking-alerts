from django.urls import path
from . import views

app_name = 'bookings'

urlpatterns = [
    path('', views.landing_page_view, name='landing'),
    path('book/', views.landing_page_view, name='book_alias'),
    path('book/confirmation/<str:reference>/', views.booking_confirmed_view, name='confirmation'),
    path('api/availability/', views.api_get_availability, name='api_availability'),
    path('api/bookings/', views.api_create_booking, name='api_create_booking'),
    path('api/bookings/verify/', views.api_verify_booking, name='api_verify_booking'),
    path('api/bookings/resend-code/', views.api_resend_code, name='api_resend_code'),
    path('api/bookings/<str:reference>/calendar.ics', views.generate_calendar_ics, name='calendar_ics'),
]

