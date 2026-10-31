"""Site-level pages that don't belong to a single feature app."""
from django.shortcuts import render
from django.utils import timezone

from apps.events.models import Event
from apps.reviews.models import Review
from apps.venues.models import Venue

HOME_BILL_SIZE = 6
HOME_WALL_SIZE = 4
HOME_VENUES = 6
HOME_REVIEWS = 20


def home(request):
    # Upcoming and ongoing events first (soonest first), topped up with the most recent past events
    now = timezone.now()
    active_events = Event.objects.filter(is_active=True).select_related('venue')
    bill = list(active_events.filter(end_date__gte=now).order_by('start_date')[:HOME_BILL_SIZE])
    if len(bill) < HOME_BILL_SIZE:
        missing = HOME_BILL_SIZE - len(bill)
        bill += list(active_events.filter(end_date__lt=now).order_by('-start_date')[:missing])

    # The wall shows four posters; events with artwork take the front slots
    wall = sorted(bill[:HOME_WALL_SIZE], key=lambda event: not event.image)

    venues = (
        Venue.objects.filter(is_available=True)
        .prefetch_related('images')
        .order_by('-created_at')[:HOME_VENUES]
    )
    reviews = (
        Review.objects.select_related('user', 'user__profile')
        .order_by('-created_at')[:HOME_REVIEWS]
    )

    return render(request, 'core/home.html', {
        'recent_events': bill,
        'wall_events': wall,
        'recent_venues': venues,
        'latest_reviews': reviews,
        'event_types': Event.EVENT_TYPE_CHOICES,
    })
