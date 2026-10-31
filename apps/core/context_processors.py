"""Context shared by every template: the site navigation and the "list your event or venue" targets."""
from django.urls import reverse

EVENT_ROLES = ('admin', 'event_manager')
VENUE_ROLES = ('admin', 'venue_manager')


def _role(user):
    """The user's profile role, or '' for anonymous users and accounts without a profile."""
    if not user.is_authenticated:
        return ''
    profile = getattr(user, 'profile', None)
    return getattr(profile, 'role', '') or ''


def _link(request, label, url):
    # '/' would match every page, so only deeper sections can be "current"
    current = url != '/' and request.path.startswith(url)
    return {'label': label, 'url': url, 'current': current}


def site_frame(request):
    user = request.user
    role = _role(user)
    can_list_event = role in EVENT_ROLES
    can_list_venue = role in VENUE_ROLES

    links = [
        _link(request, 'Events', reverse('events:event_list')),
        _link(request, 'Venues', reverse('venues:venue_list')),
        _link(request, 'Blog', reverse('blog:blog_list')),
    ]
    if can_list_event:
        links.append(_link(request, 'Create event', reverse('events:event_create')))
    if can_list_venue:
        links.append(_link(request, 'Add venue', reverse('venues:venue_create')))

    # Visitors are sent to sign up; signed-in members without the role apply for an upgrade
    if not user.is_authenticated:
        list_event_url = list_venue_url = reverse('users:signup')
    else:
        upgrade_url = reverse('users:request_upgrade')
        list_event_url = reverse('events:event_create') if can_list_event else upgrade_url
        list_venue_url = reverse('venues:venue_create') if can_list_venue else upgrade_url

    return {
        'nav_links': links,
        'list_event_url': list_event_url,
        'list_venue_url': list_venue_url,
        'can_list': can_list_event or can_list_venue,
    }
