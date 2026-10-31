from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse, HttpResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from decimal import Decimal
from .models import Venue, VenueBooking, VenueImage, VenueComment, VenueCommentLike
from .forms import VenueForm, VenueBookingForm, VenueCommentForm
from apps.users.decorators import role_required
from apps.notifications.helpers import create_venue_booking_notification, create_venue_booking_request_notification


def _safe_referer(request, fallback):
    """The page the form was submitted from, when it is one of ours; otherwise `fallback`.

    Managers reach the approve and reject buttons from several pages, so sending them back
    where they came from beats guessing. The host check stops an open redirect.
    """
    referer = request.META.get('HTTP_REFERER')
    if referer and url_has_allowed_host_and_scheme(referer, allowed_hosts={request.get_host()},
                                                   require_https=request.is_secure()):
        return referer
    return reverse(fallback)

# Add PDF generation imports
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.pdfgen import canvas
from io import BytesIO
from datetime import datetime

def venue_list(request):
    """List all active venues with search, filtering, and sorting"""
    venues = Venue.objects.filter(is_available=True).prefetch_related('images')
    
    # Search functionality
    search_query = request.GET.get('q', '')
    if search_query:
        venues = venues.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(venue_type__icontains=search_query) |
            Q(address__icontains=search_query) |
            Q(city__icontains=search_query)
        )
    
    # Filter by venue type
    venue_type = request.GET.get('type', '')
    if venue_type:
        venues = venues.filter(venue_type=venue_type)
    
    # Filter by capacity
    min_capacity = request.GET.get('min_capacity', '')
    if min_capacity:
        try:
            venues = venues.filter(capacity__gte=int(min_capacity))
        except ValueError:
            pass
    
    # Filter by amenities
    amenities = request.GET.getlist('amenities')
    for amenity in amenities:
        venues = venues.filter(amenities__icontains=amenity)
    
    # Sorting functionality
    sort_by = request.GET.get('sort', 'name')
    sort_options = {
        'name_asc': 'name',
        'name_desc': '-name',
        'price_asc': 'price_per_hour',
        'price_desc': '-price_per_hour',
        'capacity_asc': 'capacity',
        'capacity_desc': '-capacity',
        'newest': '-created_at',
        'oldest': 'created_at',
        'rating': '-rating',  # Assuming there's a rating field
        'city': 'city',
    }
    
    if sort_by in sort_options:
        venues = venues.order_by(sort_options[sort_by])
    else:
        venues = venues.order_by('name')
    
    # Pagination
    paginator = Paginator(venues, 12)  # Show 12 venues per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get venue type choices for filter dropdown
    venue_types = Venue.VENUE_TYPE_CHOICES
    
    # Sort options for dropdown
    sort_choices = [
        ('name_asc', 'Name (A-Z)'),
        ('name_desc', 'Name (Z-A)'),
        ('price_asc', 'Price (Low to High)'),
        ('price_desc', 'Price (High to Low)'),
        ('capacity_asc', 'Capacity (Small to Large)'),
        ('capacity_desc', 'Capacity (Large to Small)'),
        ('newest', 'Newest First'),
        ('oldest', 'Oldest First'),
        ('city', 'City (A-Z)'),
    ]
    
    # Common amenities for filter
    common_amenities = [
        'WiFi', 'Parking', 'Air Conditioning', 'Sound System', 'Projector',
        'Catering', 'Kitchen', 'Bar', 'Stage', 'Dance Floor'
    ]
    
    return render(request, 'venues/venue_list.html', {
        'page_obj': page_obj,
        'search_query': search_query,
        'venue_type': venue_type,
        'min_capacity': min_capacity,
        'selected_amenities': amenities,
        'sort_by': sort_by,
        'venue_types': venue_types,
        'sort_choices': sort_choices,
        'common_amenities': common_amenities,
    })

