from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Sum, Count, Q
from django.utils import timezone
from .models import UserProfile, RoleUpgradeRequest, FriendRequest, Friendship, Message, MessageFile
from apps.events.models import EventBooking
from apps.payments.reporting import platform_revenue
from apps.reviews import moderation as review_moderation
from apps.venues.models import VenueBooking
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.http import JsonResponse, HttpResponseForbidden, HttpResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
import os
from io import BytesIO

def user_login(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        
        # Try the username first, then treat what was typed as an email address.
        user = authenticate(request, username=username, password=password)
        if user is None and username:
            # Signup keeps addresses unique, but accounts made before that rule, or through
            # the Django admin, can still share one. Try each rather than crashing on the second.
            for match in User.objects.filter(email__iexact=username):
                user = authenticate(request, username=match.username, password=password)
                if user is not None:
                    break
        
        if user is not None:
            login(request, user)
            messages.success(request, 'Welcome back!')
            return redirect('home')
        else:
            messages.error(request, 'Invalid username/email or password.')
    
    return render(request, 'users/login.html')

def user_signup(request):
    if request.method == 'POST':
        first_name = request.POST['first_name']
        last_name = request.POST['last_name']
        username = request.POST['username']
        email = request.POST['email']
        password1 = request.POST['password1']
        password2 = request.POST['password2']
        
        # Validation
        if password1 != password2:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'users/signup.html')
        
        if len(password1) < 8:
            messages.error(request, 'Password must be at least 8 characters long.')
            return render(request, 'users/signup.html')

        # Django does not make User.email unique, but a password reset is sent to an address,
        # so one address has to mean one account.
        if User.objects.filter(email__iexact=email).exists():
            messages.error(request, 'An account already uses that email address. Log in, or reset your password.')
            return render(request, 'users/signup.html')

        if User.objects.filter(username__iexact=username).exists():
            messages.error(request, 'That username is taken. Please pick another.')
            return render(request, 'users/signup.html')

        try:
            # Create user with basic_user role by default
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password1,
                first_name=first_name,
                last_name=last_name
            )
            
            # User profile is automatically created with basic_user role by default
            
            # Auto-login the user
            login(request, user)
            messages.success(request, f'Account created successfully! Welcome to EventEase.')
            return redirect('home')
            
        except IntegrityError:
            messages.error(request, 'Username or email already exists.')
    
    return render(request, 'users/signup.html')

def user_logout(request):
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('home')

@login_required
def user_profile(request):
    if request.method == 'POST':
        # Handle profile update
        user = request.user
        profile = user.profile
        
        # Update user fields
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        user.email = request.POST.get('email', user.email)
        
        # Update profile fields
        profile.phone = request.POST.get('phone', profile.phone)
        profile.address = request.POST.get('address', profile.address)
        profile.bio = request.POST.get('bio', profile.bio)
        
        # Handle avatar upload
        if 'avatar' in request.FILES:
            avatar_file = request.FILES['avatar']
            
            # Validate file size (5MB limit)
            if avatar_file.size > 5 * 1024 * 1024:
                messages.error(request, 'Profile picture must be less than 5MB.')
                return redirect('users:profile')
            
            # Validate file type
            allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif']
            if avatar_file.content_type not in allowed_types:
                messages.error(request, 'Please upload a valid image file (JPG, PNG, or GIF).')
                return redirect('users:profile')
            
            # Delete old avatar if exists
            if profile.avatar:
                if default_storage.exists(profile.avatar.name):
                    default_storage.delete(profile.avatar.name)
            
            # Save new avatar
            profile.avatar = avatar_file
        
        try:
            user.save()
            profile.save()
            messages.success(request, 'Profile updated successfully!')
        except Exception as e:
            messages.error(request, f'Error updating profile: {str(e)}')
        
        return redirect('users:profile')
    
    # Get pending upgrade request for current user
    pending_request = RoleUpgradeRequest.objects.filter(
        user=request.user, 
        status='pending'
    ).first()
    
    context = {
        'pending_request': pending_request
    }
    return render(request, 'users/profile.html', context)

# Helper function to check if user is admin
def is_admin(user):
    return user.is_authenticated and (user.is_superuser or user.profile.role == 'admin')

@login_required
def request_role_upgrade(request):
    # Check if user already has a pending request
    existing_request = RoleUpgradeRequest.objects.filter(
        user=request.user, 
        status='pending'
    ).first()
    
    if existing_request:
        messages.warning(request, 'You already have a pending role upgrade request.')
        return redirect('users:profile')
    
    if request.method == 'POST':
        requested_role = request.POST.get('requested_role')
        reason = request.POST.get('reason')
        company_name = request.POST.get('company_name', '')
        experience = request.POST.get('experience', '')
        portfolio = request.POST.get('portfolio', '')
        phone = request.POST.get('phone', '')
        address = request.POST.get('address', '')
        
        # Validate that the requested role is valid and not basic_user or admin
        valid_roles = ['event_manager', 'venue_manager']
        if requested_role not in valid_roles:
            messages.error(request, 'Invalid role selection.')
            return render(request, 'users/request_upgrade.html')
        
        # Create the upgrade request
        RoleUpgradeRequest.objects.create(
            user=request.user,
            requested_role=requested_role,
            reason=reason,
            company_name=company_name,
            experience=experience,
            portfolio=portfolio,
            phone=phone,
            address=address
        )
        
        messages.success(request, 'Your role upgrade request has been submitted successfully!')
        return redirect('users:profile')
    
    return render(request, 'users/request_upgrade.html')

