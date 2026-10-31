"""
Django signals for automatic notification creation
"""
import logging

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta

from apps.venues.models import VenueBooking
from apps.events.models import EventBooking, Event
from .emails import send_event_booking_confirmation, send_venue_booking_decision
from .models import Notification
from .helpers import (
    create_venue_booking_notification,
    create_event_booking_notification,
    create_upcoming_event_notification,
    create_venue_booking_request_notification,
    create_event_registration_notification
)

logger = logging.getLogger(__name__)

# Store original status to detect changes
venue_booking_original_status = {}

@receiver(pre_save, sender=VenueBooking)
def store_original_venue_booking_status(sender, instance, **kwargs):
    """Store the original status before save to detect changes"""
    if instance.pk:
        try:
            original = VenueBooking.objects.get(pk=instance.pk)
            venue_booking_original_status[instance.pk] = original.status
        except VenueBooking.DoesNotExist:
            venue_booking_original_status[instance.pk] = None
    else:
        venue_booking_original_status[instance.pk] = None

@receiver(post_save, sender=VenueBooking)
def venue_booking_status_notification(sender, instance, created, **kwargs):
    """Send notification when venue booking status changes"""
    if created:
        # Notify venue manager about new booking request
        create_venue_booking_request_notification(
            venue_manager=instance.venue.manager,
            venue_name=instance.venue.name,
            requester_name=instance.user.get_full_name() or instance.user.username
        )
        logger.info(f"Created venue booking request notification for manager: {instance.venue.manager.username}")
    else:
        # Check if status changed
        original_status = venue_booking_original_status.get(instance.pk)
        if original_status and original_status != instance.status:
            if instance.status in ['confirmed', 'rejected']:
                # Notify the user about status change
                create_venue_booking_notification(
                    user=instance.user,
                    venue_name=instance.venue.name,
                    status=instance.status,
                    booking_id=instance.id
                )
                send_venue_booking_decision(instance)
                logger.info(f"Created venue booking status notification for user: {instance.user.username} - Status: {instance.status}")
        
        # Clean up the stored status
        if instance.pk in venue_booking_original_status:
            del venue_booking_original_status[instance.pk]

# Store original status for event bookings too
event_booking_original_status = {}

@receiver(pre_save, sender=EventBooking)
def store_original_event_booking_status(sender, instance, **kwargs):
    """Store the original status before save to detect changes"""
    if instance.pk:
        try:
            original = EventBooking.objects.get(pk=instance.pk)
            event_booking_original_status[instance.pk] = original.status
        except EventBooking.DoesNotExist:
            event_booking_original_status[instance.pk] = None
    else:
        event_booking_original_status[instance.pk] = None

@receiver(post_save, sender=EventBooking)
def event_booking_notification(sender, instance, created, **kwargs):
    """Send notification when event booking is created or status changes"""
    if created:
        # Notify event organizer about new registration
        create_event_registration_notification(
            event_manager=instance.event.organizer,
            event_name=instance.event.title,
            user_name=instance.user.get_full_name() or instance.user.username,
            total_registrations=instance.event.current_attendees
        )
        logger.info(f"Created event registration notification for organizer: {instance.event.organizer.username}")
        
        # If the booking is automatically confirmed, also notify the user
        if instance.status == 'confirmed':
            create_event_booking_notification(
                user=instance.user,
                event_name=instance.event.title,
                booking_id=instance.id
            )
            send_event_booking_confirmation(instance)
            logger.info(f"Created event booking confirmation for user: {instance.user.username}")
    else:
        # Check if status changed to confirmed
        original_status = event_booking_original_status.get(instance.pk)
        if original_status and original_status != instance.status and instance.status == 'confirmed':
            create_event_booking_notification(
                user=instance.user,
                event_name=instance.event.title,
                booking_id=instance.id
            )
            send_event_booking_confirmation(instance)
            logger.info(f"Created event booking confirmation for user: {instance.user.username} - Status changed to confirmed")
        
        # Clean up the stored status
        if instance.pk in event_booking_original_status:
            del event_booking_original_status[instance.pk]

def send_upcoming_event_notifications():
    """
    Function to send notifications for upcoming events
    This should be called by a scheduled task (like Celery or cron job)
    """
    logger.info("Checking for upcoming events...")
    now = timezone.now()
    
    # Get events starting in next 24 hours (flexible window)
    start_window = now + timedelta(hours=20)  # 20 hours from now
    end_window = now + timedelta(hours=28)    # 28 hours from now
    
    logger.info(f"Looking for events between {start_window} and {end_window}")
    
    upcoming_events = Event.objects.filter(
        start_date__gte=start_window,
        start_date__lt=end_window,
        is_active=True
    )
    
    logger.info(f"Found {upcoming_events.count()} upcoming events")
    
    for event in upcoming_events:
        logger.info(f"Processing event: {event.title} at {event.start_date}")
        # Get all confirmed attendees
        confirmed_bookings = event.bookings.filter(status='confirmed')
        logger.info(f"Found {confirmed_bookings.count()} confirmed bookings")
        
        for booking in confirmed_bookings:
            # Check if notification already exists to avoid duplicates
            existing_notification = Notification.objects.filter(
                user=booking.user,
                notification_type='upcoming_event',
                title='Upcoming Event Reminder',
                message__icontains=event.title
            ).exists()
            
            if not existing_notification:
                create_upcoming_event_notification(
                    user=booking.user,
                    event_name=event.title,
                    event_time="tomorrow at " + event.start_date.strftime("%I:%M %p")
                )
                logger.info(f"Created upcoming event notification for {booking.user.username}")
            else:
                logger.info(f"Notification already exists for {booking.user.username}")
    
    # Also get events starting in 1-3 hours for immediate reminders
    immediate_start = now + timedelta(hours=1)
    immediate_end = now + timedelta(hours=3)
    
    logger.info(f"Looking for immediate events between {immediate_start} and {immediate_end}")
    
    immediate_events = Event.objects.filter(
        start_date__gte=immediate_start,
        start_date__lt=immediate_end,
        is_active=True
    )
    
    logger.info(f"Found {immediate_events.count()} immediate events")
    
    for event in immediate_events:
        confirmed_bookings = event.bookings.filter(status='confirmed')
        
        for booking in confirmed_bookings:
            # Check if immediate notification already exists
            existing_notification = Notification.objects.filter(
                user=booking.user,
                notification_type='upcoming_event',
                title='Upcoming Event Reminder',
                message__icontains=event.title
            ).filter(message__icontains='hour').exists()
            
            if not existing_notification:
                hours_until = int((event.start_date - now).total_seconds() / 3600)
                create_upcoming_event_notification(
                    user=booking.user,
                    event_name=event.title,
                    event_time=f"in {hours_until} hour{'s' if hours_until != 1 else ''} at " + event.start_date.strftime("%I:%M %p")
                )
                logger.info(f"Created immediate event notification for {booking.user.username}")
            else:
                logger.info(f"Immediate notification already exists for {booking.user.username}")
    
    logger.info("Upcoming event notification check completed")