def venue_detail(request, pk):
    """Show venue details and allow booking"""
    venue = get_object_or_404(
        Venue.objects.prefetch_related('images'), 
        pk=pk, 
        is_available=True
    )
    
    # Dates that are already taken, so people see them before they ask
    from django.utils import timezone
    upcoming_bookings = VenueBooking.objects.filter(
        venue=venue,
        status='confirmed',
        end_date__gte=timezone.now()
    ).order_by('start_date')[:5]
    
    # Handle comment submission
    if request.method == 'POST' and request.user.is_authenticated:
        comment_form = VenueCommentForm(request.POST, request.FILES)
        if comment_form.is_valid():
            comment_text = comment_form.cleaned_data['comment']
            parent_id = comment_form.cleaned_data.get('parent_id')
            image = comment_form.cleaned_data.get('image')
            
            # Create the comment
            comment = VenueComment.objects.create(
                venue=venue,
                user=request.user,
                comment=comment_text,
                image=image,
                parent_id=parent_id if parent_id else None
            )
            
            messages.success(request, 'Your comment has been posted successfully!')
            return redirect('venues:venue_detail', pk=venue.pk)
    else:
        comment_form = VenueCommentForm()
    
    # Get all comments (top-level comments only, replies will be handled in template)
    comments = VenueComment.objects.filter(
        venue=venue, 
        parent=None
    ).select_related('user', 'user__profile').prefetch_related(        
        'likes',
        'replies__user', 
        'replies__user__profile',
        'replies__likes',
        'replies__replies__user',
        'replies__replies__user__profile',
        'replies__replies__likes',
        'replies__replies__replies__user',
        'replies__replies__replies__user__profile',
        'replies__replies__replies__likes'
    ).order_by('created_at')
    
    # Check if current user can review this venue
    user_can_review_venue = False
    user_venue_review = None
    
    if request.user.is_authenticated:
        from apps.reviews.models import VenueReview
        from django.utils import timezone
        
        # Check if user has booked this venue and booking is completed
        user_has_booked = VenueBooking.objects.filter(
            user=request.user,
            venue=venue,
            status__in=['confirmed', 'completed'],
            end_date__lt=timezone.now()
        ).exists()
        
        # Check if user has already reviewed this venue
        user_venue_review = VenueReview.objects.filter(
            venue=venue,
            user=request.user
        ).first()
        
        user_can_review_venue = user_has_booked and not user_venue_review
    
    role = getattr(getattr(request.user, 'profile', None), 'role', '')

    return render(request, 'venues/venue_detail.html', {
        'venue': venue,
        'upcoming_bookings': upcoming_bookings,
        'can_book': role in ('admin', 'event_manager'),
        'can_manage': request.user.is_authenticated and (venue.manager == request.user or role == 'admin'),
        'comments': comments,
        'comment_form': comment_form,
        'user_can_review_venue': user_can_review_venue,
        'user_venue_review': user_venue_review,
    })

@login_required
@role_required(['admin', 'venue_manager'])
def venue_create(request):
    """Create a new venue - only for admins and venue managers"""
    if request.method == 'POST':
        form = VenueForm(request.POST, request.FILES)
        if form.is_valid():
            venue = form.save(commit=False)
            venue.manager = request.user
            venue.save()
            
            # Handle multiple image uploads
            images = request.FILES.getlist('images')
            for i, image in enumerate(images):
                VenueImage.objects.create(
                    venue=venue,
                    image=image,
                    is_primary=(i == 0)  # First image is primary
                )
            
            messages.success(request, f'Venue "{venue.name}" created successfully!')
            return redirect('venues:venue_detail', pk=venue.pk)
    else:
        form = VenueForm()
    
    return render(request, 'venues/venue_form.html', {
        'form': form,
        'title': 'Create New Venue'
    })

