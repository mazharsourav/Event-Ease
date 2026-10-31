from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.events.models import EventBooking
from apps.events.tests import make_event
from apps.notifications.models import Notification
from apps.venues.models import VenueBooking
from apps.venues.tests import make_venue

from .models import Friendship, FriendRequest, Message, RoleUpgradeRequest


def assert_clean(test, html):
    test.assertNotIn('<style', html)
    test.assertNotRegex(html, r'<script(?![^>]*\bsrc=)')
    test.assertNotIn('onclick=', html)
    test.assertNotIn(' style="', html)


class AuthPagesTests(TestCase):
    def test_login_page_is_markup_only(self):
        response = self.client.get(reverse('users:login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="username"')
        assert_clean(self, response.content.decode())

    def test_login_works(self):
        User.objects.create_user('sam', password='secret-pass-1')
        response = self.client.post(reverse('users:login'), {'username': 'sam', 'password': 'secret-pass-1'})
        self.assertEqual(response.status_code, 302)

    def test_signup_page_keeps_what_was_typed_after_an_error(self):
        response = self.client.post(reverse('users:signup'), {
            'first_name': 'Sam', 'last_name': 'Ray', 'username': 'samray', 'email': 'sam@example.com',
            'password1': 'longenough1', 'password2': 'different1',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="samray"')
        self.assertContains(response, 'value="sam@example.com"')
        assert_clean(self, response.content.decode())


class AccountPagesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.me = User.objects.create_user('me', password='pw', first_name='Mia', last_name='Rahman', email='me@example.com')
        cls.other = User.objects.create_user('other', password='pw', first_name='Omar', last_name='Khan')
        cls.organiser = User.objects.create_user('organiser', password='pw')
        cls.event = make_event(cls.organiser, 'Sunset Sessions')

    def setUp(self):
        self.client.force_login(self.me)

    def test_dashboard_lists_event_and_venue_bookings_in_tabs(self):
        EventBooking.objects.create(
            event=self.event, user=self.me, attendee_name='Mia', amount=Decimal('500'), total_amount=Decimal('500'),
            status='pending', payment_status='pending',
        )
        venue = make_venue(self.organiser)
        start = timezone.now() + timedelta(days=9)
        VenueBooking.objects.create(
            venue=venue, user=self.me, event_title='Launch', event_description='x', start_date=start,
            end_date=start + timedelta(hours=3), total_amount=9000, contact_email='m@example.com', contact_phone='017',
        )
        response = self.client.get(reverse('users:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sunset Sessions')
        self.assertContains(response, 'Launch')
        self.assertContains(response, 'role="tab"', count=5)
        self.assertContains(response, 'data-confirm')
        assert_clean(self, response.content.decode())

    def test_profile_page_has_the_edit_form(self):
        response = self.client.get(reverse('users:profile'))
        self.assertContains(response, 'name="first_name" value="Mia"')
        self.assertContains(response, 'Become an organiser')
        assert_clean(self, response.content.decode())

    def test_search_and_profile_pages(self):
        found = self.client.get(reverse('users:search_users'), {'q': 'omar'})
        self.assertContains(found, 'Omar Khan')
        profile = self.client.get(reverse('users:view_user_profile', args=[self.other.pk]))
        self.assertContains(profile, 'Omar Khan')
        assert_clean(self, found.content.decode())
        assert_clean(self, profile.content.decode())

    def test_friends_page_shows_requests_and_friends(self):
        FriendRequest.objects.create(from_user=self.other, to_user=self.me, status='pending')
        response = self.client.get(reverse('users:friends'))
        self.assertContains(response, 'Accept')
        self.assertContains(response, 'Omar Khan')
        assert_clean(self, response.content.decode())

    def test_messages_page_carries_the_chat_endpoints(self):
        Friendship.objects.create(user1=self.me, user2=self.other)
        Message.objects.create(sender=self.other, receiver=self.me, content='See you there')
        response = self.client.get(reverse('users:messages'))
        self.assertContains(response, 'data-ee-chat')
        self.assertContains(response, reverse('users:api_send_message'))
        self.assertContains(response, 'See you there')
        assert_clean(self, response.content.decode())

    def test_conversation_page(self):
        Friendship.objects.create(user1=self.me, user2=self.other)
        Message.objects.create(sender=self.me, receiver=self.other, content='Tickets booked')
        response = self.client.get(reverse('users:conversation', args=[self.other.pk]))
        self.assertContains(response, 'Tickets booked')
        assert_clean(self, response.content.decode())

    def test_notifications_page(self):
        Notification.objects.create(user=self.me, title='Booking confirmed', message='Your ticket is ready', notification_type='system')
        response = self.client.get(reverse('notifications:notification_list'))
        self.assertContains(response, 'Booking confirmed')
        self.assertContains(response, 'Mark all as read')
        assert_clean(self, response.content.decode())

    def test_request_upgrade_page_and_review_page(self):
        response = self.client.get(reverse('users:request_upgrade'))
        self.assertContains(response, 'name="requested_role"', count=2)
        assert_clean(self, response.content.decode())

        admin = User.objects.create_superuser('boss', 'boss@example.com', 'pw')
        upgrade = RoleUpgradeRequest.objects.create(
            user=self.me, requested_role='event_manager', phone='017', address='Dhaka', experience='Ran a fair', reason='I love events',
        )
        self.client.force_login(admin)
        review = self.client.get(reverse('users:view_upgrade_request', args=[upgrade.pk]))
        self.assertContains(review, 'Approve')
        self.assertContains(review, 'Ran a fair')
        assert_clean(self, review.content.decode())


class ProfilePrivacyTests(TestCase):
    """Someone else's profile never shows their contact details, friend or not."""

    @classmethod
    def setUpTestData(cls):
        cls.me = User.objects.create_user('me', password='pw')
        cls.other = User.objects.create_user(
            'other', password='pw', first_name='Omar', last_name='Khan', email='omar@example.com')
        cls.other.profile.phone = '01999887766'
        cls.other.profile.save()

    def assert_hides_contact_details(self):
        response = self.client.get(reverse('users:view_user_profile', args=[self.other.pk]))
        self.assertContains(response, 'Omar Khan')
        self.assertNotContains(response, 'omar@example.com')
        self.assertNotContains(response, '01999887766')

    def test_a_stranger_sees_no_contact_details(self):
        self.client.force_login(self.me)
        self.assert_hides_contact_details()

    def test_a_friend_sees_no_contact_details_either(self):
        Friendship.objects.create(user1=self.me, user2=self.other)
        self.client.force_login(self.me)
        self.assert_hides_contact_details()

    def test_your_own_contact_details_are_still_on_your_own_profile(self):
        self.client.force_login(self.other)
        response = self.client.get(reverse('users:profile'))
        self.assertContains(response, 'omar@example.com')
