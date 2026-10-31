from django.urls import path
from . import views

app_name = 'reviews'

urlpatterns = [
    path('', views.all_reviews, name='all_reviews'),
    path('submit/', views.submit_review, name='submit_review'),
    path('delete/<int:review_id>/', views.delete_review, name='delete_review'),
    # Event review URLs
    path('event/<int:event_id>/submit/', views.submit_event_review, name='submit_event_review'),
    path('event/<int:event_id>/', views.event_reviews, name='event_reviews'),
    path('event-review/delete/<int:review_id>/', views.delete_event_review, name='delete_event_review'),
    # Venue review URLs
    path('venue/<int:venue_id>/submit/', views.submit_venue_review, name='submit_venue_review'),
    path('venue/<int:venue_id>/', views.venue_reviews, name='venue_reviews'),
    path('venue/delete/<int:review_id>/', views.delete_venue_review, name='delete_venue_review'),
]