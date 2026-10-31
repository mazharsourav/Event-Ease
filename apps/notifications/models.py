from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class Notification(models.Model):
    """
    Notification model for user notifications
    """
    NOTIFICATION_TYPES = [
        ('event_booking_confirm', 'Event Booking Confirmation'),
        ('venue_booking_status', 'Venue Booking Status'),
        ('upcoming_event', 'Upcoming Event'),
        ('venue_booking_request', 'Venue Booking Request'),
        ('event_registration', 'Event Registration'),
        ('system', 'System Notification'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_notifications')
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES, default='system')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Optional reference fields
    event_id = models.PositiveIntegerField(null=True, blank=True)
    venue_id = models.PositiveIntegerField(null=True, blank=True)
    booking_id = models.PositiveIntegerField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return f"{self.user.username} - {self.title}"
        
    def mark_as_read(self):
        """Mark this notification as read"""
        self.is_read = True
        self.save()
        
    @classmethod
    def create_notification(cls, user, title, message, notification_type='system', **kwargs):
        """Create a new notification for a user"""
        return cls.objects.create(
            user=user,
            title=title,
            message=message,
            notification_type=notification_type,
            **kwargs
        )