@login_required
@role_required(['admin', 'venue_manager'])
def venue_edit(request, pk):
    """Edit an existing venue"""
    venue = get_object_or_404(Venue, pk=pk)
    
    # Check if user can edit this venue
    if request.user != venue.manager and not request.user.profile.role == 'admin':
        messages.error(request, 'You can only edit venues you manage.')
        return redirect('venues:venue_detail', pk=venue.pk)
    
    if request.method == 'POST':
        form = VenueForm(request.POST, request.FILES, instance=venue)
        if form.is_valid():
            form.save()
            
            # Handle new image uploads
            images = request.FILES.getlist('images')
            if images:
                # If new images are uploaded, mark all existing images as non-primary
                venue.images.update(is_primary=False)
                
                for i, image in enumerate(images):
                    VenueImage.objects.create(
                        venue=venue,
                        image=image,
                        is_primary=(i == 0)  # First new image is primary
                    )
            
            messages.success(request, f'Venue "{venue.name}" updated successfully!')
            return redirect('venues:venue_detail', pk=venue.pk)
    else:
        form = VenueForm(instance=venue)
    
    return render(request, 'venues/venue_form.html', {
        'form': form,
        'title': f'Edit Venue: {venue.name}',
        'venue': venue
    })

@login_required
@role_required(['admin', 'venue_manager'])
def venue_delete(request, pk):
    """Delete a venue"""
    venue = get_object_or_404(Venue, pk=pk)
    
    # Check if user can delete this venue
    if request.user != venue.manager and not request.user.profile.role == 'admin':
        messages.error(request, 'You can only delete venues you manage.')
        return redirect('venues:venue_detail', pk=venue.pk)
    
    if request.method == 'POST':
        venue_name = venue.name
        venue.delete()
        messages.success(request, f'Venue "{venue_name}" deleted successfully!')
        return redirect('venues:venue_list')
    
    return render(request, 'venues/venue_confirm_delete.html', {
        'venue': venue
    })

@login_required
def venue_book(request, pk):
    """Book a venue for an event - for all authenticated users"""
    venue = get_object_or_404(Venue, pk=pk, is_available=True)
    
    if request.method == 'POST':
        form = VenueBookingForm(request.POST, venue=venue)
        if form.is_valid():
            booking = form.save(commit=False)
            booking.venue = venue
            booking.user = request.user
            
            # Calculate amount based on venue pricing
            duration = booking.end_date - booking.start_date
            hours = Decimal(str(duration.total_seconds() / 3600))
            
            if venue.price_per_hour:
                booking.total_amount = (venue.price_per_hour * hours).quantize(Decimal('0.01'))
            elif venue.price_per_day:
                days = max(1, int(float(hours) / 24))
                booking.total_amount = (venue.price_per_day * Decimal(str(days))).quantize(Decimal('0.01'))
            else:
                booking.total_amount = Decimal('0.00')
            
            # Set initial status
            booking.status = 'pending'
            booking.payment_status = 'pending'
            booking.save()
            
            # Create notification for the user
            create_venue_booking_notification(
                user=request.user,
                venue_name=venue.name,
                status='pending',
                booking_id=booking.id
            )
            
            # Create notification for venue manager
            if venue.manager and venue.manager != request.user:
                create_venue_booking_request_notification(
                    venue_manager=venue.manager,
                    venue_name=venue.name,
                    requester_name=request.user.get_full_name() or request.user.username
                )
            
            messages.success(request, f'Booking request for "{venue.name}" submitted successfully!')
            return redirect('venues:my_bookings')
    else:
        initial_data = {
            'contact_email': request.user.email,
            'contact_phone': getattr(request.user.profile, 'phone', '') if hasattr(request.user, 'profile') else ''
        }
        form = VenueBookingForm(initial=initial_data, venue=venue)
    
    return render(request, 'venues/venue_booking_form.html', {
        'form': form,
        'venue': venue
    })

