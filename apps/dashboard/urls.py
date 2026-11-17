from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.overview_dashboard_view, name='overview'),
    path('login/', views.admin_login_view, name='login'),
    path('logout/', views.admin_logout_view, name='logout'),
    
    path('bookings/', views.bookings_list_view, name='bookings'),
    path('bookings/export-csv/', views.export_bookings_csv, name='export_csv'),
    path('bookings/<int:pk>/detail/', views.api_booking_detail, name='api_booking_detail'),
    path('bookings/<int:pk>/update/', views.api_update_booking, name='api_update_booking'),
    path('bookings/<int:pk>/reschedule/', views.api_reschedule_booking, name='api_reschedule_booking'),
    path('bookings/<int:pk>/resend-slack/', views.api_resend_booking_slack, name='api_resend_slack'),
    
    path('calendar/', views.calendar_view, name='calendar'),
    path('calendar/events/', views.api_calendar_events, name='api_calendar_events'),
    
    path('tracked-links/', views.tracked_links_view, name='tracked_links'),
    path('analytics/', views.social_analytics_view, name='analytics'),
    path('analytics/sync/', views.api_sync_social_metrics, name='api_sync_social'),
    
    path('settings/', views.settings_view, name='settings'),
    path('settings/test-slack/', views.api_test_slack, name='api_test_slack'),
    path('settings/test-email/', views.api_test_email, name='api_test_email'),
]

