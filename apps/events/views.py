from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404, HttpResponse, JsonResponse
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from .models import Event, EventBooking, TicketCategory, BookingTicketItem, EventComment, EventCommentLike
from .forms import EventForm, EventBookingForm, TicketCategoryFormSet, EventCommentForm
from .tickets import ticket_filename, ticket_pdf
from apps.users.decorators import role_required
from apps.notifications.helpers import create_event_booking_notification, create_event_registration_notification

def event_list(request):
    """List all active events with search, filtering, and sorting"""
    from django.utils import timezone
    
    events = Event.objects.filter(is_active=True)
    today = timezone.now().date()
    
    # Search functionality
    search_query = request.GET.get('q', '')
    if search_query:
        events = events.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(event_type__icontains=search_query) |
            Q(venue_name__icontains=search_query)
        )
    
    # Filter by event type
    event_type = request.GET.get('type', '')
    if event_type:
        events = events.filter(event_type=event_type)
    
    # Filter by free/paid
    is_free = request.GET.get('free', '')
    if is_free == 'true':
        events = events.filter(is_free=True)
    elif is_free == 'false':
        events = events.filter(is_free=False)
    
    # Filter by status
    status_filter = request.GET.get('status', '')
    if status_filter == 'upcoming':
        events = events.filter(start_date__gt=today)
    elif status_filter == 'live':
        events = events.filter(start_date__lte=today, end_date__gte=today)
    elif status_filter == 'completed':
        events = events.filter(end_date__lt=today)
    
    # Sorting functionality
    sort_by = request.GET.get('sort', 'status')
    
    # Handle status-based sorting
    if sort_by == 'status':
        # Custom sorting: Live first, then Upcoming, then Completed
        events_list = list(events)
        live_events = []
        upcoming_events = []
        completed_events = []
        
        for event in events_list:
            if event.start_date.date() > today:
                upcoming_events.append(event)
            elif event.end_date.date() < today:
                completed_events.append(event)
            else:
                live_events.append(event)
        
        # Sort each category by start date
        live_events.sort(key=lambda x: x.start_date)
        upcoming_events.sort(key=lambda x: x.start_date)
        completed_events.sort(key=lambda x: x.start_date, reverse=True)
        
        # Combine in order: Live, Upcoming, Completed
        sorted_events = live_events + upcoming_events + completed_events
        events = sorted_events
    else:
        sort_options = {
            'date_asc': 'start_date',
            'date_desc': '-start_date',
            'price_asc': 'ticket_price',
            'price_desc': '-ticket_price',
            'title_asc': 'title',
            'title_desc': '-title',
            'newest': '-created_at',
            'oldest': 'created_at',
            'popular': '-max_attendees',  # Sort by capacity as popularity indicator
        }
        
        if sort_by in sort_options:
            events = events.order_by(sort_options[sort_by])
        else:
            events = events.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(events, 12)  # Show 12 events per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get event type choices for filter dropdown
    event_types = Event.EVENT_TYPE_CHOICES
    
    # Sort options for dropdown
    sort_choices = [
        ('status', 'On now, then coming up'),
        ('newest', 'Newest listed'),
        ('oldest', 'Oldest listed'),
        ('date_asc', 'Date, earliest'),
        ('date_desc', 'Date, latest'),
        ('price_asc', 'Price, low to high'),
        ('price_desc', 'Price, high to low'),
        ('title_asc', 'Title A to Z'),
        ('title_desc', 'Title Z to A'),
        ('popular', 'Most popular'),
    ]
    
    # Status filter choices
    status_options = [
        ('', 'Any time'),
        ('upcoming', 'Coming up'),
        ('live', 'On now'),
        ('completed', 'Ended'),
    ]
    
    return render(request, 'events/event_list.html', {
        'page_obj': page_obj,
        'search_query': search_query,
        'event_type': event_type,
        'is_free': is_free,
        'sort_by': sort_by,
        'status_filter': status_filter,
        'event_types': event_types,
        'sort_choices': sort_choices,
        'status_options': status_options,
        'today': today,
    })

