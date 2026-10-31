import re

from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

class Event(models.Model):
    EVENT_TYPE_CHOICES = [
        ('conference', 'Conference'),
        ('workshop', 'Workshop'),
        ('seminar', 'Seminar'),
        ('concert', 'Concert'),
        ('wedding', 'Wedding'),
        ('party', 'Party'),
        ('corporate', 'Corporate Event'),
        ('sports', 'Sports Event'),
        ('festival', 'Festival'),
        ('exhibition', 'Exhibition'),
        ('other', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('upcoming', 'Upcoming'),
        ('ongoing', 'Ongoing'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    title = models.CharField(max_length=200)
    description = models.TextField()
    event_type = models.CharField(max_length=20, choices=EVENT_TYPE_CHOICES, default='other')
    organizer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='organized_events')
    venue = models.ForeignKey('venues.Venue', on_delete=models.CASCADE, related_name='events', null=True, blank=True)
    venue_name = models.CharField(max_length=200, help_text="Venue name if not using system venue")
    venue_address = models.TextField(help_text="Venue address")
    
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    registration_deadline = models.DateTimeField(null=True, blank=True)
    
    max_attendees = models.PositiveIntegerField(default=100)
    ticket_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    is_free = models.BooleanField(default=True)
    
    image = models.ImageField(upload_to='events/', blank=True, null=True)
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=15, blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    
    requirements = models.TextField(blank=True, null=True, help_text="Special requirements or notes")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-start_date']
    
    def __str__(self):
        return self.title
    
    def get_absolute_url(self):
        return reverse('events:event_detail', kwargs={'pk': self.pk})
    
    @property
    def status(self):
        now = timezone.now()
        if self.start_date > now:
            return 'upcoming'
        elif self.start_date <= now <= self.end_date:
            return 'ongoing'
        else:
            return 'completed'
    
    @property
    def current_attendees(self):
        return self.bookings.filter(status='confirmed').count()
    
    @property
    def available_spots(self):
        return max(0, self.max_attendees - self.current_attendees)
    
    @property
    def is_full(self):
        return self.current_attendees >= self.max_attendees
    
    @property
    def average_rating(self):
        """Calculate average rating from all reviews"""
        reviews = self.reviews.all()
        if not reviews:
            return 0
        return sum([review.rating for review in reviews]) / len(reviews)
    
    @property
    def review_count(self):
        """Get total number of reviews"""
        return self.reviews.count()
    
    @property
    def can_be_reviewed(self):
        """Check if event can be reviewed (is completed)"""
        return self.status == 'completed'
    
    @property
    def avg_organization_rating(self):
        """Calculate average organization rating from all reviews"""
        reviews = self.reviews.all()
        if not reviews:
            return 0
        return sum([review.organization_rating for review in reviews]) / len(reviews)
    
    @property
    def avg_venue_rating(self):
        """Calculate average venue rating from all reviews"""
        reviews = self.reviews.all()
        if not reviews:
            return 0
        return sum([review.venue_rating for review in reviews]) / len(reviews)
    
    @property
    def avg_value_rating(self):
        """Calculate average value rating from all reviews"""
        reviews = self.reviews.all()
        if not reviews:
            return 0
        return sum([review.value_rating for review in reviews]) / len(reviews)
    
    def update_average_rating(self):
        """Update cached average rating - can be used for optimization"""
        # This method can be used to cache rating in a separate field if needed
        pass


class TicketCategory(models.Model):
    """Model for different ticket categories for an event"""
    
    CATEGORY_TYPES = [
        ('general', 'General Admission'),
        ('vip', 'VIP'),
        ('premium', 'Premium'),
        ('student', 'Student'),
        ('early_bird', 'Early Bird'),
        ('group', 'Group'),
        ('senior', 'Senior'),
        ('child', 'Child'),
    ]
    
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='ticket_categories')
    name = models.CharField(max_length=100)
    category_type = models.CharField(max_length=20, choices=CATEGORY_TYPES, default='general')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity_available = models.PositiveIntegerField(default=0)
    description = models.TextField(blank=True, null=True, help_text="Description of what this ticket includes")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['price']
        unique_together = ['event', 'name']
    
    def __str__(self):
        return f"{self.event.title} - {self.name} (${self.price})"
    
    @property
    def tickets_sold(self):
        from django.db.models import Sum
        return BookingTicketItem.objects.filter(
            ticket_category=self,
            booking__status__in=['confirmed', 'paid']
        ).aggregate(total=Sum('quantity'))['total'] or 0
    
    @property
    def tickets_available(self):
        return max(0, self.quantity_available - self.tickets_sold)
    
    @property
    def is_sold_out(self):
        return self.tickets_available <= 0


class EventBooking(models.Model):
    BOOKING_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('attended', 'Attended'),
        ('no_show', 'No Show'),
    ]
    
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='bookings')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='event_bookings')
    booking_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=BOOKING_STATUS_CHOICES, default='pending')
    attendees_count = models.PositiveIntegerField(default=1)
    special_requests = models.TextField(blank=True, null=True)
    payment_status = models.CharField(max_length=20, default='pending')
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Ticket holder information
    attendee_name = models.CharField(max_length=200, blank=True, null=True, help_text="Full name of the ticket holder")
    attendee_email = models.EmailField(blank=True, null=True, help_text="Email address of the ticket holder")
    attendee_phone = models.CharField(max_length=15, blank=True, null=True, help_text="Phone number of the ticket holder")
    
    class Meta:
        unique_together = ['event', 'user']
        ordering = ['-booking_date']
    
    def __str__(self):
        return f"{self.user.username} - {self.event.title}"
    
    @property
    def can_cancel(self):
        return self.status in ['pending', 'confirmed'] and self.event.start_date > timezone.now()

    @property
    def reference(self):
        """The booking number as people see it: printed on the ticket and held in its QR code."""
        return f'EE-{self.pk:06d}'

    @property
    def has_ticket(self):
        """A ticket exists once the place is actually held."""
        return self.status in ['confirmed', 'attended']

    @classmethod
    def from_reference(cls, reference):
        """The reverse of `reference`. Returns None when the text is not one of ours."""
        match = re.fullmatch(r'EE-(\d{1,9})', (reference or '').strip().upper())
        return cls.objects.filter(pk=int(match.group(1))).first() if match else None
    
    @property
    def total_tickets(self):
        """Calculate total number of tickets in this booking"""
        return self.ticket_items.aggregate(total=models.Sum('quantity'))['total'] or 0
    
    def save(self, *args, **kwargs):
        # Update total_amount and attendees_count based on ticket items
        super().save(*args, **kwargs)
        self.update_totals()
    
    def update_totals(self):
        """Update total_amount and attendees_count based on ticket items"""
        ticket_items = self.ticket_items.all()
        
        if ticket_items.exists():
            # Event with ticket categories - calculate from ticket items
            self.total_amount = sum(item.quantity * item.ticket_category.price for item in ticket_items)
            self.attendees_count = sum(item.quantity for item in ticket_items)
            self.amount = self.total_amount  # Keep amount in sync with total_amount
            EventBooking.objects.filter(pk=self.pk).update(
                total_amount=self.total_amount,
                attendees_count=self.attendees_count,
                amount=self.total_amount
            )
        else:
            # Event without ticket categories - don't override manually set amounts
            # Only update if amounts are not already set
            if self.amount == 0 and self.total_amount == 0:
                self.total_amount = self.event.ticket_price or 0
                self.amount = self.total_amount
                if self.attendees_count == 0:
                    self.attendees_count = 1
                EventBooking.objects.filter(pk=self.pk).update(
                    total_amount=self.total_amount,
                    amount=self.total_amount,
                    attendees_count=self.attendees_count
                )


