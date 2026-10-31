from django import template
from apps.events.models import EventCommentLike

register = template.Library()

@register.filter
def is_liked_by(comment, user):
    """Check if a comment is liked by a specific user"""
    if user.is_authenticated:
        return comment.is_liked_by_user(user)
    return False