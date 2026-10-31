from django.urls import path
from . import views

app_name = 'venues'

urlpatterns = [
    # Venue listing and details
    path('', views.venue_list, name='venue_list'),
    path('<int:pk>/', views.venue_detail, name='venue_detail'),
    
    # Venue management (for venue managers and admins)
    path('create/', views.venue_create, name='venue_create'),
    path('<int:pk>/edit/', views.venue_edit, name='venue_edit'),
    path('<int:pk>/delete/', views.venue_delete, name='venue_delete'),
    
    # Venue booking (for event managers and admins)
    path('<int:pk>/book/', views.venue_book, name='venue_book'),
    path('my-venues/', views.my_venues, name='my_venues'),
    path('my-bookings/', views.my_bookings, name='my_bookings'),
    path('booking/<int:pk>/cancel/', views.cancel_venue_booking, name='cancel_venue_booking'),
    
    # Booking management (for venue managers)
    path('<int:venue_pk>/bookings/', views.manage_bookings, name='manage_bookings'),
    path('booking/<int:pk>/update-status/', views.update_booking_status, name='update_booking_status'),
    path('booking/<int:pk>/details/', views.booking_details, name='booking_details'),
    path('booking/<int:pk>/invoice/', views.generate_invoice, name='generate_invoice'),
    path('booking/<int:pk>/review/', views.submit_review, name='submit_review'),
    
    # Comment actions
    path('comment/<int:comment_id>/like/', views.comment_like_toggle, name='comment_like_toggle'),
    path('comment/<int:comment_id>/delete/', views.comment_delete, name='comment_delete'),
]
