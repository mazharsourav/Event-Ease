"""
Notification helpers for automatic notification creation
"""
from django.contrib.auth.models import User
from .models import Notification

def create_event_booking_notification(user, event_name, booking_id):
    """Create notification for event booking confirmation"""
    return Notification.create_notification(
        user=user,
        title='Event Booking Confirmed',
        message=f'Your booking for "{event_name}" has been confirmed. Booking ID: #{booking_id}',
        notification_type='event_booking_confirm',
        booking_id=booking_id
    )

def create_venue_booking_notification(user, venue_name, status, booking_id=None):
    """Create notification for venue booking status update"""
    status_messages = {
        'approved': f'Your venue booking request for "{venue_name}" has been approved.',
        'rejected': f'Your venue booking request for "{venue_name}" has been rejected.',
        'pending': f'Your venue booking request for "{venue_name}" is under review.',
        'confirmed': f'Your venue booking for "{venue_name}" has been confirmed.',
    }
    
    return Notification.create_notification(
        user=user,
        title='Venue Booking Status Update',
        message=status_messages.get(status, f'Your venue booking status for "{venue_name}" has been updated.'),
        notification_type='venue_booking_status',
        booking_id=booking_id
    )

def create_upcoming_event_notification(user, event_name, event_time):
    """Create notification for upcoming event reminder"""
    return Notification.create_notification(
        user=user,
        title='Upcoming Event Reminder',
        message=f'Don\'t forget! "{event_name}" is happening {event_time}.',
        notification_type='upcoming_event'
    )

def create_venue_booking_request_notification(venue_manager, venue_name, requester_name):
    """Create notification for venue managers about new booking requests"""
    return Notification.create_notification(
        user=venue_manager,
        title='New Venue Booking Request',
        message=f'A new booking request has been received for "{venue_name}" from {requester_name}.',
        notification_type='venue_booking_request'
    )

def create_event_registration_notification(event_manager, event_name, user_name, total_registrations):
    """Create notification for event managers about new registrations"""
    return Notification.create_notification(
        user=event_manager,
        title='New Event Registration',
        message=f'{user_name} has registered for "{event_name}". Total registrations: {total_registrations}',
        notification_type='event_registration'
    )

def notify_venue_managers(venue_id, venue_name, requester_name):
    """Notify all venue managers about a new booking request"""
    # This would need to be implemented based on your user role system
    # For now, we'll use a simple approach
    venue_managers = User.objects.filter(username__icontains='venue')  # Simplified
    
    for manager in venue_managers:
        create_venue_booking_request_notification(manager, venue_name, requester_name)

def notify_event_managers(event_id, event_name, user_name):
    """Notify all event managers about a new registration"""
    # This would need to be implemented based on your user role system
    # For now, we'll use a simple approach
    event_managers = User.objects.filter(username__icontains='event')  # Simplified
    
    # Get total registrations (this would need to be implemented based on your model)
    total_registrations = 1  # Placeholder
    
    for manager in event_managers:
        create_event_registration_notification(manager, event_name, user_name, total_registrations)
