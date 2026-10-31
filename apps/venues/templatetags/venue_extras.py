from django import template
from apps.venues.models import VenueCommentLike

register = template.Library()

@register.filter
def is_liked_by(comment, user):
    """Check if a comment is liked by a specific user"""
    if user.is_authenticated:
        return comment.is_liked_by_user(user)
    return False

@register.filter
def role_designation(user_profile):
    """Get proper role designation for display"""
    role_designations = {
        'basic_user': 'User',
        'event_manager': 'Event Manager',
        'venue_manager': 'Venue Manager', 
        'admin': 'Administrator',
    }
    return role_designations.get(user_profile.role, user_profile.role.replace('_', ' ').title())