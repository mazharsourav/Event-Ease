from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone

class Review(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='service_reviews')
    rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Rating from 1 to 5 stars"
    )
    title = models.CharField(max_length=200, help_text="Brief title for your review")
    content = models.TextField(help_text="Your detailed review about our service")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_featured = models.BooleanField(default=False, help_text="Mark as featured review")
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ['user']  # One review per user
    
    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - {self.rating} stars"
    
    @property
    def star_range(self):
        """Returns range for displaying stars in template"""
        return range(1, 6)
    
    @property
    def filled_stars(self):
        """Returns range for filled stars"""
        return range(1, self.rating + 1)
    
    @property
    def empty_stars(self):
        """Returns range for empty stars"""
        return range(self.rating + 1, 6)


class EventReview(models.Model):
    """Model for event reviews - only users who registered for the event can review after it's completed"""
    
    event = models.ForeignKey('events.Event', on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='event_reviews')
    booking = models.OneToOneField('events.EventBooking', on_delete=models.CASCADE, related_name='review', null=True, blank=True)
    
    # Overall rating
    rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Overall rating from 1 to 5 stars"
    )
    
    # Category-specific ratings
    organization_rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Rating for event organization (1-5 stars)"
    )
    venue_rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Rating for venue quality (1-5 stars)"
    )
    value_rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Rating for value for money (1-5 stars)"
    )
    
    # Review content
    title = models.CharField(max_length=200, help_text="Brief title for your review")
    comment = models.TextField(help_text="Your detailed review about the event", blank=True, null=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_verified = models.BooleanField(default=True, help_text="Verified attendee review")
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ['event', 'user']  # One review per user per event
    
    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - {self.event.title} ({self.rating}★)"
    
    def clean(self):
        """Validate that user can only review events they've registered for and that are completed"""
        from apps.events.models import EventBooking
        
        # Skip validation if event or user is not set (e.g., during form initialization)
        if not hasattr(self, 'event') or not self.event or not self.user:
            return
            
        # Check if event is completed (past end date)
        try:
            if self.event.end_date > timezone.now():
                raise ValidationError("You can only review events that have been completed.")
        except AttributeError:
            # Event relationship not properly loaded
            return
        
        # Check if user has a confirmed or attended booking for this event
        booking_exists = EventBooking.objects.filter(
            event=self.event,
            user=self.user,
            status__in=['confirmed', 'attended', 'paid']
        ).exists()
        
        if not booking_exists:
            raise ValidationError("You can only review events you have registered for and attended.")
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        # Update event's cached rating
        self.event.update_average_rating()
    
    @property
    def star_display(self):
        """Returns dict for displaying stars in templates"""
        return {
            'filled': range(1, self.rating + 1),
            'empty': range(self.rating + 1, 6)
        }
    
    @property
    def category_ratings(self):
        """Returns category ratings as dict"""
        return {
            'organization': self.organization_rating,
            'venue': self.venue_rating,
            'value': self.value_rating
        }


class VenueReview(models.Model):
    """Model for venue reviews - users can review venues after events they attended at those venues"""
    
    venue = models.ForeignKey('venues.Venue', on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='venue_reviews')
    
    # Overall rating
    rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Overall rating from 1 to 5 stars"
    )
    
    # Category-specific ratings for venues
    ambience_rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Rating for venue ambience and atmosphere (1-5 stars)"
    )
    service_rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Rating for venue service quality (1-5 stars)"
    )
    cleanliness_rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Rating for venue cleanliness and maintenance (1-5 stars)"
    )
    value_rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Rating for venue value for money (1-5 stars)"
    )
    
    # Review content
    title = models.CharField(max_length=200, help_text="Brief title for your venue review")
    comment = models.TextField(help_text="Your detailed review about the venue", blank=True, null=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_verified = models.BooleanField(default=True, help_text="Verified venue visitor review")
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ['venue', 'user']  # One review per user per venue
    
    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - {self.venue.name} ({self.rating}★)"
    
    def clean(self):
        """Validate that user can only review venues they've actually booked"""
        from apps.venues.models import VenueBooking
        from django.utils import timezone
        
        # Skip validation if venue or user is not set (e.g., during form initialization)
        if not hasattr(self, 'venue') or not self.venue or not self.user:
            return
            
        # Check if user has actually booked this venue and the booking is completed
        has_booked_venue = VenueBooking.objects.filter(
            user=self.user,
            venue=self.venue,
            status__in=['confirmed', 'completed'],
            end_date__lt=timezone.now()  # Booking must be completed (past end date)
        ).exists()
        
        if not has_booked_venue:
            raise ValidationError("You can only review venues that you have booked and where your booking has been completed.")
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        # Update venue's cached rating
        self.venue.update_average_rating()
    
    @property
    def star_display(self):
        """Returns dict for displaying stars in templates"""
        return {
            'filled': range(1, self.rating + 1),
            'empty': range(self.rating + 1, 6)
        }
    
    @property
    def category_ratings(self):
        """Returns category ratings as dict"""
        return {
            'ambience': self.ambience_rating,
            'service': self.service_rating,
            'cleanliness': self.cleanliness_rating,
            'value': self.value_rating
        }
