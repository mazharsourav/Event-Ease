from django import forms
from .models import Review, EventReview, VenueReview

STAR_CHOICES = [(i, f'{i} Star{"s" if i != 1 else ""}') for i in range(1, 6)]


def star_select():
    """A 1-5 choice. The template draws it as a row of stars; this is the fallback and the validator."""
    return forms.Select(choices=STAR_CHOICES)


class RatingFieldsMixin:
    """Lets a template loop over every star rating on the form: {% for field in form.rating_fields %}."""

    @property
    def rating_fields(self):
        return [self[name] for name in self.fields if name.endswith('rating')]

    @property
    def body_field(self):
        """The free-text field: 'comment' on event and venue reviews, 'content' on the site review."""
        return self['comment'] if 'comment' in self.fields else self['content']


class ReviewForm(RatingFieldsMixin, forms.ModelForm):
    class Meta:
        model = Review
        fields = ['rating', 'title', 'content']
        widgets = {
            'rating': star_select(),
            'title': forms.TextInput(attrs={'placeholder': 'A few words that sum it up', 'maxlength': 200}),
            'content': forms.Textarea(attrs={'rows': 5, 'placeholder': 'Tell us how EventEase worked for you'}),
        }
        labels = {
            'rating': 'Your rating',
            'title': 'Title',
            'content': 'Your review',
        }


class EventReviewForm(RatingFieldsMixin, forms.ModelForm):
    class Meta:
        model = EventReview
        fields = ['rating', 'organization_rating', 'venue_rating', 'value_rating', 'title', 'comment']
        widgets = {
            'rating': star_select(),
            'organization_rating': star_select(),
            'venue_rating': star_select(),
            'value_rating': star_select(),
            'title': forms.TextInput(attrs={'placeholder': 'A few words that sum it up', 'maxlength': 200}),
            'comment': forms.Textarea(attrs={'rows': 5, 'placeholder': 'What was it like to be there?'}),
        }
        labels = {
            'rating': 'Overall',
            'organization_rating': 'Organisation',
            'venue_rating': 'Venue',
            'value_rating': 'Value for money',
            'title': 'Title',
            'comment': 'Your review',
        }

    def __init__(self, *args, **kwargs):
        self.event = kwargs.pop('event', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['comment'].required = False

    def save(self, commit=True):
        review = super().save(commit=False)
        if self.event:
            review.event = self.event
        if self.user:
            review.user = self.user
        if commit:
            review.save()
        return review


class VenueReviewForm(RatingFieldsMixin, forms.ModelForm):
    class Meta:
        model = VenueReview
        fields = ['rating', 'ambience_rating', 'service_rating', 'cleanliness_rating', 'value_rating', 'title', 'comment']
        widgets = {
            'rating': star_select(),
            'ambience_rating': star_select(),
            'service_rating': star_select(),
            'cleanliness_rating': star_select(),
            'value_rating': star_select(),
            'title': forms.TextInput(attrs={'placeholder': 'A few words that sum it up', 'maxlength': 200}),
            'comment': forms.Textarea(attrs={'rows': 5, 'placeholder': 'What was the venue like to use?'}),
        }
        labels = {
            'rating': 'Overall',
            'ambience_rating': 'Ambience',
            'service_rating': 'Service',
            'cleanliness_rating': 'Cleanliness',
            'value_rating': 'Value for money',
            'title': 'Title',
            'comment': 'Your review',
        }

    def __init__(self, *args, **kwargs):
        self.venue = kwargs.pop('venue', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['comment'].required = False

    def save(self, commit=True):
        review = super().save(commit=False)
        if self.venue:
            review.venue = self.venue
        if self.user:
            review.user = self.user
        if commit:
            review.save()
        return review
