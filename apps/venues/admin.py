from django.contrib import admin
from .models import Venue, VenueImage, VenueBooking, VenueComment

@admin.register(Venue)
class VenueAdmin(admin.ModelAdmin):
    list_display = ['name', 'venue_type', 'city', 'capacity', 'is_available', 'manager']
    list_filter = ['venue_type', 'is_available', 'city', 'created_at']
    search_fields = ['name', 'description', 'city']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(VenueImage)
class VenueImageAdmin(admin.ModelAdmin):
    list_display = ['venue', 'is_primary', 'created_at']
    list_filter = ['is_primary', 'created_at']

@admin.register(VenueBooking)
class VenueBookingAdmin(admin.ModelAdmin):
    list_display = ['venue', 'user', 'event_title', 'start_date', 'status', 'total_amount']
    list_filter = ['status', 'payment_status', 'booking_date']
    search_fields = ['event_title', 'venue__name', 'user__username']
    readonly_fields = ['booking_date']

@admin.register(VenueComment)
class VenueCommentAdmin(admin.ModelAdmin):
    list_display = ['venue', 'user', 'comment_preview', 'parent', 'created_at']
    list_filter = ['created_at', 'venue']
    search_fields = ['comment', 'venue__name', 'user__username']
    readonly_fields = ['created_at', 'updated_at']
    
    def comment_preview(self, obj):
        return obj.comment[:50] + '...' if len(obj.comment) > 50 else obj.comment
    comment_preview.short_description = 'Comment'