@user_passes_test(is_admin)
def admin_dashboard(request):
    if not is_admin(request.user):
        return HttpResponseForbidden("You don't have permission to access this page.")
    
    from apps.events.models import Event, EventBooking, EventComment
    from apps.venues.models import Venue, VenueBooking, VenueComment
    from apps.reviews.models import EventReview, Review, VenueReview
    from django.db.models import Count, Q, Avg
    from django.contrib.auth.models import User
    
    # Role upgrade requests (existing functionality)
    pending_requests = RoleUpgradeRequest.objects.filter(status='pending').order_by('-created_at')
    approved_requests = RoleUpgradeRequest.objects.filter(status='approved').order_by('-updated_at')[:10]
    rejected_requests = RoleUpgradeRequest.objects.filter(status='rejected').order_by('-updated_at')[:10]
    
    # Users with detailed activity statistics
    users_with_stats = User.objects.select_related('profile').annotate(
        # Event statistics
        events_posted=Count('organized_events', distinct=True),
        event_bookings_received=Count('organized_events__bookings', distinct=True),
        
        # Venue statistics
        venues_posted=Count('managed_venues', distinct=True),
        venue_bookings_received=Count('managed_venues__bookings', distinct=True),
        
        # Review statistics
        event_reviews_given=Count('event_reviews', distinct=True),
        venue_reviews_given=Count('venue_reviews', distinct=True),
        
        # Comment statistics
        event_comments_posted=Count('event_comments', distinct=True),
        venue_comments_posted=Count('venue_comments', distinct=True),
        
        # Booking statistics as customer
        event_bookings_made=Count('event_bookings', distinct=True),
        venue_bookings_made=Count('venue_bookings', distinct=True)
    ).order_by('-date_joined')
    
    # Overall platform statistics
    total_users = User.objects.count()
    total_events = Event.objects.count()
    total_venues = Venue.objects.count()
    total_event_reviews = EventReview.objects.count()
    total_venue_reviews = VenueReview.objects.count()
    total_site_reviews = Review.objects.count()
    total_event_comments = EventComment.objects.count()
    total_venue_comments = VenueComment.objects.count()
    total_event_bookings = EventBooking.objects.count()
    total_venue_bookings = VenueBooking.objects.count()
    
    # Top performers statistics
    top_event_creators = User.objects.annotate(
        event_count=Count('organized_events')
    ).filter(event_count__gt=0).order_by('-event_count')[:5]
    
    top_venue_creators = User.objects.annotate(
        venue_count=Count('managed_venues')
    ).filter(venue_count__gt=0).order_by('-venue_count')[:5]
    
    # Event and Venue stats with reviews and comments
    events_with_stats = Event.objects.annotate(
        review_total=Count('reviews', distinct=True),
        comment_total=Count('comments', distinct=True),
        avg_rating=Avg('reviews__rating'),
        booking_total=Count('bookings', distinct=True)
    ).select_related('organizer').order_by('-created_at')[:10]
    
    venues_with_stats = Venue.objects.annotate(
        review_total=Count('reviews', distinct=True),
        comment_total=Count('comments', distinct=True),
        avg_rating=Avg('reviews__rating'),
        booking_total=Count('bookings', distinct=True)
    ).select_related('manager').order_by('-created_at')[:10]
    
    # Recent activity
    recent_event_reviews = EventReview.objects.select_related('user', 'event').order_by('-created_at')[:5]
    recent_venue_reviews = VenueReview.objects.select_related('user', 'venue').order_by('-created_at')[:5]
    
    context = {
        # Existing role upgrade data
        'pending_requests': pending_requests,
        'approved_requests': approved_requests,
        'rejected_requests': rejected_requests,
        
        # User management data
        'users_with_stats': users_with_stats,
        'total_users': total_users,
        
        # Platform statistics
        'total_events': total_events,
        'total_venues': total_venues,
        'total_event_reviews': total_event_reviews,
        'total_venue_reviews': total_venue_reviews,
        'total_site_reviews': total_site_reviews,
        'total_event_comments': total_event_comments,
        'total_venue_comments': total_venue_comments,
        'total_event_bookings': total_event_bookings,
        'total_venue_bookings': total_venue_bookings,
        
        # Top performers
        'top_event_creators': top_event_creators,
        'top_venue_creators': top_venue_creators,
        
        # Content with stats
        'events_with_stats': events_with_stats,
        'venues_with_stats': venues_with_stats,
        
        # Recent activity
        'recent_event_reviews': recent_event_reviews,
        'recent_venue_reviews': recent_venue_reviews,

        # What the platform has taken
        'revenue': platform_revenue(),
    }
    return render(request, 'users/enhanced_admin_dashboard.html', context)

@user_passes_test(is_admin)
def view_upgrade_request(request, request_id):
    if not is_admin(request.user):
        return HttpResponseForbidden("You don't have permission to access this page.")
    
    upgrade_request = get_object_or_404(RoleUpgradeRequest, id=request_id)
    return render(request, 'users/view_upgrade_request.html', {'upgrade_request': upgrade_request})