def event_detail(request, pk):
    """Show event details and allow booking"""
    from django.utils import timezone
    from django.db.models import Sum
    
    event = get_object_or_404(Event, pk=pk, is_active=True)
    is_booked = False
    user_booking = None
    
    if request.user.is_authenticated:
        user_booking = EventBooking.objects.filter(event=event, user=request.user).first()
        is_booked = user_booking is not None
    
    # Calculate total registered people (sum of all ticket quantities)
    current_bookings = 0
    if event.ticket_categories.exists():
        # For events with ticket categories, sum all sold tickets
        total_tickets_sold = BookingTicketItem.objects.filter(
            booking__event=event,
            booking__status__in=['confirmed', 'paid']
        ).aggregate(total=Sum('quantity'))['total'] or 0
        current_bookings = total_tickets_sold
    else:
        # For events without categories, count bookings
        current_bookings = EventBooking.objects.filter(
            event=event, 
            status__in=['confirmed', 'paid']
        ).count()
    
    # Check if event is full
    is_full = current_bookings >= event.max_attendees
    
    # Check if registration deadline has passed
    registration_closed = False
    if event.registration_deadline:
        registration_closed = timezone.now() > event.registration_deadline

    # Get ticket categories for better template handling
    has_categories = event.ticket_categories.exists()
    active_categories = event.ticket_categories.filter(is_active=True)
    
    # Handle comment submission
    if request.method == 'POST' and request.user.is_authenticated:
        comment_form = EventCommentForm(request.POST, request.FILES)
        if comment_form.is_valid():
            comment_text = comment_form.cleaned_data['comment']
            parent_id = comment_form.cleaned_data.get('parent_id')
            image = comment_form.cleaned_data.get('image')
            
            # Create the comment
            comment = EventComment.objects.create(
                event=event,
                user=request.user,
                comment=comment_text,
                image=image,
                parent_id=parent_id if parent_id else None
            )
            
            messages.success(request, 'Your comment has been posted successfully!')
            return redirect('events:event_detail', pk=event.pk)
    else:
        comment_form = EventCommentForm()
    
    # Get all comments (top-level comments only, replies will be handled in template)
    comments = EventComment.objects.filter(
        event=event, 
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
    
    # Check if user can review this event
    user_can_review = False
    if request.user.is_authenticated and event.can_be_reviewed:
        # Check if user attended this event (has a confirmed booking)
        user_attended = EventBooking.objects.filter(
            event=event,
            user=request.user,
            status__in=['confirmed', 'paid']
        ).exists()
        
        # Check if user hasn't already reviewed this event
        from apps.reviews.models import EventReview
        already_reviewed = EventReview.objects.filter(
            event=event,
            user=request.user
        ).exists()
        
        user_can_review = user_attended and not already_reviewed
    
    # Get recent reviews for the event (show top 3)
    recent_reviews = []
    if hasattr(event, 'reviews'):
        recent_reviews = event.reviews.select_related('user').order_by('-created_at')[:3]

    # Cheapest ticket, shown as "From ..." next to the book button
    if has_categories:
        from_price = min((category.price for category in active_categories), default=event.ticket_price)
    else:
        from_price = event.ticket_price

    return render(request, 'events/event_detail.html', {
        'event': event,
        'is_booked': is_booked,
        'user_booking': user_booking,
        'is_full': is_full,
        'current_bookings': current_bookings,  # Total tickets sold
        'registration_closed': registration_closed,
        'has_categories': has_categories,
        'active_categories': active_categories,
        'comments': comments,
        'comment_form': comment_form,
        'user_can_review': user_can_review,
        'recent_reviews': recent_reviews,
        'from_price': from_price,
        'can_pick': (
            request.user.is_authenticated and has_categories
            and not is_booked and not is_full and not registration_closed
        ),
    })


@login_required
@role_required(['admin', 'event_manager'])
def event_create(request):
    """Create a new event with ticket categories - only for admins and event managers"""
    if request.method == 'POST':
        form = EventForm(request.POST, request.FILES)
        ticket_formset = TicketCategoryFormSet(request.POST, prefix='tickets')
        
        if form.is_valid() and ticket_formset.is_valid():
            with transaction.atomic():
                # Save the event
                event = form.save(commit=False)
                event.organizer = request.user
                event.save()
                
                # Save ticket categories
                valid_tickets = 0
                for ticket_form in ticket_formset:
                    if ticket_form.cleaned_data and not ticket_form.cleaned_data.get('DELETE', False):
                        if ticket_form.cleaned_data.get('name') and ticket_form.cleaned_data.get('price') is not None:
                            ticket = ticket_form.save(commit=False)
                            ticket.event = event
                            ticket.save()
                            valid_tickets += 1
                
                if valid_tickets > 0:
                    # If ticket categories are created, make event not free
                    event.is_free = False
                    event.save()
                    messages.success(request, f'Event "{event.title}" created successfully with {valid_tickets} ticket categories!')
                else:
                    messages.success(request, f'Event "{event.title}" created successfully!')
                
                return redirect('events:event_detail', pk=event.pk)
    else:
        form = EventForm()
        ticket_formset = TicketCategoryFormSet(prefix='tickets')
    
    return render(request, 'events/event_form.html', {
        'form': form,
        'ticket_formset': ticket_formset,
        'title': 'Create New Event'
    })

@login_required
@role_required(['admin', 'event_manager'])
def event_edit(request, pk):
    """Edit an existing event"""
    event = get_object_or_404(Event, pk=pk)
    
    # Check if user can edit this event
    if request.user != event.organizer and not request.user.profile.role == 'admin':
        messages.error(request, 'You can only edit events you created.')
        return redirect('events:event_detail', pk=event.pk)
    
    if request.method == 'POST':
        form = EventForm(request.POST, request.FILES, instance=event)
        if form.is_valid():
            form.save()
            messages.success(request, f'Event "{event.title}" updated successfully!')
            return redirect('events:event_detail', pk=event.pk)
    else:
        form = EventForm(instance=event)
    
    return render(request, 'events/event_form.html', {
        'form': form,
        'title': f'Edit Event: {event.title}',
        'event': event
    })

@login_required
@role_required(['admin', 'event_manager'])
def event_delete(request, pk):
    """Delete an event"""
    event = get_object_or_404(Event, pk=pk)
    
    # Check if user can delete this event
    if request.user != event.organizer and not request.user.profile.role == 'admin':
        messages.error(request, 'You can only delete events you created.')
        return redirect('events:event_detail', pk=event.pk)
    
    if request.method == 'POST':
        event_title = event.title
        event.delete()
        messages.success(request, f'Event "{event_title}" deleted successfully!')
        return redirect('events:event_list')
    
    return render(request, 'events/event_confirm_delete.html', {
        'event': event
    })

@login_required
def event_book(request, pk):
    """Book an event"""
    from django.utils import timezone
    
    event = get_object_or_404(Event, pk=pk, is_active=True)
    
    # Check if registration deadline has passed
    if event.registration_deadline and timezone.now() > event.registration_deadline:
        messages.error(request, 'Registration deadline has passed for this event.')
        return redirect('events:event_detail', pk=event.pk)
    
    # Check if user already booked
    existing_booking = EventBooking.objects.filter(event=event, user=request.user).first()
    if existing_booking:
        messages.warning(request, 'You have already booked this event.')
        return redirect('events:event_detail', pk=event.pk)
    
    # Check if event is full (only for events without ticket categories)
    if not event.ticket_categories.exists():
        current_attendees = EventBooking.objects.filter(
            event=event, 
            status__in=['confirmed', 'paid']
        ).count()
        if current_attendees >= event.max_attendees:
            messages.error(request, 'This event is fully booked.')
            return redirect('events:event_detail', pk=event.pk)
    
    if request.method == 'POST':
        form = EventBookingForm(request.POST, event=event, user=request.user)
        if form.is_valid():
            with transaction.atomic():
                # Create the booking
                booking = form.save(commit=False)
                booking.event = event
                booking.user = request.user
                booking.save()
                
                # Handle events with or without ticket categories
                if event.ticket_categories.exists():
                    # Get selected tickets and create BookingTicketItem instances
                    selected_tickets = form.get_selected_tickets()
                    total_amount = 0
                    total_quantity = 0
                    
                    for category, quantity in selected_tickets.items():
                        # Create ticket item
                        ticket_item = BookingTicketItem.objects.create(
                            booking=booking,
                            ticket_category=category,
                            quantity=quantity,
                            price_per_ticket=category.price
                        )
                        total_amount += ticket_item.subtotal
                        total_quantity += quantity
                    
                    # Update booking totals
                    booking.amount = total_amount
                    booking.total_amount = total_amount
                    booking.attendees_count = total_quantity
                else:
                    # Event without ticket categories - use default pricing
                    booking.amount = event.ticket_price
                    booking.total_amount = event.ticket_price
                    booking.attendees_count = 1
                
                # Set status based on payment
                if event.is_free or booking.amount == 0:
                    booking.status = 'confirmed'
                    booking.payment_status = 'completed'
                else:
                    booking.status = 'pending'
                    booking.payment_status = 'pending'
                
                booking.save()
                
                # Create notification for the user
                if event.is_free or booking.amount == 0:
                    create_event_booking_notification(
                        user=request.user,
                        event_name=event.title,
                        booking_id=booking.id
                    )
                    messages.success(request, 'Event booked successfully!')
                    return redirect('events:event_detail', pk=event.pk)
                else:
                    create_event_booking_notification(
                        user=request.user,
                        event_name=event.title,
                        booking_id=booking.id
                    )
                    messages.info(request, 'Booking created. Please complete payment to confirm.')
                    return redirect('payments:payment_process', booking_id=booking.id)
                
                # Create notification for event organizer
                if event.organizer and event.organizer != request.user:
                    # Count total registrations for this event
                    total_registrations = EventBooking.objects.filter(event=event).count()
                    create_event_registration_notification(
                        event_manager=event.organizer,
                        event_name=event.title,
                        user_name=request.user.get_full_name() or request.user.username,
                        total_registrations=total_registrations
                    )
                
                # Redirect based on payment needs
                if event.is_free or booking.amount == 0:
                    return redirect('events:event_detail', pk=event.pk)
                else:
                    return redirect('payments:payment_process', booking_id=booking.id)
        
        # If form is invalid, prepare context for re-rendering the form
        context = {
            'form': form,
            'event': event,
            'selected_quantities': {},
            'total_amount': 0,
            'total_tickets': 0,
            'is_checkout': False,
            'has_categories': event.ticket_categories.exists()
        }
    else:
        # Handle GET request - parse pre-selected quantities from URL
        initial_data = {}
        selected_quantities = {}
        total_amount = 0
        total_tickets = 0
        
        if event.ticket_categories.exists():
            for category in event.ticket_categories.all():
                quantity_param = f'quantity_{category.id}'
                quantity = request.GET.get(quantity_param, 0)
                try:
                    quantity = int(quantity)
                    if quantity > 0:
                        line_total = quantity * category.price
                        selected_quantities[category] = {
                            'quantity': quantity,
                            'line_total': line_total
                        }
                        total_amount += line_total
                        total_tickets += quantity
                        # Set initial form data for quantity fields
                        initial_data[f'quantity_{category.id}'] = quantity
                except (ValueError, TypeError):
                    continue
        
        # Initialize form with quantity data
        form = EventBookingForm(initial=initial_data, event=event, user=request.user)
        
        # Pass the selected quantities and totals to the template
        context = {
            'form': form,
            'event': event,
            'selected_quantities': selected_quantities,
            'total_amount': total_amount,
            'total_tickets': total_tickets,
            'is_checkout': bool(selected_quantities),  # Flag to indicate this is a checkout page
            'has_categories': event.ticket_categories.exists()
        }
    
    return render(request, 'events/event_booking_form.html', context)

@login_required
def my_events(request):
    """Show user's event bookings and organized events with comprehensive dashboard stats"""
    from django.db.models import Sum, Count
    from django.utils import timezone
    from apps.venues.models import VenueBooking
    
    # User's bookings
    bookings = EventBooking.objects.filter(user=request.user).order_by('-booking_date')
    
    # User's organized events (if they are event manager or admin)
    organized_events = []
    dashboard_stats = {}
    detailed_data = {}
    user_role = request.user.profile.role
    
    if user_role in ['admin', 'event_manager']:
        organized_events = Event.objects.filter(organizer=request.user).order_by('-created_at')
        
        # Calculate comprehensive dashboard statistics
        now = timezone.now()
        
        # Total events created by this user
        total_events_created = organized_events.count()
        
        # Event status counts
        upcoming_events = organized_events.filter(start_date__gt=now).count()
        live_events = organized_events.filter(start_date__lte=now, end_date__gte=now).count()
        completed_events = organized_events.filter(end_date__lt=now).count()
        
        # Total bookings across all user's events (confirmed when payment is completed)
        all_user_events = organized_events.all()
        total_event_bookings = EventBooking.objects.filter(
            event__in=all_user_events,
            payment_status='completed'
        ).count()
        
        # Total revenue from event bookings
        event_revenue = EventBooking.objects.filter(
            event__in=all_user_events,
            payment_status='completed'
        ).aggregate(total=Sum('total_amount'))['total'] or 0
        
        # Total venue bookings made by this user (from system venues)
        total_venue_bookings = VenueBooking.objects.filter(
            user=request.user,
            status__in=['confirmed', 'completed']
        ).count()
        
        # Calculate total tickets sold across all events
        total_tickets_sold = 0
        for event in all_user_events:
            if event.ticket_categories.exists():
                # Events with categories - sum ticket quantities
                tickets = BookingTicketItem.objects.filter(
                    booking__event=event,
                    booking__status__in=['confirmed', 'paid']
                ).aggregate(total=Sum('quantity'))['total'] or 0
            else:
                # Events without categories - sum attendee counts
                tickets = EventBooking.objects.filter(
                    event=event,
                    status__in=['confirmed', 'paid']
                ).aggregate(total=Sum('attendees_count'))['total'] or 0
            total_tickets_sold += tickets
        
        dashboard_stats = {
            'total_events_created': total_events_created,
            'total_event_bookings': total_event_bookings,
            'total_revenue': event_revenue,
            'total_venue_bookings': total_venue_bookings,
            'upcoming_events': upcoming_events,
            'live_events': live_events,
            'completed_events': completed_events,
            'total_tickets_sold': total_tickets_sold,
        }
        
        # Detailed data for modals
        detailed_data = {
            'upcoming_events_list': organized_events.filter(start_date__gt=now)[:5],
            'live_events_list': organized_events.filter(start_date__lte=now, end_date__gte=now)[:5],
            'completed_events_list': organized_events.filter(end_date__lt=now)[:5],
            'recent_bookings': EventBooking.objects.filter(
                event__in=all_user_events,
                status__in=['confirmed', 'paid']
            ).order_by('-booking_date')[:5],
            'venue_bookings_list': VenueBooking.objects.filter(
                user=request.user,
                status__in=['confirmed', 'completed']
            )[:5] if VenueBooking.objects.filter(user=request.user).exists() else [],
        }
    
    return render(request, 'events/my_events.html', {
        'bookings': bookings,
        'organized_events': organized_events,
        'user_role': user_role,
        'is_organiser': user_role in ['admin', 'event_manager'],
        'dashboard_stats': dashboard_stats,
        'detailed_data': detailed_data,
    })


@login_required
def events_created_detail(request):
    """Detailed view of all events created by the user"""
    if request.user.profile.role != 'event_manager':
        return redirect('events:event_list')
    
    events = Event.objects.filter(organizer=request.user).order_by('-created_at')
    
    # Categorize events
    now = timezone.now()
    live_events = events.filter(start_date__lte=now, end_date__gte=now)
    upcoming_events = events.filter(start_date__gt=now)
    completed_events = events.filter(end_date__lt=now)
    
    context = {
        'all_events': events,
        'live_events': live_events,
        'upcoming_events': upcoming_events,
        'completed_events': completed_events,
        'total_count': events.count(),
        'live_count': live_events.count(),
        'upcoming_count': upcoming_events.count(),
        'completed_count': completed_events.count(),
    }
    
    return render(request, 'events/events_created_detail.html', context)


@login_required
def events_live_detail(request):
    """Detailed view of live/running events only"""
    if request.user.profile.role != 'event_manager':
        return redirect('events:event_list')
    
    now = timezone.now()
    live_events = Event.objects.filter(
        organizer=request.user,
        start_date__lte=now,
        end_date__gte=now
    ).order_by('-created_at')
    
    context = {
        'events': live_events,
        'page_title': 'Live/Running Events',
        'page_subtitle': 'Events that are currently happening',
        'empty_message': 'No live events at the moment',
        'status_filter': 'live',
    }
    
    return render(request, 'events/events_status_detail.html', context)


@login_required
def events_upcoming_detail(request):
    """Detailed view of upcoming events only"""
    if request.user.profile.role != 'event_manager':
        return redirect('events:event_list')
    
    now = timezone.now()
    upcoming_events = Event.objects.filter(
        organizer=request.user,
        start_date__gt=now
    ).order_by('start_date')
    
    context = {
        'events': upcoming_events,
        'page_title': 'Upcoming Events',
        'page_subtitle': 'Events scheduled for the future',
        'empty_message': 'No upcoming events scheduled',
        'status_filter': 'upcoming',
    }
    
    return render(request, 'events/events_status_detail.html', context)


@login_required
def events_completed_detail(request):
    """Detailed view of completed events only"""
    if request.user.profile.role != 'event_manager':
        return redirect('events:event_list')
    
    now = timezone.now()
    completed_events = Event.objects.filter(
        organizer=request.user,
        end_date__lt=now
    ).order_by('-end_date')
    
    context = {
        'events': completed_events,
        'page_title': 'Completed Events',
        'page_subtitle': 'Events that have finished',
        'empty_message': 'No completed events yet',
        'status_filter': 'completed',
    }
    
    return render(request, 'events/events_status_detail.html', context)


@login_required
def event_bookings_detail(request):
    """Detailed view of all event bookings"""
    if request.user.profile.role != 'event_manager':
        return redirect('events:event_list')
    
    # Get all bookings for events organized by this user
    bookings = EventBooking.objects.filter(
        event__organizer=request.user
    ).select_related('event', 'user').order_by('-booking_date')
    
    # Calculate statistics based on payment status
    total_bookings = bookings.count()
    confirmed_bookings = bookings.filter(payment_status='completed')
    pending_bookings = bookings.filter(payment_status='pending')
    total_revenue = sum(booking.total_amount for booking in confirmed_bookings)
    
    context = {
        'bookings': bookings,
        'total_bookings': total_bookings,
        'confirmed_count': confirmed_bookings.count(),
        'pending_count': pending_bookings.count(),
        'total_revenue': total_revenue,
        'avg_booking_value': total_revenue / confirmed_bookings.count() if confirmed_bookings.count() > 0 else 0,
    }
    
    return render(request, 'events/event_bookings_detail.html', context)


@login_required
def revenue_detail(request):
    """Detailed view of revenue analytics"""
    if request.user.profile.role != 'event_manager':
        return redirect('events:event_list')
    
    # Get confirmed bookings
    bookings = EventBooking.objects.filter(
        event__organizer=request.user,
        status='confirmed'
    ).select_related('event')
    
    # Revenue by event
    revenue_by_event = {}
    for booking in bookings:
        event_title = booking.event.title
        if event_title not in revenue_by_event:
            revenue_by_event[event_title] = {'amount': 0, 'bookings': 0, 'avg_per_booking': 0}
        revenue_by_event[event_title]['amount'] += booking.total_amount
        revenue_by_event[event_title]['bookings'] += 1
    
    # Calculate average per booking for each event
    for event_title, data in revenue_by_event.items():
        if data['bookings'] > 0:
            data['avg_per_booking'] = data['amount'] / data['bookings']
    
    # Sort by revenue
    revenue_by_event = dict(sorted(revenue_by_event.items(), key=lambda x: x[1]['amount'], reverse=True))
    
    total_revenue = sum(booking.total_amount for booking in bookings)
    total_bookings = bookings.count()
    
    context = {
        'total_revenue': total_revenue,
        'total_bookings': total_bookings,
        'avg_per_booking': total_revenue / total_bookings if total_bookings > 0 else 0,
        'revenue_by_event': revenue_by_event,
        # The best-earning event, so the template can scale each bar against it
        'top_event_revenue': max((data['amount'] for data in revenue_by_event.values()), default=0),
        'recent_payments': bookings.order_by('-booking_date')[:10],
    }
    
    return render(request, 'events/revenue_detail.html', context)


@login_required
def venue_bookings_detail(request):
    """Detailed view of venue bookings"""
    if request.user.profile.role != 'event_manager':
        return redirect('events:event_list')
    
    # Import VenueBooking if it exists
    try:
        from apps.venues.models import VenueBooking
        venue_bookings = VenueBooking.objects.filter(
            user=request.user
        ).select_related('venue').order_by('-booking_date')
        
        confirmed = venue_bookings.filter(status='confirmed')
        pending = venue_bookings.filter(status='pending')
        total_spent = sum(booking.total_amount for booking in confirmed)
        
        context = {
            'venue_bookings': venue_bookings,
            'total_bookings': venue_bookings.count(),
            'confirmed_count': confirmed.count(),
            'pending_count': pending.count(),
            'total_spent': total_spent,
        }
    except ImportError:
        context = {
            'venue_bookings': [],
            'total_bookings': 0,
            'confirmed_count': 0,
            'pending_count': 0,
            'total_spent': 0,
        }
    
    return render(request, 'events/venue_bookings_detail.html', context)


@login_required
def tickets_sold_detail(request):
    """Detailed view of tickets sold analytics"""
    if request.user.profile.role != 'event_manager':
        return redirect('events:event_list')
    
    events = Event.objects.filter(organizer=request.user).prefetch_related('bookings')
    
    tickets_data = []
    total_tickets = 0
    total_revenue = 0
    
    for event in events:
        confirmed_bookings = event.bookings.filter(status='confirmed')
        event_tickets = confirmed_bookings.count()
        event_revenue = sum(booking.total_amount for booking in confirmed_bookings)
        
        tickets_data.append({
            'event': event,
            'tickets_sold': event_tickets,
            'revenue': event_revenue,
            'avg_ticket_price': event_revenue / event_tickets if event_tickets > 0 else 0,
        })
        
        total_tickets += event_tickets
        total_revenue += event_revenue
    
    # Sort by tickets sold
    tickets_data.sort(key=lambda x: x['tickets_sold'], reverse=True)
    
    context = {
        'tickets_data': tickets_data,
        'total_tickets': total_tickets,
        'total_revenue': total_revenue,
        'avg_ticket_price': total_revenue / total_tickets if total_tickets > 0 else 0,
        'total_events': events.count(),
        'avg_tickets_per_event': total_tickets / events.count() if events.count() > 0 else 0,
    }
    
    return render(request, 'events/tickets_sold_detail.html', context)


@login_required
def cancel_booking(request, pk):
    """Cancel an event booking"""
    booking = get_object_or_404(EventBooking, pk=pk, user=request.user)
    
    if booking.status == 'cancelled':
        messages.warning(request, 'This booking is already cancelled.')
        return redirect('events:my_events')
    
    if request.method == 'POST':
        booking.status = 'cancelled'
        booking.save()
        messages.success(request, f'Booking for "{booking.event.title}" cancelled successfully.')
        return redirect('events:my_events')
    
    return render(request, 'events/cancel_booking.html', {
        'booking': booking
    })


@login_required
def download_ticket(request, pk):
    """The PDF ticket for a confirmed booking: the attendee's own, or the organiser's copy.

    Anyone else gets a 404 rather than a refusal, so the page cannot be used to find out
    which bookings exist.
    """
    booking = get_object_or_404(EventBooking.objects.select_related('event', 'user'), pk=pk)
    if not _may_see_booking(request.user, booking):
        raise Http404('No such ticket.')

    if not booking.has_ticket:
        messages.info(request, 'A ticket is issued once the booking is confirmed.')
        return redirect('events:my_events')

    verify_url = request.build_absolute_uri(reverse('events:ticket_check', args=[booking.reference]))
    response = HttpResponse(ticket_pdf(booking, verify_url), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{ticket_filename(booking)}"'
    return response


@login_required
def ticket_check(request, reference):
    """Where a scanned ticket lands: whoever is on the gate sees whether to let someone in.

    The verdict only shows for the event's organiser, an admin, or the ticket holder
    themselves; for anyone else the page says who to ask and nothing about the booking.
    """
    booking = EventBooking.from_reference(reference)
    may_check = bool(booking) and _may_see_booking(request.user, booking)

    return render(request, 'events/ticket_check.html', {
        'reference': reference.upper(),
        'booking': booking if may_check else None,
        'may_check': may_check,
        'is_holder': bool(booking) and request.user == booking.user,
        'unknown': booking is None,
    })


def _may_see_booking(user, booking):
    return user == booking.user or user == booking.event.organizer or user.profile.role == 'admin'


@login_required
def comment_like_toggle(request, comment_id):
    """Toggle like/unlike on an event comment via AJAX"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        comment = get_object_or_404(EventComment, id=comment_id)
        
        # Toggle the like status
        is_liked = comment.toggle_like(request.user)
        
        return JsonResponse({
            'success': True,
            'is_liked': is_liked,
            'like_count': comment.like_count,
            'message': 'Liked!' if is_liked else 'Unliked!'
        })
        
    except EventComment.DoesNotExist:
        return JsonResponse({'error': 'Comment not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def comment_delete(request, comment_id):
    """Delete an event comment (owner or admin only)"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        comment = get_object_or_404(EventComment, id=comment_id)
        
        # Check permissions: owner or admin can delete
        if comment.user != request.user and not request.user.is_staff:
            return JsonResponse({'error': 'Permission denied'}, status=403)
        
        # Store the event ID for potential redirect
        event_id = comment.event.id
        
        # Delete the comment (this will cascade to replies due to foreign key)
        comment.delete()
        
        return JsonResponse({
            'success': True,
            'message': 'Comment deleted successfully',
            'event_id': event_id
        })
        
    except EventComment.DoesNotExist:
        return JsonResponse({'error': 'Comment not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