@login_required
def my_venues(request):
    """Show different dashboards based on user role"""
    user_role = request.user.profile.role
    
    if user_role == 'event_manager':
        # Event Manager Dashboard - only show their bookings and related info
        bookings = VenueBooking.objects.filter(user=request.user).order_by('-booking_date')
        
        # Calculate statistics for event manager
        total_bookings = bookings.count()
        pending_bookings = bookings.filter(status='pending').count()
        confirmed_bookings = bookings.filter(status='confirmed').count()
        completed_bookings = bookings.filter(status='completed').count()
        cancelled_bookings = bookings.filter(status='cancelled').count()
        
        # Calculate total spent
        confirmed_and_completed = bookings.filter(status__in=['confirmed', 'completed'])
        total_spent = sum(booking.total_amount for booking in confirmed_and_completed)
        
        # Recent activity (last 5 bookings)
        recent_bookings = bookings[:5]
        
        return render(request, 'venues/event_manager_dashboard.html', {
            'bookings': bookings,
            'user_role': user_role,
            'total_bookings': total_bookings,
            'pending_bookings': pending_bookings,
            'confirmed_bookings': confirmed_bookings,
            'completed_bookings': completed_bookings,
            'cancelled_bookings': cancelled_bookings,
            'total_spent': total_spent,
            'recent_bookings': recent_bookings,
        })
    
    else:
        # Venue Manager/Admin Dashboard - show venue management
        # User's venue bookings
        bookings = VenueBooking.objects.filter(user=request.user).order_by('-booking_date')
        
        # User's managed venues (if they are venue manager or admin)
        managed_venues = []
        if user_role in ['admin', 'venue_manager']:
            managed_venues = Venue.objects.filter(manager=request.user).order_by('-created_at')
        
        # For venue managers, get booking requests for their venues
        pending_booking_requests = []
        if user_role in ['admin', 'venue_manager'] and managed_venues:
            pending_booking_requests = VenueBooking.objects.filter(
                venue__in=managed_venues,
                status='pending'
            ).order_by('-booking_date')
        
        # Calculate statistics
        total_venues = managed_venues.count() if managed_venues else 0
        total_bookings = bookings.count()
        pending_bookings = bookings.filter(status='pending').count()
        
        # Calculate total revenue from confirmed bookings
        confirmed_bookings = bookings.filter(status='confirmed')
        total_revenue = sum(booking.total_amount for booking in confirmed_bookings)
        
        # Recent activity (last 5 bookings)
        recent_bookings = bookings[:5]
        
        return render(request, 'venues/my_venues.html', {
            'bookings': bookings,
            'managed_venues': managed_venues,
            'user_venues': managed_venues,  # Template uses this name
            'pending_booking_requests': pending_booking_requests,
            'user_role': user_role,
            'total_venues': total_venues,
            'total_bookings': total_bookings,
            'pending_bookings': pending_bookings,
            'total_revenue': total_revenue,
            'recent_bookings': recent_bookings,
        })

@login_required
def my_bookings(request):
    """Show user's venue bookings or all bookings for venue managers"""
    user_role = request.user.profile.role
    
    if user_role in ['admin', 'venue_manager']:
        # For venue managers, show bookings for their venues
        if user_role == 'admin':
            # Admins see all bookings
            bookings = VenueBooking.objects.all().order_by('-booking_date')
        else:
            # Venue managers see bookings for their venues
            bookings = VenueBooking.objects.filter(
                venue__manager=request.user
            ).order_by('-booking_date')
        
        # Add status filtering
        status_filter = request.GET.get('status', 'all')
        if status_filter != 'all':
            bookings = bookings.filter(status=status_filter)
        
        # Add search functionality
        search_query = request.GET.get('q', '')
        if search_query:
            bookings = bookings.filter(
                Q(event_title__icontains=search_query) |
                Q(user__first_name__icontains=search_query) |
                Q(user__last_name__icontains=search_query) |
                Q(venue__name__icontains=search_query)
            )
        
        # Calculate counts for tabs
        all_bookings = VenueBooking.objects.filter(venue__manager=request.user) if user_role == 'venue_manager' else VenueBooking.objects.all()
        counts = {
            'total_count': all_bookings.count(),
            'pending_count': all_bookings.filter(status='pending').count(),
            'confirmed_count': all_bookings.filter(status='confirmed').count(),
            'completed_count': all_bookings.filter(status='completed').count(),
            'cancelled_count': all_bookings.filter(status='cancelled').count(),
            'rejected_count': all_bookings.filter(status='rejected').count(),
        }
        
        template_name = 'venues/my_bookings_manager.html'
        context = {
            'bookings': bookings,
            'current_status': status_filter,
            'search_query': search_query,
            'user_role': user_role,
            **counts
        }
    else:
        # For regular users, show only their own bookings
        bookings = VenueBooking.objects.filter(user=request.user).order_by('-booking_date')
        template_name = 'venues/my_bookings.html'
        context = {
            'bookings': bookings,
        }
    
    return render(request, template_name, context)