@user_passes_test(is_admin)
def process_upgrade_request(request, request_id):
    if not is_admin(request.user):
        return HttpResponseForbidden("You don't have permission to access this page.")
    
    if request.method == 'POST':
        upgrade_request = get_object_or_404(RoleUpgradeRequest, id=request_id)
        action = request.POST.get('action')
        
        if action == 'approve':
            # Update user role
            upgrade_request.user.profile.role = upgrade_request.requested_role
            upgrade_request.user.profile.save()
            
            # Update request status
            upgrade_request.status = 'approved'
            upgrade_request.reviewed_by = request.user
            upgrade_request.save()
            
            messages.success(request, f'Role upgrade approved for {upgrade_request.user.username}.')
            
        elif action == 'reject':
            upgrade_request.status = 'rejected'
            upgrade_request.reviewed_by = request.user
            upgrade_request.save()
            
            messages.success(request, f'Role upgrade rejected for {upgrade_request.user.username}.')
        
        return redirect('users:admin_dashboard')
    
    return redirect('users:admin_dashboard')

@login_required
def user_dashboard(request):
    """User dashboard with booking statistics and management"""
    user = request.user
    now = timezone.now()
    
    # Get all user's event bookings with related event data
    event_bookings = EventBooking.objects.filter(user=user).select_related('event').order_by('-booking_date')
    
    # Get all user's venue bookings with related venue data
    venue_bookings = VenueBooking.objects.filter(user=user).select_related('venue').order_by('-booking_date')
    
    # Calculate statistics
    total_events = event_bookings.count()
    total_venues = venue_bookings.count()
    
    # Calculate total spent
    event_spent = event_bookings.aggregate(
        total=Sum('total_amount')
    )['total'] or 0
    
    venue_spent = venue_bookings.aggregate(
        total=Sum('total_amount')
    )['total'] or 0
    
    total_spent = event_spent + venue_spent
    total_bookings = total_events + total_venues
    
    # Categorize bookings for new structure
    # Events - upcoming vs past based on event start_date
    upcoming_events = event_bookings.filter(
        event__start_date__gte=now,
        status__in=['pending', 'confirmed']
    ).order_by('event__start_date')
    
    past_events = event_bookings.filter(
        event__start_date__lt=now
    ).order_by('-event__start_date')
    
    # Add review context for past events
    for booking in past_events:
        # Check if user can review this event (completed and not already reviewed)
        from apps.reviews.models import EventReview
        booking.can_review = (
            booking.event.can_be_reviewed and 
            booking.status in ['confirmed', 'paid'] and
            not EventReview.objects.filter(event=booking.event, user=user).exists()
        )
        
        # Check if user has already reviewed this event
        booking.user_review = EventReview.objects.filter(
            event=booking.event, 
            user=user
        ).first()
    
    # Venues - upcoming vs past
    upcoming_venues = venue_bookings.filter(
        end_date__gte=now,
        status__in=['pending', 'confirmed']
    ).order_by('start_date')
    
    past_venues = venue_bookings.filter(
        end_date__lt=now
    ).order_by('-start_date')
    
    # Add review context for past venues
    for booking in past_venues:
        from apps.reviews.models import VenueReview
        # Check if user can review this venue (completed and not already reviewed)
        has_existing_review = VenueReview.objects.filter(venue=booking.venue, user=user).exists()
        booking.can_review = (
            booking.status in ['confirmed', 'completed'] and
            booking.end_date < now and  # Booking must be completed
            not has_existing_review
        )
        

        
        # Check if user has already reviewed this venue
        booking.user_review = VenueReview.objects.filter(
            venue=booking.venue, 
            user=user
        ).first()
    
    # Venues by status (all time)
    confirmed_venues = venue_bookings.filter(
        status='confirmed'
    ).order_by('start_date')
    
    # Add review context for confirmed venues
    for booking in confirmed_venues:
        from apps.reviews.models import VenueReview
        # Check if booking is completed (end date has passed)
        booking_completed = booking.end_date < now
        
        # Check if user has already reviewed this venue
        booking.user_review = VenueReview.objects.filter(
            venue=booking.venue, 
            user=user
        ).first()
        
        # User can review if booking is completed and no existing review
        booking.can_review = booking_completed and not booking.user_review
        
        # Set review status message
        if not booking_completed:
            booking.review_status = "Please wait for the event to end"
        elif booking.user_review:
            booking.review_status = "You have reviewed this venue"
        else:
            booking.review_status = "You can review this venue"
    
    pending_venues = venue_bookings.filter(
        status='pending'
    ).order_by('start_date')
    
    cancelled_venues = venue_bookings.filter(
        status__in=['cancelled', 'rejected']
    ).order_by('-start_date')
    
    context = {
        # Stats for overview cards
        'total_events': total_events,
        'total_venues': total_venues,
        'total_spent': total_spent,
        'total_bookings': total_bookings,
        
        # Event tabs
        'upcoming_events': upcoming_events,
        'past_events': past_events,
        
        # Venue tabs
        'upcoming_venues': upcoming_venues,
        'past_venues': past_venues,
        'confirmed_venues': confirmed_venues,
        'pending_venues': pending_venues,
        'cancelled_venues': cancelled_venues,
        
        # Legacy fields for compatibility
        'event_bookings': event_bookings,
        'venue_bookings': venue_bookings,
    }
    
    return render(request, 'users/dashboard.html', context)

