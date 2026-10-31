from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import Venue, VenueBooking, VenueImage

class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = single_file_clean(data, initial)
        return result

class VenueForm(forms.ModelForm):
    """Form for creating and editing venues"""
    
    # Add multiple image upload field
    images = MultipleFileField(
        required=False,
        help_text='Select as many images as you want to showcase your venue (Max 5MB per image)'
    )
    
    class Meta:
        model = Venue
        fields = [
            'name', 'description', 'venue_type', 'address', 'city', 'state', 
            'zipcode', 'capacity', 'price_per_hour', 'price_per_day',
            'has_parking', 'has_wifi', 'has_catering', 'has_av_equipment',
            'has_air_conditioning', 'has_accessibility',
            'contact_email', 'contact_phone', 'website', 'main_image', 'is_available'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Venue Name'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Describe your venue...'
            }),
            'venue_type': forms.Select(attrs={
                'class': 'form-control'
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Street Address'
            }),
            'city': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'City'
            }),
            'state': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'State/Province'
            }),
            'zipcode': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'ZIP Code'
            }),
            'country': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Country'
            }),
            'capacity': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1'
            }),
            'price_per_hour': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'price_per_day': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'has_parking': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'has_wifi': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'has_catering': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'has_av_equipment': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'has_air_conditioning': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'has_accessibility': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'contact_email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'contact@venue.com'
            }),
            'contact_phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+1234567890'
            }),
            'website': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://venue.com'
            }),
            'main_image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set widget attributes for the images field
        self.fields['images'].widget.attrs.update({
            'class': 'form-control',
            'accept': 'image/*'
        })
        
        # Set initial contact email to user's email if creating new venue
        if not self.instance.pk and hasattr(self, 'user'):
            self.fields['contact_email'].initial = self.user.email
    
    def clean(self):
        cleaned_data = super().clean()
        price_per_hour = cleaned_data.get('price_per_hour')
        price_per_day = cleaned_data.get('price_per_day')
        
        # Validate that at least one rate is provided
        if not price_per_hour and not price_per_day:
            raise ValidationError("Please provide either hourly rate or daily rate (or both).")
        
        return cleaned_data
    
    def clean_images(self):
        images = self.files.getlist('images')
        if images:
            # Validate image files
            for image in images:
                if image.size > 5 * 1024 * 1024:  # 5MB limit
                    raise ValidationError(f"Image {image.name} is too large. Maximum size is 5MB.")
                
                # Check file type
                if not image.content_type.startswith('image/'):
                    raise ValidationError(f"File {image.name} is not a valid image.")
        
        return images

class VenueBookingForm(forms.ModelForm):
    """Form for booking venues"""
    
    class Meta:
        model = VenueBooking
        fields = [
            'event_title', 'event_description', 'start_date', 'end_date', 
            'contact_email', 'contact_phone', 'special_requirements'
        ]
        widgets = {
            'event_title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Event Title'
            }),
            'event_description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Brief description of your event...'
            }),
            'start_date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'end_date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'contact_email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'contact@example.com'
            }),
            'contact_phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+1234567890'
            }),
            'special_requirements': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Special setup requirements, catering needs, etc.'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.venue = kwargs.pop('venue', None)
        super().__init__(*args, **kwargs)
        
        # Make special requirements optional
        self.fields['special_requirements'].required = False
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        # Validate date is in the future
        if start_date and start_date <= timezone.now():
            raise ValidationError("Start date must be in the future.")
        
        # Validate time order
        if start_date and end_date:
            if start_date >= end_date:
                raise ValidationError("End date must be after start date.")
        
        # Check for conflicting bookings
        if start_date and end_date and self.venue:
            conflicting_bookings = VenueBooking.objects.filter(
                venue=self.venue,
                status__in=['confirmed', 'completed']
            ).exclude(pk=self.instance.pk if self.instance else None)
            
            for booking in conflicting_bookings:
                # Check for time overlap
                if (start_date < booking.end_date and end_date > booking.start_date):
                    raise ValidationError(
                        f"This time slot conflicts with an existing booking."
                    )
        
        return cleaned_data

class VenueSearchForm(forms.Form):
    """Form for searching venues"""
    
    q = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search venues...'
        })
    )
    
    venue_type = forms.ChoiceField(
        choices=[('', 'All Types')] + Venue.VENUE_TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
    min_capacity = forms.IntegerField(
        required=False,
        min_value=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Minimum capacity'
        })
    )
    
    city = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'City'
        })
    )
    
    amenities = forms.MultipleChoiceField(
        choices=[
            ('WiFi', 'WiFi'),
            ('Parking', 'Parking'),
            ('Air Conditioning', 'Air Conditioning'),
            ('Sound System', 'Sound System'),
            ('Projector', 'Projector'),
            ('Catering', 'Catering'),
            ('Kitchen', 'Kitchen'),
            ('Bar', 'Bar'),
            ('Stage', 'Stage'),
            ('Dance Floor', 'Dance Floor'),
        ],
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input'
        })
    )


class VenueCommentForm(forms.Form):
    """Form for submitting comments and replies on venue pages"""
    comment = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Ask a question or leave a comment...',
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
