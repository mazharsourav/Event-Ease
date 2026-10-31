from django.contrib import admin
from .models import Event, EventBooking, TicketCategory, BookingTicketItem


class TicketCategoryInline(admin.TabularInline):
    model = TicketCategory
    extra = 1
    fields = ['name', 'category_type', 'price', 'quantity_available', 'description', 'is_active']


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ['title', 'organizer', 'event_type', 'start_date', 'is_free', 'is_active']
    list_filter = ['event_type', 'is_free', 'is_active', 'start_date']
    search_fields = ['title', 'description', 'organizer__username']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [TicketCategoryInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'event_type', 'organizer')
        }),
        ('Venue Details', {
            'fields': ('venue', 'venue_name', 'venue_address')
        }),
        ('Date & Time', {
            'fields': ('start_date', 'end_date', 'registration_deadline')
        }),
        ('Pricing & Capacity', {
            'fields': ('max_attendees', 'ticket_price', 'is_free')
        }),
        ('Additional Information', {
            'fields': ('image', 'contact_email', 'contact_phone', 'website', 'requirements')
        }),
        ('Status', {
            'fields': ('is_active', 'created_at', 'updated_at')
        }),
    )


@admin.register(TicketCategory)
class TicketCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'event', 'category_type', 'price', 'quantity_available', 'tickets_sold', 'is_active']
    list_filter = ['category_type', 'is_active', 'event__event_type']
    search_fields = ['name', 'event__title', 'description']
    readonly_fields = ['created_at', 'tickets_sold', 'tickets_available']
    
    def tickets_sold(self, obj):
        return obj.tickets_sold
    tickets_sold.short_description = 'Sold'


class BookingTicketItemInline(admin.TabularInline):
    model = BookingTicketItem
    extra = 0
    readonly_fields = ['price_per_ticket', 'subtotal']
    fields = ['ticket_category', 'quantity', 'price_per_ticket']
    
    def subtotal(self, obj):
        return f"${obj.subtotal}"
    subtotal.short_description = 'Subtotal'


@admin.register(EventBooking)
class EventBookingAdmin(admin.ModelAdmin):
    list_display = ['user', 'event', 'status', 'attendees_count', 'total_amount', 'booking_date']
    list_filter = ['status', 'payment_status', 'event__event_type', 'booking_date']
    search_fields = ['user__username', 'event__title', 'attendee_name', 'attendee_email']
    readonly_fields = ['booking_date', 'total_tickets']
    inlines = [BookingTicketItemInline]
    
    def total_tickets(self, obj):
        return obj.total_tickets
    total_tickets.short_description = 'Total Tickets'


@admin.register(BookingTicketItem)
class BookingTicketItemAdmin(admin.ModelAdmin):
    list_display = ['booking', 'ticket_category', 'quantity', 'price_per_ticket', 'subtotal']
    list_filter = ['ticket_category__category_type', 'booking__event']
    search_fields = ['booking__user__username', 'booking__event__title', 'ticket_category__name']
    readonly_fields = ['subtotal']
    
    def subtotal(self, obj):
        return f"${obj.subtotal}"
    subtotal.short_description = 'Subtotal'
