from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse

class Venue(models.Model):
    VENUE_TYPE_CHOICES = [
        ('conference_hall', 'Conference Hall'),
        ('banquet_hall', 'Banquet Hall'),
        ('auditorium', 'Auditorium'),
        ('outdoor_space', 'Outdoor Space'),
        ('hotel', 'Hotel'),
        ('restaurant', 'Restaurant'),
        ('community_center', 'Community Center'),
        ('sports_facility', 'Sports Facility'),
        ('art_gallery', 'Art Gallery'),
        ('museum', 'Museum'),
        ('theater', 'Theater'),
        ('other', 'Other'),
    ]
    
    name = models.CharField(max_length=200)
    description = models.TextField()
    venue_type = models.CharField(max_length=20, choices=VENUE_TYPE_CHOICES, default='other')
    manager = models.ForeignKey(User, on_delete=models.CASCADE, related_name='managed_venues')
    
    address = models.TextField()
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    zipcode = models.CharField(max_length=10)
    country = models.CharField(max_length=100, default='USA')
    
    capacity = models.PositiveIntegerField()
    price_per_hour = models.DecimalField(max_digits=10, decimal_places=2)
    price_per_day = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Amenities
    has_parking = models.BooleanField(default=False)
    has_wifi = models.BooleanField(default=False)
    has_catering = models.BooleanField(default=False)
    has_av_equipment = models.BooleanField(default=False)
    has_air_conditioning = models.BooleanField(default=False)
    has_accessibility = models.BooleanField(default=False)
    
    # Contact Information
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=15)
    website = models.URLField(blank=True, null=True)
    
    # Images
    main_image = models.ImageField(upload_to='venues/', blank=True, null=True)
    
    # Availability
    is_available = models.BooleanField(default=True)
    min_booking_hours = models.PositiveIntegerField(default=1)
    max_booking_days = models.PositiveIntegerField(default=30)
    
    # Additional Info
    rules_and_regulations = models.TextField(blank=True, null=True)
    cancellation_policy = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def get_absolute_url(self):
        return reverse('venues:venue_detail', kwargs={'pk': self.pk})
    
    @property
    def amenities_list(self):
        amenities = []
        if self.has_parking:
            amenities.append('Parking')
        if self.has_wifi:
            amenities.append('WiFi')
        if self.has_catering:
            amenities.append('Catering')
        if self.has_av_equipment:
            amenities.append('A/V Equipment')
        if self.has_air_conditioning:
            amenities.append('Air Conditioning')
        if self.has_accessibility:
            amenities.append('Accessibility')
        return amenities
    
    @property
    def average_rating(self):
        """Return the average rating for this venue"""
        reviews = self.reviews.all()
        if reviews.exists():
            return reviews.aggregate(models.Avg('rating'))['rating__avg'] or 0
        return 0
    
    @property
    def review_count(self):
        """Return the total number of reviews for this venue"""
        return self.reviews.count()
    
    @property
    def category_averages(self):
        """Return average ratings for each category"""
        reviews = self.reviews.all()
        if reviews.exists():
            return {
                'ambience': reviews.aggregate(models.Avg('ambience_rating'))['ambience_rating__avg'] or 0,
                'service': reviews.aggregate(models.Avg('service_rating'))['service_rating__avg'] or 0,
                'cleanliness': reviews.aggregate(models.Avg('cleanliness_rating'))['cleanliness_rating__avg'] or 0,
                'value': reviews.aggregate(models.Avg('value_rating'))['value_rating__avg'] or 0,
            }
        return {'ambience': 0, 'service': 0, 'cleanliness': 0, 'value': 0}
    
    def update_average_rating(self):
        """Update cached rating fields if needed (currently using properties)"""
        # This method exists for consistency with Event model
        # Currently using properties for real-time calculation
        pass

class VenueImage(models.Model):
    """Model for storing multiple images for each venue"""
    venue = models.ForeignKey(Venue, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='venues/images/')
    caption = models.CharField(max_length=200, blank=True, null=True)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-is_primary', 'created_at']
    
    def __str__(self):
        return f"{self.venue.name} - Image {self.id}"

class VenueBooking(models.Model):
    BOOKING_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
    ]
    
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    
    venue = models.ForeignKey(Venue, on_delete=models.CASCADE, related_name='bookings')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='venue_bookings')
    event_title = models.CharField(max_length=200)
    event_description = models.TextField()
    
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    booking_date = models.DateTimeField(auto_now_add=True)
    
    status = models.CharField(max_length=20, choices=BOOKING_STATUS_CHOICES, default='pending')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=15)
    special_requirements = models.TextField(blank=True, null=True)
    
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    
    class Meta:
        ordering = ['-booking_date']
    
    def __str__(self):
        return f"{self.user.username} - {self.venue.name} - {self.event_title}"
    
    def get_payment_status_display(self):
        return dict(self.PAYMENT_STATUS_CHOICES).get(self.payment_status, self.payment_status)


class VenueComment(models.Model):
    """Model for storing comments and questions about venues"""
    venue = models.ForeignKey(Venue, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='venue_comments')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    comment = models.TextField()
    image = models.ImageField(upload_to='venue_comments/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.venue.name} - {self.comment[:50]}"
    
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
            like, created = VenueCommentLike.objects.get_or_create(
                comment=self,
                user=user
            )
            if not created:
                like.delete()
                return False
            return True
        return False


class VenueCommentLike(models.Model):
    """Model for storing likes on venue comments and replies"""
    comment = models.ForeignKey(VenueComment, on_delete=models.CASCADE, related_name='likes')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='venue_comment_likes')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('comment', 'user')  # Ensure one like per user per comment
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} likes {self.comment.user.username}'s comment"