@login_required
def cancel_booking(request):
    """Cancel a booking via POST form"""
    if request.method == 'POST':
        booking_type = request.POST.get('booking_type')
        booking_id = request.POST.get('booking_id')
        
        try:
            if booking_type == 'event':
                booking = EventBooking.objects.get(id=booking_id, user=request.user)
                if booking.status in ['pending', 'confirmed']:
                    booking.status = 'cancelled'
                    booking.save()
                    messages.success(request, f'Event booking for "{booking.event.title}" has been cancelled.')
                else:
                    messages.error(request, 'This booking cannot be cancelled.')
            elif booking_type == 'venue':
                booking = VenueBooking.objects.get(id=booking_id, user=request.user)
                if booking.status in ['pending', 'confirmed']:
                    booking.status = 'cancelled'
                    booking.save()
                    messages.success(request, f'Venue booking for "{booking.venue.name}" has been cancelled.')
                else:
                    messages.error(request, 'This booking cannot be cancelled.')
                    
        except (EventBooking.DoesNotExist, VenueBooking.DoesNotExist):
            messages.error(request, 'Booking not found or you do not have permission to cancel it.')
        except Exception as e:
            messages.error(request, f'An error occurred: {str(e)}')
    
    return redirect('users:dashboard')

@login_required
def download_event_invoice(request, booking_id):
    """Generate and download PDF invoice for event booking"""
    try:
        booking = EventBooking.objects.get(id=booking_id, user=request.user)
        
        # Create PDF response
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="EventEase_Event_Invoice_{booking.id}.pdf"'
        
        # Create PDF
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        
        # Define styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            textColor=HexColor('#40B5AD'),
            alignment=1  # Center alignment
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            spaceAfter=12,
            textColor=HexColor('#333333')
        )
        
        normal_style = styles['Normal']
        
        # Build PDF content
        content = []
        
        # Title
        content.append(Paragraph("EventEase - Event Booking Invoice", title_style))
        content.append(Spacer(1, 20))
        
        # Invoice details
        content.append(Paragraph("Invoice Details", heading_style))
        invoice_data = [
            ['Invoice Number:', f'EVT-{booking.id:06d}'],
            ['Booking Date:', booking.booking_date.strftime('%B %d, %Y')],
            ['Status:', booking.get_status_display()],
        ]
        
        invoice_table = Table(invoice_data, colWidths=[2*inch, 3*inch])
        invoice_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (0, -1), HexColor('#666666')),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        content.append(invoice_table)
        content.append(Spacer(1, 20))
        
        # Customer details
        content.append(Paragraph("Customer Information", heading_style))
        customer_data = [
            ['Name:', f'{booking.user.first_name} {booking.user.last_name}'],
            ['Email:', booking.user.email],
            ['Username:', booking.user.username],
        ]
        
        customer_table = Table(customer_data, colWidths=[2*inch, 3*inch])
        customer_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (0, -1), HexColor('#666666')),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        content.append(customer_table)
        content.append(Spacer(1, 20))
        
        # Event details
        content.append(Paragraph("Event Information", heading_style))
        event_data = [
            ['Event Title:', booking.event.title],
            ['Event Date:', booking.event.start_date.strftime('%B %d, %Y at %I:%M %p')],
            ['End Date:', booking.event.end_date.strftime('%B %d, %Y at %I:%M %p') if booking.event.end_date else 'N/A'],
            ['Location:', booking.event.venue_name or 'TBA'],
            ['Number of Tickets:', str(booking.attendees_count)],
            ['Price per Ticket:', f'${booking.event.ticket_price:.2f}'],
        ]
        
        event_table = Table(event_data, colWidths=[2*inch, 4*inch])
        event_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (0, -1), HexColor('#666666')),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        content.append(event_table)
        content.append(Spacer(1, 20))
        
        # Payment summary
        content.append(Paragraph("Payment Summary", heading_style))
        payment_data = [
            ['Subtotal:', f'${booking.event.ticket_price * booking.attendees_count:.2f}'],
            ['Total Amount:', f'${booking.total_amount:.2f}'],
        ]
        
        payment_table = Table(payment_data, colWidths=[2*inch, 3*inch])
        payment_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (0, -1), HexColor('#666666')),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, -1), (-1, -1), 12),
            ('TEXTCOLOR', (0, -1), (-1, -1), HexColor('#40B5AD')),
            ('LINEABOVE', (0, -1), (-1, -1), 2, HexColor('#40B5AD')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        content.append(payment_table)
        content.append(Spacer(1, 30))
        
        # Footer
        footer_text = "Thank you for choosing EventEase! For any questions about this invoice, please contact our support team."
        content.append(Paragraph(footer_text, normal_style))
        
        # Build PDF
        doc.build(content)
        
        # Get PDF data
        pdf_data = buffer.getvalue()
        buffer.close()
        
        response.write(pdf_data)
        return response
        
    except EventBooking.DoesNotExist:
        messages.error(request, 'Event booking not found.')
        return redirect('users:dashboard')
    except Exception as e:
        messages.error(request, f'Error generating invoice: {str(e)}')
        return redirect('users:dashboard')

@login_required
def download_venue_invoice(request, booking_id):
    """Generate and download PDF invoice for venue booking"""
    try:
        booking = VenueBooking.objects.get(id=booking_id, user=request.user)
        
        # Create PDF response
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="EventEase_Venue_Invoice_{booking.id}.pdf"'
        
        # Create PDF
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        
        # Define styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            textColor=HexColor('#40B5AD'),
            alignment=1  # Center alignment
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            spaceAfter=12,
            textColor=HexColor('#333333')
        )
        
        normal_style = styles['Normal']
        
        # Build PDF content
        content = []
        
        # Title
        content.append(Paragraph("EventEase - Venue Booking Invoice", title_style))
        content.append(Spacer(1, 20))
        
        # Invoice details
        content.append(Paragraph("Invoice Details", heading_style))
        invoice_data = [
            ['Invoice Number:', f'VEN-{booking.id:06d}'],
            ['Booking Date:', booking.booking_date.strftime('%B %d, %Y')],
            ['Status:', booking.get_status_display()],
        ]
        
        invoice_table = Table(invoice_data, colWidths=[2*inch, 3*inch])
        invoice_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (0, -1), HexColor('#666666')),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        content.append(invoice_table)
        content.append(Spacer(1, 20))
        
        # Customer details
        content.append(Paragraph("Customer Information", heading_style))
        customer_data = [
            ['Name:', f'{booking.user.first_name} {booking.user.last_name}'],
            ['Email:', booking.user.email],
            ['Username:', booking.user.username],
        ]
        
        customer_table = Table(customer_data, colWidths=[2*inch, 3*inch])
        customer_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (0, -1), HexColor('#666666')),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        content.append(customer_table)
        content.append(Spacer(1, 20))
        
        # Venue details
        content.append(Paragraph("Venue Information", heading_style))
        venue_data = [
            ['Venue Name:', booking.venue.name],
            ['Event Title:', booking.event_title],
            ['Start Date:', booking.start_date.strftime('%B %d, %Y')],
            ['End Date:', booking.end_date.strftime('%B %d, %Y')],
            ['Address:', f'{booking.venue.address}, {booking.venue.city}, {booking.venue.state}'],
            ['Capacity:', str(booking.venue.capacity)],
        ]
        
        venue_table = Table(venue_data, colWidths=[2*inch, 4*inch])
        venue_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (0, -1), HexColor('#666666')),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        content.append(venue_table)
        content.append(Spacer(1, 20))
        
        # Payment summary
        content.append(Paragraph("Payment Summary", heading_style))
        payment_data = [
            ['Total Amount:', f'${booking.total_amount:.2f}'],
        ]
        
        payment_table = Table(payment_data, colWidths=[2*inch, 3*inch])
        payment_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('TEXTCOLOR', (0, 0), (0, -1), HexColor('#666666')),
            ('TEXTCOLOR', (0, 0), (-1, -1), HexColor('#40B5AD')),
            ('LINEABOVE', (0, 0), (-1, -1), 2, HexColor('#40B5AD')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        content.append(payment_table)
        content.append(Spacer(1, 30))
        
        # Footer
        footer_text = "Thank you for choosing EventEase! For any questions about this invoice, please contact our support team."
        content.append(Paragraph(footer_text, normal_style))
        
        # Build PDF
        doc.build(content)
        
        # Get PDF data
        pdf_data = buffer.getvalue()
        buffer.close()
        
        response.write(pdf_data)
        return response
        
    except VenueBooking.DoesNotExist:
        messages.error(request, 'Venue booking not found.')
        return redirect('users:dashboard')
    except Exception as e:
        messages.error(request, f'Error generating invoice: {str(e)}')
        return redirect('users:dashboard')


@user_passes_test(is_admin)
def admin_comments_management(request):
    """Admin page to view and manage all comments from events and venues"""
    if not is_admin(request.user):
        return HttpResponseForbidden("You don't have permission to access this page.")
    
    from apps.events.models import EventComment
    from apps.venues.models import VenueComment
    from django.db.models import Q
    
    # Get search query if provided
    search_query = request.GET.get('search', '')
    comment_type = request.GET.get('type', 'all')
    
    # Get all event comments
    event_comments = EventComment.objects.select_related('user', 'event').all()
    if search_query:
        event_comments = event_comments.filter(
            Q(comment__icontains=search_query) |
            Q(event__title__icontains=search_query) |
            Q(user__username__icontains=search_query) |
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query)
        )
    
    # Get all venue comments
    venue_comments = VenueComment.objects.select_related('user', 'venue').all()
    if search_query:
        venue_comments = venue_comments.filter(
            Q(comment__icontains=search_query) |
            Q(venue__name__icontains=search_query) |
            Q(user__username__icontains=search_query) |
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query)
        )
    
    # Combine comments with type indicators
    all_comments = []
    
    if comment_type in ['all', 'event']:
        for comment in event_comments.order_by('-created_at'):
            all_comments.append({
                'id': comment.id,
                'type': 'event',
                'content_name': comment.event.title,
                'content_id': comment.event.id,
                'user': comment.user,
                'comment': comment.comment,
                'created_at': comment.created_at,
                'has_image': bool(comment.image),
                'image': comment.image,
                'image_url': comment.image.url if comment.image else None,
                'is_reply': comment.parent is not None,
                'parent_id': comment.parent.id if comment.parent else None,
            })
    
    if comment_type in ['all', 'venue']:
        for comment in venue_comments.order_by('-created_at'):
            all_comments.append({
                'id': comment.id,
                'type': 'venue',
                'content_name': comment.venue.name,
                'content_id': comment.venue.id,
                'user': comment.user,
                'comment': comment.comment,
                'created_at': comment.created_at,
                'has_image': bool(comment.image),
                'image': comment.image,
                'image_url': comment.image.url if comment.image else None,
                'is_reply': comment.parent is not None,
                'parent_id': comment.parent.id if comment.parent else None,
            })
    
    # Sort all comments by creation date
    all_comments.sort(key=lambda x: x['created_at'], reverse=True)
    
    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(all_comments, 20)  # Show 20 comments per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Statistics
    total_event_comments = EventComment.objects.count()
    total_venue_comments = VenueComment.objects.count()
    total_comments = total_event_comments + total_venue_comments
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'comment_type': comment_type,
        'total_comments': total_comments,
        'total_event_comments': total_event_comments,
        'total_venue_comments': total_venue_comments,
    }
    
    return render(request, 'users/admin_comments_management.html', context)