@login_required
def cancel_venue_booking(request, pk):
    """Cancel a venue booking"""
    booking = get_object_or_404(VenueBooking, pk=pk, user=request.user)
    
    if booking.status == 'cancelled':
        messages.warning(request, 'This booking is already cancelled.')
        return redirect('venues:my_venues')
    
    # Event managers can only cancel pending bookings
    if request.user.profile.role == 'event_manager' and booking.status != 'pending':
        messages.error(request, 'You can only cancel pending bookings that have not been approved yet.')
        return redirect('venues:my_venues')
    
    if request.method == 'POST':
        booking.status = 'cancelled'
        booking.save()
        messages.success(request, f'Booking for "{booking.venue.name}" cancelled successfully.')
        return redirect('venues:my_venues')
    
    return render(request, 'venues/cancel_venue_booking.html', {
        'booking': booking
    })

@login_required
@role_required(['admin', 'venue_manager'])
def manage_bookings(request, venue_pk):
    """Manage bookings for a specific venue"""
    venue = get_object_or_404(Venue, pk=venue_pk)
    
    # Check if user can manage this venue
    if request.user != venue.manager and not request.user.profile.role == 'admin':
        messages.error(request, 'You can only manage bookings for venues you manage.')
        return redirect('venues:venue_detail', pk=venue.pk)
    
    bookings = VenueBooking.objects.filter(venue=venue).order_by('-booking_date')
    
    return render(request, 'venues/manage_bookings.html', {
        'venue': venue,
        'bookings': bookings,
    })

@login_required
@role_required(['admin', 'venue_manager'])
def update_booking_status(request, pk):
    """Approve, reject, cancel or complete a venue booking.

    Submitted by the plain forms in venues/_manager_row.html, so the answer is always a
    redirect back to the page the manager was on.
    """
    booking = get_object_or_404(VenueBooking, pk=pk)
    venue = booking.venue

    if request.user != venue.manager and request.user.profile.role != 'admin':
        messages.error(request, 'You can only manage bookings for venues you manage.')
        return redirect('venues:venue_detail', pk=venue.pk)

    back = _safe_referer(request, fallback='venues:my_venues')

    if request.method != 'POST':
        return redirect(back)

    new_status = request.POST.get('status')
    if new_status not in dict(VenueBooking.BOOKING_STATUS_CHOICES):
        messages.error(request, 'That is not a booking status.')
        return redirect(back)

    # Approving is the only change that can double-book the venue: two requests for the same
    # slot can both sit in "pending" until a manager works through them.
    if new_status == 'confirmed':
        clash = VenueBooking.objects.filter(
            venue=venue,
            status__in=['confirmed', 'completed'],
            start_date__lt=booking.end_date,
            end_date__gt=booking.start_date,
        ).exclude(pk=booking.pk).first()
        if clash:
            messages.error(
                request,
                f'"{clash.event_title}" already holds this venue from '
                f'{timezone.localtime(clash.start_date):%d %b %Y, %I:%M %p} to '
                f'{timezone.localtime(clash.end_date):%d %b %Y, %I:%M %p}. '
                'Cancel that booking first, or reject this one.'
            )
            return redirect(back)

    booking.status = new_status
    booking.save()
    messages.success(request, f'Booking marked as {booking.get_status_display().lower()}.')
    return redirect(back)

