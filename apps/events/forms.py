from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import Event, EventBooking, TicketCategory
from apps.venues.models import Venue

class EventForm(forms.ModelForm):
    """Form for creating and editing events"""
    
    class Meta:
        model = Event
        fields = [
            'title', 'description', 'event_type', 'venue', 'venue_name', 'venue_address',
            'start_date', 'end_date', 'registration_deadline', 'max_attendees',
            'ticket_price', 'is_free', 'image', 'contact_email', 'contact_phone',
            'website', 'requirements'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Event Title'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Describe your event...'
            }),
            'event_type': forms.Select(attrs={
                'class': 'form-control'
            }),
            'venue': forms.Select(attrs={
                'class': 'form-control'
            }),
            'venue_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Venue Name (if not using system venue)'
            }),
            'venue_address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Venue Address'
            }),
            'start_date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'end_date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'registration_deadline': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'max_attendees': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1'
            }),
            'ticket_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'is_free': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
            'contact_email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'contact@example.com'
            }),
            'contact_phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+1234567890'
            }),
            'website': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://example.com'
            }),
            'requirements': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Special requirements or notes...'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show available venues
        self.fields['venue'].queryset = Venue.objects.filter(is_available=True)
        self.fields['venue'].empty_label = "Select a venue (optional)"
        
        # Set initial contact email to user's email if creating new event
        if not self.instance.pk and hasattr(self, 'user'):
            self.fields['contact_email'].initial = self.user.email
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        registration_deadline = cleaned_data.get('registration_deadline')
        venue = cleaned_data.get('venue')
        venue_name = cleaned_data.get('venue_name')
        is_free = cleaned_data.get('is_free')
        ticket_price = cleaned_data.get('ticket_price')
        
        # Validate dates
        if start_date and end_date:
            if start_date >= end_date:
                raise ValidationError("End date must be after start date.")
            
            if start_date <= timezone.now():
                raise ValidationError("Start date must be in the future.")
        
        if registration_deadline and start_date:
            if registration_deadline >= start_date:
                raise ValidationError("Registration deadline must be before start date.")
        
        # Validate venue information
        if not venue and not venue_name:
            raise ValidationError("Please either select a venue or provide venue name.")
        
        # Validate pricing
        if not is_free and (not ticket_price or ticket_price <= 0):
            raise ValidationError("Please set a ticket price for paid events.")
        
        if is_free and ticket_price and ticket_price > 0:
            cleaned_data['ticket_price'] = 0  # Reset price for free events
        
        return cleaned_data

