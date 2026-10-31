from django.db import models
from django.contrib.auth.models import User
from apps.events.models import EventBooking

class Payment(models.Model):
    """Payment model for event bookings"""
    
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    
    PAYMENT_METHOD_CHOICES = [
        ('credit_card', 'Credit Card'),
        ('debit_card', 'Debit Card'),
        ('paypal', 'PayPal'),
        ('bank_transfer', 'Bank Transfer'),
        ('cash', 'Cash'),
        ('free', 'Free Event'),
        ('bkash', 'bKash'),
        ('nagad', 'Nagad'),
    ]
    
    booking = models.OneToOneField(EventBooking, on_delete=models.CASCADE, related_name='payment')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    
    # Payment gateway fields
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    bank_transaction_id = models.CharField(max_length=100, blank=True, null=True)  # For SSL Commerz bank_tran_id
    payment_gateway = models.CharField(max_length=50, blank=True, null=True)
    gateway_response = models.TextField(blank=True, null=True)
    
    # Billing information
    billing_name = models.CharField(max_length=100)
    billing_email = models.EmailField()
    billing_phone = models.CharField(max_length=20, blank=True)
    billing_address = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return f"Payment #{self.id} - {self.booking.event.title} - ${self.amount}"
        
    def mark_as_paid(self):
        """Mark payment as completed and update booking status"""
        from django.utils import timezone
        
        self.payment_status = 'completed'
        self.paid_at = timezone.now()
        self.save()
        
        # Update booking status
        self.booking.payment_status = 'completed'
        self.booking.status = 'confirmed'
        self.booking.save()
        
        return True
        
    def mark_as_failed(self, reason=""):
        """Mark payment as failed"""
        self.payment_status = 'failed'
        self.gateway_response = reason
        self.save()
        
        # Update booking status
        self.booking.payment_status = 'failed'
        self.booking.status = 'cancelled'
        self.booking.save()
        
        return True