@login_required
@role_required(['admin', 'venue_manager', 'event_manager'])
def booking_details(request, pk):
    """Get detailed booking information for venue managers and event managers"""
    booking = get_object_or_404(VenueBooking, pk=pk)
    
    # Check if user can view this booking
    user_role = request.user.profile.role
    if user_role == 'venue_manager' and request.user != booking.venue.manager:
        messages.error(request, 'Access denied - not your venue')
        return redirect('venues:my_venues')
    elif user_role == 'event_manager' and request.user != booking.user:
        messages.error(request, 'Access denied - not your booking')
        return redirect('venues:my_venues')
    elif user_role not in ['admin', 'venue_manager', 'event_manager']:
        messages.error(request, 'Access denied')
        return redirect('venues:my_venues')
    
    # Calculate duration
    duration = booking.end_date - booking.start_date
    hours = duration.total_seconds() / 3600
    days = hours / 24
    
    context = {
        'booking': booking,
        'duration_hours': round(hours, 1),
        'duration_days': round(days, 1),
        'venue': booking.venue,
        'user_role': user_role,
    }
    
    # If it's an AJAX request, return partial template
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'venues/booking_details_modal.html', context)
    
    # Otherwise return full page
    return render(request, 'venues/booking_details.html', context)

@login_required  
def generate_invoice(request, pk):
    """Generate PDF invoice for a booking"""
    booking = get_object_or_404(VenueBooking, pk=pk)
    
    # Check permissions - only the booking user or venue manager/admin can generate invoice
    user_role = request.user.profile.role
    if request.user != booking.user and request.user != booking.venue.manager and user_role != 'admin':
        messages.error(request, 'Permission denied')
        return redirect('venues:my_venues')
    
    # Only generate invoices for confirmed or completed bookings
    if booking.status not in ['confirmed', 'completed']:
        messages.error(request, 'Cannot generate invoice for pending/cancelled bookings')
        return redirect('venues:my_venues')
    
    # Create PDF in memory
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    
    # Get styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        textColor=colors.HexColor('#40B5AD'),
        alignment=1  # Center alignment
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        spaceBefore=20,
        spaceAfter=10,
        textColor=colors.HexColor('#40B5AD')
    )
    
    # Build PDF content
    content = []
    
    # Title
    content.append(Paragraph("EventEase Invoice", title_style))
    content.append(Spacer(1, 20))
    
    # Invoice details
    invoice_number = f'INV-{booking.id}-{booking.booking_date.year}'
    invoice_date = datetime.now().strftime('%B %d, %Y')
    
    invoice_info = [
        ['Invoice Number:', invoice_number],
        ['Invoice Date:', invoice_date],
        ['Booking ID:', f'#{booking.id}'],
        ['Status:', booking.get_status_display()]
    ]
    
    invoice_table = Table(invoice_info, colWidths=[2*inch, 3*inch])
    invoice_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    
    content.append(invoice_table)
    content.append(Spacer(1, 30))
    
    # Client Information
    content.append(Paragraph("Bill To:", heading_style))
    client_info = [
        ['Client Name:', booking.user.get_full_name()],
        ['Email:', booking.contact_email],
        ['Phone:', booking.contact_phone],
    ]
    
    client_table = Table(client_info, colWidths=[2*inch, 4*inch])
    client_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    
    content.append(client_table)
    content.append(Spacer(1, 30))
    
    # Venue Information
    content.append(Paragraph("Venue Details:", heading_style))
    venue_info = [
        ['Venue Name:', booking.venue.name],
        ['Address:', f"{booking.venue.address}, {booking.venue.city}"],
        ['State & Zip:', f"{booking.venue.state} {booking.venue.zipcode}"],
        ['Venue Type:', booking.venue.get_venue_type_display()],
        ['Capacity:', f"{booking.venue.capacity} guests"],
        ['Hourly Rate:', f"${booking.venue.price_per_hour}/hour"],
    ]
    
    venue_table = Table(venue_info, colWidths=[2*inch, 4*inch])
    venue_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    
    content.append(venue_table)
    content.append(Spacer(1, 30))
    
    # Event Information
    content.append(Paragraph("Event Details:", heading_style))
    
    # Calculate duration
    duration = booking.end_date - booking.start_date
    hours = duration.total_seconds() / 3600
    
    event_info = [
        ['Event Title:', booking.event_title],
        ['Event Start:', booking.start_date.strftime('%B %d, %Y at %I:%M %p')],
        ['Event End:', booking.end_date.strftime('%B %d, %Y at %I:%M %p')],
        ['Duration:', f"{round(hours, 1)} hours"],
        ['Venue Capacity:', f"{booking.venue.capacity} guests"],
        ['Special Requirements:', booking.special_requirements or 'None'],
    ]
    
    event_table = Table(event_info, colWidths=[2*inch, 4*inch])
    event_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    
    content.append(event_table)
    content.append(Spacer(1, 30))
    
    # Payment Information
    content.append(Paragraph("Payment Summary:", heading_style))
    
    payment_data = [
        ['Description', 'Amount'],
        ['Venue Rental Fee', f"${booking.total_amount}"],
        ['Payment Status', booking.get_payment_status_display() if hasattr(booking, 'get_payment_status_display') else 'Pending'],
    ]
    
    # Add total row
    payment_data.append(['TOTAL AMOUNT', f"${booking.total_amount}"])
    
    payment_table = Table(payment_data, colWidths=[4*inch, 2*inch])
    payment_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#40B5AD')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (-2, -1), (-1, -1), colors.HexColor('#40B5AD')),
        ('TEXTCOLOR', (-2, -1), (-1, -1), colors.whitesmoke),
        ('FONTNAME', (-2, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (-2, -1), (-1, -1), 14),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    
    content.append(payment_table)
    content.append(Spacer(1, 30))
    
    # Footer
    footer_text = """
    <para align=center>
    <b>Thank you for choosing EventEase!</b><br/>
    For any questions regarding this invoice, please contact us at support@eventease.com<br/>
    Generated on {date}
    </para>
    """.format(date=datetime.now().strftime('%B %d, %Y at %I:%M %p'))
    
    content.append(Paragraph(footer_text, styles['Normal']))
    
    # Build PDF
    doc.build(content)
    
    # Get PDF data
    pdf_data = buffer.getvalue()
    buffer.close()
    
    # Create response
    response = HttpResponse(pdf_data, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="EventEase_Invoice_{invoice_number}.pdf"'
    
    return response

@login_required
def submit_review(request, pk):
    """Reviewing a finished booking is done on the venue's review page; this keeps the old link working."""
    booking = get_object_or_404(VenueBooking, pk=pk, user=request.user, status='completed')
    return redirect('reviews:submit_venue_review', venue_id=booking.venue_id)


@login_required
def comment_like_toggle(request, comment_id):
    """Toggle like/unlike on a venue comment via AJAX"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        comment = get_object_or_404(VenueComment, id=comment_id)
        
        # Toggle the like status
        is_liked = comment.toggle_like(request.user)
        
        return JsonResponse({
            'success': True,
            'is_liked': is_liked,
            'like_count': comment.like_count,
            'message': 'Liked!' if is_liked else 'Unliked!'
        })
        
    except VenueComment.DoesNotExist:
        return JsonResponse({'error': 'Comment not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def comment_delete(request, comment_id):
    """Delete a venue comment (owner or admin only)"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        comment = get_object_or_404(VenueComment, id=comment_id)
        
        # Check permissions: owner or admin can delete
        if comment.user != request.user and not request.user.is_staff:
            return JsonResponse({'error': 'Permission denied'}, status=403)
        
        # Store the venue ID for potential redirect
        venue_id = comment.venue.id
        
        # Delete the comment (this will cascade to replies due to foreign key)
        comment.delete()
        
        return JsonResponse({
            'success': True,
            'message': 'Comment deleted successfully',
            'venue_id': venue_id
        })
        
    except VenueComment.DoesNotExist:
        return JsonResponse({'error': 'Comment not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