class EventBookingForm(forms.ModelForm):
    """Form for booking events with multiple ticket categories"""
    
    class Meta:
        model = EventBooking
        fields = ['attendee_name', 'attendee_email', 'attendee_phone', 'special_requests']
        widgets = {
            'attendee_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Full name of the primary ticket holder'
            }),
            'attendee_email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Email address for ticket confirmation'
            }),
            'attendee_phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Phone number for contact'
            }),
            'special_requests': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Any special requirements or dietary restrictions...'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.event = kwargs.pop('event', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Auto-fill with user information if available
        if self.user and not self.initial:
            user_full_name = self.user.get_full_name()
            if not user_full_name:
                user_full_name = self.user.username
            
            self.fields['attendee_name'].initial = user_full_name
            self.fields['attendee_email'].initial = self.user.email
            
            # Get phone from user profile if available
            if hasattr(self.user, 'profile') and self.user.profile.phone:
                self.fields['attendee_phone'].initial = self.user.profile.phone
        
        # Add dynamic quantity fields for each ticket category
        if self.event and self.event.ticket_categories.exists():
            for category in self.event.ticket_categories.filter(quantity_available__gt=0):
                field_name = f'quantity_{category.id}'
                self.fields[field_name] = forms.IntegerField(
                    min_value=0,
                    max_value=min(6, category.tickets_available),  # Max 6 or available tickets
                    initial=0,
                    required=False,
                    widget=forms.NumberInput(attrs={
                        'class': 'quantity-input form-control',
                        'data-category-id': category.id,
                        'data-price': str(category.price),
                        'data-max': min(6, category.tickets_available),
                        'min': '0',
                        'max': str(min(6, category.tickets_available))
                    }),
                    label=f'{category.name} (${category.price})'
                )
        
        # Make attendee fields required
        self.fields['attendee_name'].required = True
        self.fields['attendee_email'].required = True
        self.fields['attendee_phone'].required = True
        # Make special requests optional
        self.fields['special_requests'].required = False
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Only validate ticket quantities if event has ticket categories
        if self.event and self.event.ticket_categories.exists():
            # Calculate total tickets selected
            total_tickets = 0
            has_tickets = False
            
            for category in self.event.ticket_categories.all():
                field_name = f'quantity_{category.id}'
                quantity = cleaned_data.get(field_name, 0)
                if quantity and quantity > 0:
                    total_tickets += quantity
                    has_tickets = True
                    
                    # Check availability
                    if quantity > category.tickets_available:
                        raise ValidationError(f'Only {category.tickets_available} tickets available for {category.name}')
            
            # Validate total tickets for events with categories
            if total_tickets > 6:
                raise ValidationError('You can purchase a maximum of 6 tickets total.')
            
            if not has_tickets:
                raise ValidationError('Please select at least one ticket.')
        
        # For events without categories, no ticket quantity validation needed
        # The booking will use the event's default ticket_price and quantity of 1
        
        return cleaned_data
    
    def get_selected_tickets(self):
        """Get dictionary of selected ticket categories and quantities"""
        selected_tickets = {}
        if self.is_valid() and self.event:
            for category in self.event.ticket_categories.all():
                field_name = f'quantity_{category.id}'
                quantity = self.cleaned_data.get(field_name, 0)
                if quantity and quantity > 0:
                    selected_tickets[category] = quantity
        return selected_tickets

class EventSearchForm(forms.Form):
    """Form for searching events"""
    
    q = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search events...'
        })
    )
    
    event_type = forms.ChoiceField(
        choices=[('', 'All Types')] + Event.EVENT_TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
    is_free = forms.ChoiceField(
        choices=[
            ('', 'All Events'),
            ('true', 'Free Events'),
            ('false', 'Paid Events')
        ],
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )


class TicketCategoryForm(forms.ModelForm):
    """Form for creating ticket categories"""
    
    class Meta:
        model = TicketCategory
        fields = ['name', 'category_type', 'price', 'quantity_available', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., General Admission, VIP, Student'
            }),
            'category_type': forms.Select(attrs={
                'class': 'form-control'
            }),
            'price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00'
            }),
            'quantity_available': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'placeholder': 'Number of tickets available'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'What does this ticket include?'
            }),
        }

    def clean_price(self):
        price = self.cleaned_data.get('price')
        if price < 0:
            raise ValidationError("Price cannot be negative.")
        return price

    def clean_quantity_available(self):
        quantity = self.cleaned_data.get('quantity_available')
        if quantity <= 0:
            raise ValidationError("Quantity must be greater than 0.")
        return quantity


# Formset for handling multiple ticket categories
TicketCategoryFormSet = forms.formset_factory(
    TicketCategoryForm,
    extra=0,  # Start with no extra forms - will add dynamically
    max_num=5,  # Allow up to 5 ticket categories
    validate_max=True,
    can_delete=True
)


class EventCommentForm(forms.Form):
    """Form for submitting comments and replies on event pages"""
    comment = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Ask a question or leave a comment about this event...',
            'style': 'resize: vertical; min-height: 80px;'
        }),
        max_length=1000,
        help_text='Maximum 1000 characters'
    )
    image = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*'
        }),
        help_text='Optional: Upload an image (Max 5MB, JPG/PNG/GIF)'
    )
    parent_id = forms.IntegerField(
        widget=forms.HiddenInput(),
        required=False
    )
    
    def clean_image(self):
        image = self.cleaned_data.get('image')
        if image:
            # Check file size (5MB limit)
            if image.size > 5 * 1024 * 1024:
                raise forms.ValidationError('Image file too large. Maximum size is 5MB.')
            
            # Check file type
            if not image.content_type.startswith('image/'):
                raise forms.ValidationError('File must be an image.')
                
        return image