@user_passes_test(is_admin)
def admin_reviews_management(request):
    """Admin page for every review on the site: events, venues and EventEase itself."""
    if not is_admin(request.user):
        return HttpResponseForbidden("You don't have permission to access this page.")

    search_query = request.GET.get('search', '').strip()
    review_type = request.GET.get('type', 'all')
    if review_type not in ['all', 'event', 'venue', 'site']:
        review_type = 'all'

    reviews = review_moderation.search_reviews(review_type, search_query)
    page_obj = Paginator(reviews, 20).get_page(request.GET.get('page'))

    return render(request, 'users/admin_reviews_management.html', {
        'page_obj': page_obj,
        'search_query': search_query,
        'review_type': review_type,
        'counts': review_moderation.counts(),
    })


@user_passes_test(is_admin)
def delete_review(request):
    """Remove a review of an event, a venue or the site itself."""
    if not is_admin(request.user):
        return HttpResponseForbidden("You don't have permission to access this page.")

    if request.method == 'POST':
        about = review_moderation.delete_review(request.POST.get('review_type'), request.POST.get('review_id'))
        if about:
            messages.success(request, f'The review of "{about}" has been deleted.')
        else:
            messages.error(request, 'That review no longer exists.')

    return redirect('users:admin_reviews_management')


