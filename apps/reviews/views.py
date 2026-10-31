from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db import models
from django.core.exceptions import ValidationError
from .models import Review, EventReview, VenueReview
from .forms import ReviewForm, EventReviewForm, VenueReviewForm
from apps.events.models import Event, EventBooking
from apps.venues.models import Venue

def all_reviews(request):
    """Display all reviews in a paginated card layout"""
    reviews_list = Review.objects.all()
    paginator = Paginator(reviews_list, 12)  # 12 reviews per page
    
    page_number = request.GET.get('page')
    reviews = paginator.get_page(page_number)
    
    # Calculate average rating
    avg_rating = Review.objects.aggregate(
        avg_rating=models.Avg('rating')
    )['avg_rating'] or 0
    
    total_reviews = Review.objects.count()
    
    context = {
        'reviews': reviews,
        'avg_rating': round(avg_rating, 1),
        'total_reviews': total_reviews,
    }
    return render(request, 'reviews/all_reviews.html', context)

@login_required
def submit_review(request):
    """Handle review submission"""
    # Check if user already has a review
    existing_review = Review.objects.filter(user=request.user).first()
    
    if request.method == 'POST':
        if existing_review:
            form = ReviewForm(request.POST, instance=existing_review)
            action = 'updated'
        else:
            form = ReviewForm(request.POST)
            action = 'submitted'
            
        if form.is_valid():
            review = form.save(commit=False)
            review.user = request.user
            review.save()
            
            messages.success(request, f'Your review has been {action} successfully!')
            return redirect('home')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = ReviewForm(instance=existing_review) if existing_review else ReviewForm()
    
    context = {
        'form': form,
        'existing_review': existing_review,
    }
    return render(request, 'reviews/review_form.html', context)

@login_required  
@require_POST
def delete_review(request, review_id):
    """Delete user's own review"""
    review = get_object_or_404(Review, id=review_id, user=request.user)
    review.delete()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'message': 'Review deleted successfully!'})
    
    messages.success(request, 'Your review has been deleted.')
    return redirect('home')

def get_latest_reviews(limit=20):
    """Helper function to get latest reviews for home page"""
    return Review.objects.select_related('user', 'user__profile').order_by('-created_at')[:limit]


@login_required
def submit_event_review(request, event_id):
    """Handle event review submission"""
    event = get_object_or_404(Event, id=event_id)
    
    # Check if user has a booking for this event
    try:
        booking = EventBooking.objects.get(
            event=event,
            user=request.user,
            status__in=['confirmed', 'attended']
        )
    except EventBooking.DoesNotExist:
        messages.error(request, "You can only review events you have registered for.")
        return redirect('events:event_detail', pk=event_id)
    
    # Check if event is completed
    if event.status != 'completed':
        messages.error(request, "You can only review events that have been completed.")
        return redirect('events:event_detail', pk=event_id)
    
    # Check if user already has a review for this event
    existing_review = EventReview.objects.filter(event=event, user=request.user).first()
    
    if request.method == 'POST':
        if existing_review:
            form = EventReviewForm(request.POST, instance=existing_review, event=event, user=request.user)
            action = 'updated'
        else:
            form = EventReviewForm(request.POST, event=event, user=request.user)
            action = 'submitted'
            
        if form.is_valid():
            try:
                review = form.save(commit=False)
                review.booking = booking
                review.save()
                
                messages.success(request, f'Your event review has been {action} successfully!')
                return redirect('events:event_detail', pk=event_id)
            except ValidationError as e:
                if hasattr(e, 'message_dict'):
                    for field, errors in e.message_dict.items():
                        for error in errors:
                            messages.error(request, error)
                else:
                    messages.error(request, str(e))
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        if existing_review:
            form = EventReviewForm(instance=existing_review, event=event, user=request.user)
        else:
            form = EventReviewForm(event=event, user=request.user)
    
    context = {
        'form': form,
        'event': event,
        'existing_review': existing_review,
    }
    return render(request, 'reviews/review_form.html', context)


def event_reviews(request, event_id):
    """Display all reviews for a specific event"""
    event = get_object_or_404(Event, id=event_id)
    reviews = EventReview.objects.filter(event=event).select_related('user', 'user__profile')
    
    # Calculate average ratings
    if reviews:
        average_rating = sum([r.rating for r in reviews]) / len(reviews)
        avg_organization = sum([r.organization_rating for r in reviews]) / len(reviews)
        avg_venue = sum([r.venue_rating for r in reviews]) / len(reviews)
        avg_value = sum([r.value_rating for r in reviews]) / len(reviews)
    else:
        average_rating = avg_organization = avg_venue = avg_value = 0
    
    # Check if current user can review this event
    user_can_review_event = False
    if request.user.is_authenticated:
        has_booking = EventBooking.objects.filter(
            event=event,
            user=request.user,
            status__in=['confirmed', 'attended']
        ).exists()
        
        has_existing_review = EventReview.objects.filter(
            event=event,
            user=request.user
        ).exists()
        
        user_can_review_event = (
            event.status == 'completed' and 
            has_booking and 
            not has_existing_review
        )
    
    context = {
        'event': event,
        'reviews': reviews,
        'average_rating': average_rating,
        'avg_organization': avg_organization,
        'avg_venue': avg_venue,
        'avg_value': avg_value,
        'breakdown': [
            ('Organisation', avg_organization),
            ('Venue', avg_venue),
            ('Value for money', avg_value),
        ],
        'review_count': len(reviews),
        'user_can_review_event': user_can_review_event,
    }
    return render(request, 'reviews/event_reviews.html', context)


