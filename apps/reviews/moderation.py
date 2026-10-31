"""Every review on the site in one list, for the admin moderation page.

The three review models have different shapes - an event review, a venue review and a review
of EventEase itself - so they are flattened here into rows that read the same. Keeping this
beside the models means the admin view stays a view.
"""
from django.db.models import Q

from .models import EventReview, Review, VenueReview

KIND_LABELS = {'event': 'Event', 'venue': 'Venue', 'site': 'EventEase'}


def counts():
    """How many reviews there are of each kind, for the page's stat cards."""
    event, venue, site = EventReview.objects.count(), VenueReview.objects.count(), Review.objects.count()
    return {'event': event, 'venue': venue, 'site': site, 'total': event + venue + site}


def search_reviews(kind='all', query=''):
    """Reviews of one kind or all three, newest first, narrowed by a search."""
    rows = []
    if kind in ('all', 'event'):
        rows += [_row(review, 'event', review.event.title, review.event_id) for review in _events(query)]
    if kind in ('all', 'venue'):
        rows += [_row(review, 'venue', review.venue.name, review.venue_id) for review in _venues(query)]
    if kind in ('all', 'site'):
        rows += [_row(review, 'site', 'EventEase', None) for review in _site(query)]

    rows.sort(key=lambda row: row['created_at'], reverse=True)
    return rows


def delete_review(kind, review_id):
    """Remove one review. Returns what it was about, or None if there was nothing to remove."""
    models = {'event': EventReview, 'venue': VenueReview, 'site': Review}
    if kind not in models:
        return None

    review = models[kind].objects.filter(pk=review_id).first()
    if review is None:
        return None

    about = {'event': lambda: review.event.title, 'venue': lambda: review.venue.name,
             'site': lambda: 'EventEase'}[kind]()
    review.delete()
    return about


def _row(review, kind, about, about_id):
    return {
        'id': review.pk,
        'kind': kind,
        'kind_label': KIND_LABELS[kind],
        'about': about,
        'about_id': about_id,
        'user': review.user,
        'rating': review.rating,
        'title': review.title,
        # Event and venue reviews call the body "comment"; a review of the site calls it "content".
        'body': getattr(review, 'comment', None) or getattr(review, 'content', ''),
        'created_at': review.created_at,
    }


def _events(query):
    reviews = EventReview.objects.select_related('user', 'event')
    if query:
        reviews = reviews.filter(_words(query) | Q(event__title__icontains=query) | Q(comment__icontains=query))
    return reviews


def _venues(query):
    reviews = VenueReview.objects.select_related('user', 'venue')
    if query:
        reviews = reviews.filter(_words(query) | Q(venue__name__icontains=query) | Q(comment__icontains=query))
    return reviews


def _site(query):
    reviews = Review.objects.select_related('user')
    if query:
        reviews = reviews.filter(_words(query) | Q(content__icontains=query))
    return reviews


def _words(query):
    """The parts of a search that mean the same thing for all three kinds."""
    return (Q(title__icontains=query) | Q(user__username__icontains=query)
            | Q(user__first_name__icontains=query) | Q(user__last_name__icontains=query))
