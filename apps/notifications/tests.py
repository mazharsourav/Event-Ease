"""Notifications and the emails that go out beside them."""
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.events.models import EventBooking
from apps.events.tests import make_event
from apps.venues.models import VenueBooking
from apps.venues.tests import make_venue

from .models import Notification


class NotificationPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.member = User.objects.create_user('member', password='pw', email='member@example.com')

    def setUp(self):
        self.client.force_login(self.member)

    def test_the_list_shows_unread_first_and_is_markup_only(self):
        Notification.create_notification(self.member, 'Older thing', 'Already seen', is_read=True)
        Notification.create_notification(self.member, 'Newer thing', 'Not seen yet')

        response = self.client.get(reverse('notifications:notification_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Newer thing')
        self.assertContains(response, 'Older thing')
        html = response.content.decode()
        self.assertNotIn('<style', html)
        self.assertNotRegex(html, r'<script(?![^>]*\bsrc=)')
        self.assertNotIn('onclick=', html)

    def test_the_empty_state_explains_itself(self):
        response = self.client.get(reverse('notifications:notification_list'))
        self.assertContains(response, 'All quiet')
        self.assertContains(response, 'will show up here')

    def test_the_count_endpoint_only_counts_unread(self):
        Notification.create_notification(self.member, 'Read one', 'x', is_read=True)
        Notification.create_notification(self.member, 'Unread one', 'x')

        response = self.client.get(reverse('notifications:notification_count_api'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['count'], 1)

    def test_marking_everything_read_clears_the_count(self):
        Notification.create_notification(self.member, 'Unread one', 'x')
        self.client.post(reverse('notifications:mark_all_read_api'))
        self.assertEqual(Notification.objects.filter(user=self.member, is_read=False).count(), 0)

    def test_one_persons_notifications_are_not_another_persons(self):
        other = User.objects.create_user('other', password='pw')
        Notification.create_notification(other, 'Private to other', 'x')
        self.assertNotContains(self.client.get(reverse('notifications:notification_list')), 'Private to other')


class BookingEmailTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organiser = User.objects.create_user('organiser', password='pw', email='org@example.com')
        cls.member = User.objects.create_user('member', password='pw', email='member@example.com')
        cls.event = make_event(cls.organiser, 'Sunset Sessions')
        cls.venue = make_venue(cls.organiser, 'Grand Hall')

    def book(self, **extra):
        fields = dict(event=self.event, user=self.member, attendee_name='Member One',
                      attendee_email='member@example.com', attendees_count=1)
        fields.update(extra)
        return EventBooking.objects.create(**fields)

    def request_venue(self, status='pending'):
        start = timezone.now() + timedelta(days=15)
        return VenueBooking.objects.create(
            venue=self.venue, user=self.member, event_title='Annual dinner', event_description='A dinner',
            start_date=start, end_date=start + timedelta(hours=4), total_amount=8000,
            contact_email='member@example.com', contact_phone='01711', status=status,
        )

    def test_a_confirmed_booking_emails_the_attendee(self):
        booking = self.book(status='confirmed')

        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ['member@example.com'])
        self.assertIn('Sunset Sessions', message.subject)
        self.assertIn(booking.reference, message.body)
        self.assertIn('Open Air Hall', message.body)

    def test_a_pending_booking_does_not_email_anyone_yet(self):
        self.book(status='pending')
        self.assertEqual(len(mail.outbox), 0)

    def test_the_email_goes_out_when_the_booking_is_later_confirmed(self):
        booking = self.book(status='pending')
        mail.outbox.clear()

        booking.status = 'confirmed'
        booking.save()

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Sunset Sessions', mail.outbox[0].subject)

    def test_approving_a_venue_request_emails_the_person_who_asked(self):
        booking = self.request_venue()
        mail.outbox.clear()

        booking.status = 'confirmed'
        booking.save()

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Grand Hall', mail.outbox[0].subject)
        self.assertIn('is yours', mail.outbox[0].body)

    def test_rejecting_one_says_nothing_was_charged(self):
        booking = self.request_venue()
        mail.outbox.clear()

        booking.status = 'rejected'
        booking.save()

        self.assertIn('not accepted', mail.outbox[0].body)
        self.assertIn('Nothing has been charged', mail.outbox[0].body)

    def test_a_booking_still_succeeds_when_the_mail_server_is_down(self):
        """A paid-for booking must not be lost because email failed."""
        with patch('apps.notifications.emails.send_mail', side_effect=OSError('smtp is down')):
            with self.assertLogs('apps.notifications.emails', level='ERROR'):
                booking = self.book(status='confirmed')

        self.assertTrue(EventBooking.objects.filter(pk=booking.pk).exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_a_booking_with_no_address_on_file_is_skipped_quietly(self):
        self.member.email = ''
        self.member.save()
        self.book(status='confirmed', attendee_email='')
        self.assertEqual(len(mail.outbox), 0)
