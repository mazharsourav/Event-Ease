from django.urls import path
from . import views

app_name = 'events'

urlpatterns = [
    # Event listing and details
    path('', views.event_list, name='event_list'),
    path('<int:pk>/', views.event_detail, name='event_detail'),
    
    # Event management (for event managers and admins)
    path('create/', views.event_create, name='event_create'),
    path('<int:pk>/edit/', views.event_edit, name='event_edit'),
    path('<int:pk>/delete/', views.event_delete, name='event_delete'),
    
    # Event booking
    path('<int:pk>/book/', views.event_book, name='event_book'),
    path('my-events/', views.my_events, name='my_events'),
    path('booking/<int:pk>/cancel/', views.cancel_booking, name='cancel_booking'),
    path('booking/<int:pk>/ticket/', views.download_ticket, name='download_ticket'),
    path('ticket/<str:reference>/', views.ticket_check, name='ticket_check'),
    
    # Event comments
    path('comment/<int:comment_id>/like/', views.comment_like_toggle, name='comment_like_toggle'),
    path('comment/<int:comment_id>/delete/', views.comment_delete, name='comment_delete'),
    
    # Dashboard detail pages
    path('dashboard/events-created/', views.events_created_detail, name='events_created_detail'),
    path('dashboard/events-live/', views.events_live_detail, name='events_live_detail'),
    path('dashboard/events-upcoming/', views.events_upcoming_detail, name='events_upcoming_detail'),
    path('dashboard/events-completed/', views.events_completed_detail, name='events_completed_detail'),
    path('dashboard/event-bookings/', views.event_bookings_detail, name='event_bookings_detail'),
    path('dashboard/revenue/', views.revenue_detail, name='revenue_detail'),
    path('dashboard/venue-bookings/', views.venue_bookings_detail, name='venue_bookings_detail'),
    path('dashboard/tickets-sold/', views.tickets_sold_detail, name='tickets_sold_detail'),
]
