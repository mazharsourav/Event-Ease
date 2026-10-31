"""Template tags shared by every page."""
from django import template
from django.conf import settings
from django.templatetags.static import static

register = template.Library()


@register.simple_tag
def asset(path):
    """URL of a static file with the release version appended, so browsers reload it after a change.

    Usage: {% asset 'css/core/base.css' %}
    """
    return f'{static(path)}?v={settings.ASSET_VERSION}'


ROLE_LABELS = {
    'basic_user': 'Member',
    'event_manager': 'Organiser',
    'venue_manager': 'Venue manager',
    'admin': 'Admin',
}


RATING_LABELS = {
    'organization': 'Organisation',
    'venue': 'Venue',
    'value': 'Value for money',
    'ambience': 'Ambience',
    'service': 'Service',
    'cleanliness': 'Cleanliness',
}


@register.filter
def rating_label(key):
    """Reader-facing name for a review category key such as 'organization'."""
    return RATING_LABELS.get(key, str(key).replace('_', ' ').capitalize())


@register.filter
def is_liked_by(comment, user):
    """True when `user` has liked the comment (event and venue comments share this)."""
    return user.is_authenticated and comment.is_liked_by_user(user)


@register.filter
def role_label(profile):
    """Short public name for a profile's role."""
    role = getattr(profile, 'role', '') or ''
    return ROLE_LABELS.get(role, role.replace('_', ' ').title())


@register.filter
def initials(user):
    """Up to two capital letters for an avatar placeholder."""
    name = (user.get_full_name() or user.username or '').split()
    letters = ''.join(part[0] for part in name[:2])
    return (letters or '?').upper()


@register.filter
def page_window(page_obj):
    """Page numbers to show in a pager: the current page and its neighbours, the ends, and '…' between."""
    return page_obj.paginator.get_elided_page_range(page_obj.number, on_each_side=1, on_ends=1)
