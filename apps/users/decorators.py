from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.core.exceptions import PermissionDenied

def role_required(allowed_roles):
    """
    Decorator to check if user has the required role.
    Usage: @role_required(['admin', 'event_manager'])
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                messages.error(request, 'You must be logged in to access this page.')
                return redirect('users:login')
            
            try:
                user_role = request.user.profile.role
            except:
                messages.error(request, 'User profile not found.')
                return redirect('users:profile')
            
            # Superusers always have access
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            
            # Check if user role is in allowed roles
            if user_role not in allowed_roles:
                messages.error(request, f'You need {" or ".join(allowed_roles)} privileges to access this page.')
                return redirect('home')
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

def admin_required(view_func):
    """
    Decorator to check if user is admin or superuser.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, 'You must be logged in to access this page.')
            return redirect('users:login')
        
        if not (request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile.role == 'admin')):
            messages.error(request, 'You need admin privileges to access this page.')
            return redirect('home')
        
        return view_func(request, *args, **kwargs)
    return wrapper

def venue_manager_required(view_func):
    """
    Decorator to check if user is venue manager, admin, or superuser.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, 'You must be logged in to access this page.')
            return redirect('users:login')
        
        allowed_roles = ['admin', 'venue_manager']
        user_role = getattr(request.user.profile, 'role', None) if hasattr(request.user, 'profile') else None
        
        if not (request.user.is_superuser or user_role in allowed_roles):
            messages.error(request, 'You need venue manager or admin privileges to access this page.')
            return redirect('home')
        
        return view_func(request, *args, **kwargs)
    return wrapper

def event_manager_required(view_func):
    """
    Decorator to check if user is event manager, admin, or superuser.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, 'You must be logged in to access this page.')
            return redirect('users:login')
        
        allowed_roles = ['admin', 'event_manager']
        user_role = getattr(request.user.profile, 'role', None) if hasattr(request.user, 'profile') else None
        
        if not (request.user.is_superuser or user_role in allowed_roles):
            messages.error(request, 'You need event manager or admin privileges to access this page.')
            return redirect('home')
        
        return view_func(request, *args, **kwargs)
    return wrapper