@login_required  
@require_POST
def delete_event_review(request, review_id):
    """Delete user's own event review"""
    review = get_object_or_404(EventReview, id=review_id, user=request.user)
    event_id = review.event.id
    review.delete()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'message': 'Review deleted successfully!'})
    
    messages.success(request, 'Your review has been deleted.')
    return redirect('events:event_detail', pk=event_id)


@login_required
def submit_venue_review(request, venue_id):
    venue = get_object_or_404(Venue, id=venue_id)
    
    # Check if user has booked this venue and booking is completed
    from apps.venues.models import VenueBooking
    from django.utils import timezone
    
    user_has_booked = VenueBooking.objects.filter(
        user=request.user,
        venue=venue,
        status__in=['confirmed', 'completed'],
        end_date__lt=timezone.now()
    ).exists()
    
    if not user_has_booked:
        messages.error(request, 'You can only review venues that you have booked and where your booking has been completed.')
        return redirect('venues:venue_detail', pk=venue_id)
    
    # Check if user has already reviewed this venue
    existing_review = VenueReview.objects.filter(user=request.user, venue=venue).first()
    
    if request.method == 'POST':
        form = VenueReviewForm(request.POST, instance=existing_review)
        if form.is_valid():
            review = form.save(commit=False)
            review.user = request.user
            review.venue = venue
            review.save()
            
            action = 'updated' if existing_review else 'submitted'
            messages.success(request, f'Your venue review has been {action} successfully!')
            return redirect('venues:venue_detail', pk=venue_id)
    else:
        form = VenueReviewForm(instance=existing_review)
    
    context = {
        'form': form,
        'venue': venue,
        'existing_review': existing_review,
    }
    return render(request, 'reviews/review_form.html', context)


def venue_reviews(request, venue_id):
    venue = get_object_or_404(Venue, id=venue_id)
    
    reviews = VenueReview.objects.filter(venue=venue).select_related('user').order_by('-created_at')
    
    # Calculate average ratings
    if reviews.exists():
        from django.db.models import Avg
        ratings = reviews.aggregate(
            avg_overall=Avg('rating'),
            avg_ambience=Avg('ambience_rating'),
            avg_service=Avg('service_rating'),
            avg_cleanliness=Avg('cleanliness_rating'),
            avg_value=Avg('value_rating'),
        )
        average_rating = ratings['avg_overall'] or 0
        avg_ambience = ratings['avg_ambience'] or 0
        avg_service = ratings['avg_service'] or 0
        avg_cleanliness = ratings['avg_cleanliness'] or 0
        avg_value = ratings['avg_value'] or 0
    else:
        average_rating = 0
        avg_ambience = avg_service = avg_cleanliness = avg_value = 0
    
    # Check if current user can review this venue
    user_can_review_venue = False
    if request.user.is_authenticated:
        from apps.venues.models import VenueBooking
        from django.utils import timezone
        
        user_has_booked = VenueBooking.objects.filter(
            user=request.user,
            venue=venue,
            status__in=['confirmed', 'completed'],
            end_date__lt=timezone.now()
        ).exists()
        
        user_has_existing_review = VenueReview.objects.filter(
            user=request.user,
            venue=venue
        ).exists()
        
        user_can_review_venue = (
            user_has_booked and 
            not user_has_existing_review
        )
    
    context = {
        'venue': venue,
        'reviews': reviews,
        'average_rating': average_rating,
        'avg_ambience': avg_ambience,
        'avg_service': avg_service,
        'avg_cleanliness': avg_cleanliness,
        'avg_value': avg_value,
        'breakdown': [
            ('Ambience', avg_ambience),
            ('Service', avg_service),
            ('Cleanliness', avg_cleanliness),
            ('Value for money', avg_value),
        ],
        'review_count': len(reviews),
        'user_can_review_venue': user_can_review_venue,
    }
    return render(request, 'reviews/venue_reviews.html', context)


@login_required  
@require_POST
def delete_venue_review(request, review_id):
    """Delete user's own venue review"""
    review = get_object_or_404(VenueReview, id=review_id, user=request.user)
    venue_id = review.venue.id
    review.delete()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'message': 'Review deleted successfully!'})
    
    messages.success(request, 'Your review has been deleted.')
    return redirect('venues:venue_detail', pk=venue_id)