class BookingTicketItem(models.Model):
    """Individual ticket items within a booking"""
    booking = models.ForeignKey(EventBooking, on_delete=models.CASCADE, related_name='ticket_items')
    ticket_category = models.ForeignKey(TicketCategory, on_delete=models.CASCADE, related_name='booking_items')
    quantity = models.PositiveIntegerField(default=1)
    price_per_ticket = models.DecimalField(max_digits=10, decimal_places=2, help_text="Price at time of booking")
    
    class Meta:
        unique_together = ['booking', 'ticket_category']
    
    def __str__(self):
        return f"{self.booking.user.username} - {self.ticket_category.name} x{self.quantity}"
    
    @property
    def subtotal(self):
        return self.quantity * self.price_per_ticket
    
    def save(self, *args, **kwargs):
        # Store the price at time of booking
        if not self.price_per_ticket:
            self.price_per_ticket = self.ticket_category.price
        super().save(*args, **kwargs)
        # Update booking totals after saving
        self.booking.update_totals()


class EventComment(models.Model):
    """Model for storing comments and questions about events"""
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='event_comments')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    comment = models.TextField()
    image = models.ImageField(upload_to='event_comments/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.event.title} - {self.comment[:50]}"
    
    @property
    def is_reply(self):
        return self.parent is not None
    
    def get_replies(self):
        return self.replies.all().order_by('created_at')
    
    @property
    def like_count(self):
        """Return the number of likes for this comment"""
        return self.likes.count()
    
    def is_liked_by_user(self, user):
        """Check if a specific user has liked this comment"""
        if user.is_authenticated:
            return self.likes.filter(user=user).exists()
        return False
    
    def toggle_like(self, user):
        """Toggle like status for a user - returns True if liked, False if unliked"""
        if user.is_authenticated:
            like, created = EventCommentLike.objects.get_or_create(
                comment=self,
                user=user
            )
            if not created:
                like.delete()
                return False
            return True
        return False


class EventCommentLike(models.Model):
    """Model for storing likes on event comments and replies"""
    comment = models.ForeignKey(EventComment, on_delete=models.CASCADE, related_name='likes')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='event_comment_likes')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['comment', 'user']
    
    def __str__(self):
        return f"{self.user.username} liked {self.comment.user.username}'s comment on {self.comment.event.title}"
