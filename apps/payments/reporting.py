"""What the platform has taken, for the admin dashboard.

Organisers see their own revenue on their dashboard; this is the same question asked of the
whole site. It lives beside the Payment model because that is where the money is recorded.
"""
from datetime import timedelta

from django.db.models import Q, Sum
from django.utils import timezone

from apps.events.models import Event
from apps.venues.models import Venue, VenueBooking

from .models import Payment

HELD = ['confirmed', 'completed']  # a venue booking the manager has accepted
RECENT_DAYS = 30
TOP = 5


def platform_revenue():
    """Money actually taken, split by what it was taken for.

    Tickets are counted from completed payments rather than from confirmed bookings, because
    a booking can be confirmed without money changing hands: a free event, or an organiser
    confirming someone by hand. Venue hire has no payment record of its own, so it is counted
    from the bookings a manager has accepted.
    """
    since = timezone.now() - timedelta(days=RECENT_DAYS)
    paid = Payment.objects.filter(payment_status='completed')
    hired = VenueBooking.objects.filter(status__in=HELD)

    tickets = {'count': paid.count(), 'amount': _total(paid, 'amount')}
    venues = {'count': hired.count(), 'amount': _total(hired, 'total_amount')}
    recent_tickets = _total(paid.filter(paid_at__gte=since), 'amount')
    recent_venues = _total(hired.filter(booking_date__gte=since), 'total_amount')

    return {
        'tickets': tickets,
        'venues': venues,
        'total': tickets['amount'] + venues['amount'],
        'recent': recent_tickets + recent_venues,
        'recent_days': RECENT_DAYS,
        'awaiting': _total(Payment.objects.filter(payment_status__in=['pending', 'processing']), 'amount'),
        'top_events': _top_events(),
        'top_venues': _top_venues(),
    }


def _total(queryset, field):
    return queryset.aggregate(total=Sum(field))['total'] or 0


def _top_events():
    """The events that have taken the most, with nothing earned left out."""
    events = Event.objects.annotate(
        taken=Sum('bookings__payment__amount', filter=Q(bookings__payment__payment_status='completed')),
    ).filter(taken__gt=0).select_related('organizer').order_by('-taken')
    return events[:TOP]


def _top_venues():
    venues = Venue.objects.annotate(
        taken=Sum('bookings__total_amount', filter=Q(bookings__status__in=HELD)),
    ).filter(taken__gt=0).select_related('manager').order_by('-taken')
    return venues[:TOP]
