from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views

app_name = 'users'

urlpatterns = [
    path('login/', views.user_login, name='login'),
    path('signup/', views.user_signup, name='signup'),
    path('logout/', views.user_logout, name='logout'),

    # Forgotten password: ask for an address, email a one-time link, set a new password.
    # Django's own views do the work; only the templates are ours.
    path('password-reset/', auth_views.PasswordResetView.as_view(
        template_name='users/password_reset.html',
        email_template_name='users/password_reset_email.txt',
        subject_template_name='users/password_reset_subject.txt',
        success_url=reverse_lazy('users:password_reset_done'),
    ), name='password_reset'),
    path('password-reset/sent/', auth_views.PasswordResetDoneView.as_view(
        template_name='users/password_reset_sent.html',
    ), name='password_reset_done'),
    path('password-reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='users/password_reset_confirm.html',
        success_url=reverse_lazy('users:password_reset_complete'),
    ), name='password_reset_confirm'),
    path('password-reset/done/', auth_views.PasswordResetCompleteView.as_view(
        template_name='users/password_reset_complete.html',
    ), name='password_reset_complete'),

    # Changing a password while signed in
    path('password-change/', auth_views.PasswordChangeView.as_view(
        template_name='users/password_change.html',
        success_url=reverse_lazy('users:password_change_done'),
    ), name='password_change'),
    path('password-change/done/', auth_views.PasswordChangeDoneView.as_view(
        template_name='users/password_change_done.html',
    ), name='password_change_done'),
    path('profile/', views.user_profile, name='profile'),
    path('dashboard/', views.user_dashboard, name='dashboard'),
    path('cancel-booking/', views.cancel_booking, name='cancel_booking'),
    path('download-event-invoice/<int:booking_id>/', views.download_event_invoice, name='download_event_invoice'),
    path('download-venue-invoice/<int:booking_id>/', views.download_venue_invoice, name='download_venue_invoice'),
    path('request-upgrade/', views.request_role_upgrade, name='request_upgrade'),
    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin/comments/', views.admin_comments_management, name='admin_comments_management'),
    path('admin/delete-comment/', views.delete_comment, name='delete_comment'),
    path('admin/reviews/', views.admin_reviews_management, name='admin_reviews_management'),
    path('admin/delete-review/', views.delete_review, name='delete_review'),
    path('admin/request/<int:request_id>/', views.view_upgrade_request, name='view_upgrade_request'),
    path('admin/process/<int:request_id>/', views.process_upgrade_request, name='process_upgrade_request'),
    # Social features - User search and profiles
    path('search/', views.search_users, name='search_users'),
    path('profile/<int:user_id>/', views.view_user_profile, name='view_user_profile'),
    
    # Friend request system
    path('send-friend-request/<int:user_id>/', views.send_friend_request, name='send_friend_request'),
    path('friends/', views.friends_page, name='friends'),
    path('accept-friend-request/<int:request_id>/', views.accept_friend_request, name='accept_friend_request'),
    path('reject-friend-request/<int:request_id>/', views.reject_friend_request, name='reject_friend_request'),
    path('unfriend/<int:user_id>/', views.unfriend_user, name='unfriend_user'),
    
    # Messaging system
    path('messages/', views.messages_page, name='messages'),
    path('conversation/<int:user_id>/', views.conversation_view, name='conversation'),
    
    # API endpoints
    path('api/unread-counts/', views.get_unread_counts, name='get_unread_counts'),
    path('api/mark-friend-requests-seen/', views.mark_friend_requests_seen, name='mark_friend_requests_seen'),
    path('api/mark-messages-read/', views.mark_messages_read, name='mark_messages_read'),
    path('api/messages/<int:user_id>/', views.api_get_messages, name='api_get_messages'),
    path('api/send-message/', views.api_send_message, name='api_send_message'),
    path('api/send-message-files/', views.api_send_message_with_files, name='api_send_message_with_files'),
]
