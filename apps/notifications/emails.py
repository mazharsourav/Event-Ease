"""Email that goes out alongside an in-app notification.

A booking must never fail because a mail server is down, so every send here is wrapped:
the failure is logged and the booking stands.
"""
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def _send(subject, template, context, recipient):
    if not recipient:
        logger.info('No email address on file; skipping "%s"', subject)
        return False
    try:
        send_mail(
            subject=subject,
            message=render_to_string(template, context),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=False,
        )
        return True
    except Exception:
        # Logged rather than raised: the booking it belongs to has already been paid for.
        logger.exception('Could not send "%s" to %s', subject, recipient)
        return False


def send_event_booking_confirmation(booking):
    """Tell the attendee their place is booked, with what they need on the day."""
    recipient = booking.attendee_email or booking.user.email
    return _send(
        subject=f'Your booking for {booking.event.title}',
        template='emails/event_booking_confirmed.txt',
        context={'booking': booking, 'event': booking.event, 'user': booking.user},
        recipient=recipient,
    )


def send_venue_booking_decision(booking):
    """Tell the person who asked for a venue whether they got it."""
    return _send(
        subject=f'Your booking request for {booking.venue.name}',
        template='emails/venue_booking_decision.txt',
        context={'booking': booking, 'venue': booking.venue, 'user': booking.user},
        recipient=booking.contact_email or booking.user.email,
    )