@user_passes_test(is_admin)
def delete_comment(request):
    """Delete a comment (event or venue comment)"""
    if not is_admin(request.user):
        return HttpResponseForbidden("You don't have permission to access this page.")
    
    if request.method == 'POST':
        comment_id = request.POST.get('comment_id')
        comment_type = request.POST.get('comment_type')
        
        try:
            if comment_type == 'event':
                from apps.events.models import EventComment
                comment = EventComment.objects.get(id=comment_id)
                event_title = comment.event.title
                comment.delete()
                messages.success(request, f'Event comment on "{event_title}" has been deleted successfully.')
            
            elif comment_type == 'venue':
                from apps.venues.models import VenueComment
                comment = VenueComment.objects.get(id=comment_id)
                venue_name = comment.venue.name
                comment.delete()
                messages.success(request, f'Venue comment on "{venue_name}" has been deleted successfully.')
            
            else:
                messages.error(request, 'Invalid comment type.')
        
        except Exception as e:
            messages.error(request, f'Error deleting comment: {str(e)}')
    
    return redirect('users:admin_comments_management')


# ============================================
# SOCIAL FEATURES - FRIENDS & MESSAGING
# ============================================

@login_required
def search_users(request):
    """Search for users to send friend requests or view profiles"""
    query = request.GET.get('q', '').strip()
    results = []
    
    if query and len(query) >= 2:
        # Search users by username, first name, last name, or email
        results = User.objects.filter(
            Q(username__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(email__icontains=query)
        ).exclude(id=request.user.id).select_related('profile')[:20]
        
        # Add friendship status for each user
        for user in results:
            user.friendship_status = get_friendship_status(request.user, user)
    
    context = {
        'query': query,
        'users': results,  # Changed from 'results' to 'users' to match template
    }
    
    return render(request, 'users/search_users.html', context)


@login_required
def view_user_profile(request, user_id):
    """View another user's profile"""
    viewed_user = get_object_or_404(User, id=user_id)
    
    if viewed_user == request.user:
        # Redirect to own profile if viewing self
        return redirect('users:profile')
    
    friendship_status = get_friendship_status(request.user, viewed_user)
    
    # Count mutual friends
    user_friends = set(Friendship.get_friends(request.user))
    viewed_user_friends = set(Friendship.get_friends(viewed_user))
    mutual_friends = user_friends.intersection(viewed_user_friends)
    
    context = {
        'viewed_user': viewed_user,
        'friendship_status': friendship_status,
        'mutual_friends_count': len(mutual_friends),
    }
    
    return render(request, 'users/view_profile.html', context)


@login_required
def send_friend_request(request, user_id):
    """Send a friend request to another user"""
    if request.method == 'POST':
        to_user = get_object_or_404(User, id=user_id)
        
        if to_user == request.user:
            messages.error(request, "You cannot send a friend request to yourself.")
            return redirect('users:search_users')
        
        # Check if users are already friends
        if Friendship.are_friends(request.user, to_user):
            messages.info(request, f"You are already friends with {to_user.get_full_name() or to_user.username}.")
            return redirect('users:view_user_profile', user_id=user_id)
        
        # Check if friend request already exists
        existing_request = FriendRequest.objects.filter(
            Q(from_user=request.user, to_user=to_user) |
            Q(from_user=to_user, to_user=request.user)
        ).first()
        
        if existing_request:
            if existing_request.status == 'pending':
                messages.info(request, "Friend request is already pending.")
            elif existing_request.status == 'rejected':
                # Allow sending again if previously rejected
                existing_request.from_user = request.user
                existing_request.to_user = to_user
                existing_request.status = 'pending'
                existing_request.save()
                messages.success(request, f"Friend request sent to {to_user.get_full_name() or to_user.username}!")
        else:
            # Create new friend request
            FriendRequest.objects.create(
                from_user=request.user,
                to_user=to_user,
                status='pending'
            )
            messages.success(request, f"Friend request sent to {to_user.get_full_name() or to_user.username}!")
    
    return redirect('users:view_user_profile', user_id=user_id)


@login_required
def friends_page(request):
    """Main friends page showing friends, friend requests, and search"""
    friends = Friendship.get_friends(request.user)
    
    # Get pending friend requests (received)
    pending_requests = FriendRequest.objects.filter(
        to_user=request.user, 
        status='pending'
    ).select_related('from_user')
    
    # Get sent friend requests
    sent_requests = FriendRequest.objects.filter(
        from_user=request.user, 
        status='pending'
    ).select_related('to_user')
    
    # Handle search within friends
    friend_search_query = request.GET.get('friend_search', '').strip()
    if friend_search_query:
        friends = [friend for friend in friends if 
                  friend_search_query.lower() in friend.username.lower() or
                  friend_search_query.lower() in (friend.get_full_name() or '').lower()]
    
    # Handle user search to find new friends
    user_search_query = request.GET.get('user_search', '').strip()
    search_results = []
    if user_search_query:
        # Search for users excluding current user and existing friends
        friend_ids = [friend.id for friend in Friendship.get_friends(request.user)]
        friend_ids.append(request.user.id)  # Exclude self
        
        search_results = User.objects.filter(
            Q(username__icontains=user_search_query) |
            Q(first_name__icontains=user_search_query) |
            Q(last_name__icontains=user_search_query)
        ).exclude(id__in=friend_ids).select_related('profile')[:20]
        
        # Add friendship status for each search result
        for user in search_results:
            user.friendship_status = get_friendship_status(request.user, user)

    context = {
        'friends': friends,
        'pending_requests': pending_requests,
        'sent_requests': sent_requests,
        'friend_search_query': friend_search_query,
        'user_search_query': user_search_query,
        'search_results': search_results,
    }
    
    return render(request, 'users/friends.html', context)


@login_required
def accept_friend_request(request, request_id):
    """Accept a friend request"""
    if request.method == 'POST':
        friend_request = get_object_or_404(
            FriendRequest, 
            id=request_id, 
            to_user=request.user, 
            status='pending'
        )
        
        # Mark request as accepted
        friend_request.status = 'accepted'
        friend_request.save()
        
        # Create friendship (ensure user1.id < user2.id for consistency)
        user1, user2 = (request.user, friend_request.from_user) if request.user.id < friend_request.from_user.id else (friend_request.from_user, request.user)
        Friendship.objects.get_or_create(user1=user1, user2=user2)
        
        messages.success(request, f"You are now friends with {friend_request.from_user.get_full_name() or friend_request.from_user.username}!")
    
    return redirect('users:friends')


@login_required
def reject_friend_request(request, request_id):
    """Reject a friend request"""
    if request.method == 'POST':
        friend_request = get_object_or_404(
            FriendRequest, 
            id=request_id, 
            to_user=request.user, 
            status='pending'
        )
        
        friend_request.status = 'rejected'
        friend_request.save()
        
        messages.info(request, "Friend request rejected.")
    
    return redirect('users:friends')


@login_required
def unfriend_user(request, user_id):
    """Remove a friend"""
    if request.method == 'POST':
        friend_user = get_object_or_404(User, id=user_id)
        
        # Find and delete the friendship
        friendship = Friendship.objects.filter(
            Q(user1=request.user, user2=friend_user) |
            Q(user1=friend_user, user2=request.user)
        ).first()
        
        if friendship:
            friendship.delete()
            messages.success(request, f"You are no longer friends with {friend_user.get_full_name() or friend_user.username}.")
        else:
            messages.error(request, "Friendship not found.")
    
    return redirect('users:friends')


@login_required
@login_required
def messages_page(request):
    """Main messages page showing conversations"""
    conversations = Message.get_recent_conversations(request.user)
    
    context = {
        'conversations': conversations,
    }
    
    return render(request, 'users/messages.html', context)


@login_required
def conversation_view(request, user_id):
    """View conversation with a specific user"""
    other_user = get_object_or_404(User, id=user_id)
    
    # Check if users are friends
    if not Friendship.are_friends(request.user, other_user):
        messages.error(request, "You can only message your friends.")
        return redirect('users:friends')
    
    # Get conversation messages
    messages_list = Message.get_conversation(request.user, other_user)
    
    # Mark messages as read
    Message.objects.filter(
        sender=other_user, 
        receiver=request.user, 
        is_read=False
    ).update(is_read=True)
    
    # Handle sending new message
    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        if content:
            Message.objects.create(
                sender=request.user,
                receiver=other_user,
                content=content
            )
            messages.success(request, "Message sent!")
            return redirect('users:conversation', user_id=user_id)
    
    context = {
        'other_user': other_user,
        'messages_list': messages_list,
    }
    
    return render(request, 'users/conversation.html', context)


def get_friendship_status(user1, user2):
    """Get the friendship status between two users"""
    if Friendship.are_friends(user1, user2):
        return 'friends'
    
    # Check for pending friend requests
    request_from_user1 = FriendRequest.objects.filter(
        from_user=user1, to_user=user2, status='pending'
    ).exists()
    
    request_from_user2 = FriendRequest.objects.filter(
        from_user=user2, to_user=user1, status='pending'
    ).exists()
    
    if request_from_user1:
        return 'request_sent'
    elif request_from_user2:
        return 'request_received'
    else:
        return 'not_friends'


@login_required
def get_unread_counts(request):
    """AJAX endpoint to get unread message and friend request counts"""
    unread_messages = Message.objects.filter(
        receiver=request.user, 
        is_read=False
    ).count()
    
    pending_friend_requests = FriendRequest.objects.filter(
        to_user=request.user, 
        status='pending'
    ).count()
    
    return JsonResponse({
        'unread_messages': unread_messages,
        'pending_friend_requests': pending_friend_requests,
    })


@login_required
def mark_friend_requests_seen(request):
    """AJAX endpoint to mark friend requests as seen when user clicks friends icon"""
    if request.method == 'POST':
        try:
            # Mark all pending friend requests as seen (we can add a 'seen' field later if needed)
            # For now, we'll just return success as the user has seen them
            pending_count = FriendRequest.objects.filter(
                to_user=request.user, 
                status='pending'
            ).count()
            
            return JsonResponse({
                'success': True,
                'message': f'Marked {pending_count} friend requests as seen'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=405)


@login_required  
def mark_messages_read(request):
    """AJAX endpoint to mark messages as read when user clicks messages icon"""
    if request.method == 'POST':
        try:
            # Mark all unread messages as read
            updated_count = Message.objects.filter(
                receiver=request.user, 
                is_read=False
            ).update(is_read=True)
            
            return JsonResponse({
                'success': True,
                'message': f'Marked {updated_count} messages as read'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=405)
@login_required
def api_get_messages(request, user_id):
    """API endpoint to get messages for a conversation"""
    other_user = get_object_or_404(User, id=user_id)
    
    # Check if users are friends
    if not Friendship.are_friends(request.user, other_user):
        return JsonResponse({'error': 'You can only message your friends.'}, status=403)
    
    # Get conversation messages with files prefetched
    messages_list = Message.get_conversation(request.user, other_user).prefetch_related('files')
    
    # Mark messages as read
    Message.objects.filter(
        sender=other_user, 
        receiver=request.user, 
        is_read=False
    ).update(is_read=True)
    
    # Format messages for JSON response
    messages_data = []
    for msg in messages_list:
        files = []
        for f in msg.files.all():
            files.append({
                'id': f.id,
                'url': f.file.url,
                'original_name': f.original_name,
                'file_type': f.file_type,
                'file_size': f.file_size,
            })
        messages_data.append({
            'id': msg.id,
            'sender': msg.sender.id,
            'receiver': msg.receiver.id,
            'content': msg.content,
            'files': files,
            'created_at': msg.created_at.isoformat(),
            'is_read': msg.is_read
        })
    
    return JsonResponse({
        'success': True,
        'messages': messages_data
    })


@login_required
def api_send_message(request):
    """API endpoint to send a message"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    
    try:
        import json
        data = json.loads(request.body)
        receiver_id = data.get('receiver_id')
        content = data.get('content', '').strip()
        
        if not receiver_id or not content:
            return JsonResponse({'error': 'Missing receiver_id or content'}, status=400)
        
        other_user = get_object_or_404(User, id=receiver_id)
        
        # Check if users are friends
        if not Friendship.are_friends(request.user, other_user):
            return JsonResponse({'error': 'You can only message your friends.'}, status=403)
        
        # Create message
        message = Message.objects.create(
            sender=request.user,
            receiver=other_user,
            content=content
        )
        
        return JsonResponse({
            'success': True,
            'message': {
                'id': message.id,
                'sender': message.sender.id,
                'receiver': message.receiver.id,
                'content': message.content,
                'created_at': message.created_at.isoformat(),
                'is_read': message.is_read
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def api_send_message_with_files(request):
    """API endpoint to send a message with file attachments (multipart/form-data)"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=405)

    try:
        receiver_id = request.POST.get('receiver_id')
        content = request.POST.get('content', '').strip()

        if not receiver_id:
            return JsonResponse({'error': 'Missing receiver_id'}, status=400)

        other_user = get_object_or_404(User, id=receiver_id)

        # Check if users are friends
        if not Friendship.are_friends(request.user, other_user):
            return JsonResponse({'error': 'You can only message your friends.'}, status=403)

        # Create message (content can be blank if files are present)
        message = Message.objects.create(
            sender=request.user,
            receiver=other_user,
            content=content
        )

        saved_files = []
        files = request.FILES.getlist('files')
        allowed_types = [
            'image/jpeg', 'image/png', 'image/gif',
            'application/pdf', 'text/plain',
            'application/zip', 'application/x-zip-compressed',
            'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        ]
        max_size = 10 * 1024 * 1024  # 10 MB

        for f in files:
            # basic validation
            if f.size > max_size:
                continue
            # allow unknown types but capture type
            file_type = getattr(f, 'content_type', '')

            mf = None
            try:
                mf = MessageFile.objects.create(
                    message=message,
                    file=f,
                    original_name=getattr(f, 'name', ''),
                    file_size=getattr(f, 'size', 0),
                    file_type=file_type
                )

                saved_files.append({
                    'id': mf.id,
                    'url': mf.file.url,
                    'original_name': mf.original_name,
                    'file_type': mf.file_type,
                    'file_size': mf.file_size,
                })
            except Exception:
                # skip failed file saves
                continue

        return JsonResponse({
            'success': True,
            'message': {
                'id': message.id,
                'sender': message.sender.id,
                'receiver': message.receiver.id,
                'content': message.content,
                'created_at': message.created_at.isoformat(),
                'is_read': message.is_read,
                'files': saved_files
            }
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
