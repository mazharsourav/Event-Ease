from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import VenueBooking
from .tests import make_venue


class VenueManagerPagesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user('manager', password='pw')
        cls.manager.profile.role = 'venue_manager'
        cls.manager.profile.save()
        cls.venue = make_venue(cls.manager, 'Grand Hall')
        cls.client_user = User.objects.create_user('client', password='pw', first_name='Cara', last_name='Lee')
        start = timezone.now() + timedelta(days=12)
        cls.booking = VenueBooking.objects.create(
            venue=cls.venue, user=cls.client_user, event_title='Gala Night', event_description='A gala',
            start_date=start, end_date=start + timedelta(hours=4), total_amount=10000,
            contact_email='c@example.com', contact_phone='01711',
        )

    def assert_clean(self, response):
        html = response.content.decode()
        self.assertNotIn('<style', html)
        self.assertNotRegex(html, r'<script(?![^>]*\bsrc=)')
        self.assertNotIn('onclick=', html)
        self.assertNotIn(' style="', html)

    def test_my_venues_shows_pending_requests_with_plain_post_forms(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse('venues:my_venues'))
        self.assertContains(response, 'Gala Night')
        self.assertContains(response, reverse('venues:update_booking_status', args=[self.booking.pk]))
        self.assertContains(response, 'name="status" value="confirmed"')
        self.assert_clean(response)

    def test_approving_a_request(self):
        self.client.force_login(self.manager)
        self.client.post(reverse('venues:update_booking_status', args=[self.booking.pk]), {'status': 'confirmed'})
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, 'confirmed')

    def test_booking_lists_and_the_per_venue_page(self):
        self.client.force_login(self.manager)
        manager_list = self.client.get(reverse('venues:my_bookings'))
        self.assertContains(manager_list, 'Booking requests')
        per_venue = self.client.get(reverse('venues:manage_bookings', args=[self.venue.pk]))
        self.assertContains(per_venue, 'Gala Night')
        self.assert_clean(manager_list)
        self.assert_clean(per_venue)

        self.client.force_login(self.client_user)
        mine = self.client.get(reverse('venues:my_bookings'))
        self.assertContains(mine, 'Gala Night')
        self.assert_clean(mine)

    def test_venue_form_and_delete_pages(self):
        self.client.force_login(self.manager)
        create = self.client.get(reverse('venues:venue_create'))
        self.assertContains(create, 'List venue')
        edit = self.client.get(reverse('venues:venue_edit', args=[self.venue.pk]))
        self.assertContains(edit, 'Save changes')
        delete = self.client.get(reverse('venues:venue_delete', args=[self.venue.pk]))
        self.assertContains(delete, 'Yes, delete this venue')
        for response in (create, edit, delete):
            self.assert_clean(response)


class BookingApprovalTests(TestCase):
    """Approving a venue booking: it answers with a page, and it will not double-book the venue."""

    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user('hallkeeper', password='pw')
        cls.manager.profile.role = 'venue_manager'
        cls.manager.profile.save()
        cls.venue = make_venue(cls.manager, 'Lakeside Hall')
        cls.hirer = User.objects.create_user('hirer', password='pw')
        cls.outsider = User.objects.create_user('outsider', password='pw')
        cls.start = timezone.now() + timedelta(days=20)

    def make_booking(self, title, offset_hours=0, status='pending'):
        start = self.start + timedelta(hours=offset_hours)
        return VenueBooking.objects.create(
            venue=self.venue, user=self.hirer, event_title=title, event_description='An event',
            start_date=start, end_date=start + timedelta(hours=4), total_amount=5000,
            contact_email='h@example.com', contact_phone='01711', status=status,
        )

    def post(self, booking, status, **extra):
        """Post exactly as a browser form does, which is not what the test client sends by default."""
        return self.client.post(
            reverse('venues:update_booking_status', args=[booking.pk]),
            data=f'status={status}', content_type='application/x-www-form-urlencoded', **extra,
        )

    def test_approving_redirects_to_a_page_rather_than_returning_json(self):
        self.client.force_login(self.manager)
        booking = self.make_booking('Gala Night')
        response = self.post(booking, 'confirmed', HTTP_REFERER='http://testserver/venues/my-venues/')

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], 'http://testserver/venues/my-venues/')
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'confirmed')

    def test_without_a_referer_it_falls_back_to_the_manager_dashboard(self):
        self.client.force_login(self.manager)
        booking = self.make_booking('Gala Night')
        response = self.post(booking, 'confirmed')
        self.assertRedirects(response, reverse('venues:my_venues'))

    def test_a_referer_on_another_site_is_not_followed(self):
        self.client.force_login(self.manager)
        booking = self.make_booking('Gala Night')
        response = self.post(booking, 'confirmed', HTTP_REFERER='https://evil.example.com/')
        self.assertRedirects(response, reverse('venues:my_venues'))

    def test_an_overlapping_booking_cannot_be_approved(self):
        self.client.force_login(self.manager)
        self.make_booking('Wedding reception', status='confirmed')
        overlapping = self.make_booking('Birthday party', offset_hours=1)

        response = self.post(overlapping, 'confirmed')

        overlapping.refresh_from_db()
        self.assertEqual(overlapping.status, 'pending')
        message = ' '.join(str(m) for m in response.wsgi_request._messages)
        self.assertIn('Wedding reception', message)

    def test_a_booking_that_only_touches_another_is_fine(self):
        """One ends exactly when the next begins, so the hall is free."""
        self.client.force_login(self.manager)
        self.make_booking('Morning workshop', status='confirmed')
        later = self.make_booking('Evening dinner', offset_hours=4)

        self.post(later, 'confirmed')

        later.refresh_from_db()
        self.assertEqual(later.status, 'confirmed')

    def test_overlapping_is_still_fine_to_reject(self):
        self.client.force_login(self.manager)
        self.make_booking('Wedding reception', status='confirmed')
        overlapping = self.make_booking('Birthday party', offset_hours=1)

        self.post(overlapping, 'rejected')

        overlapping.refresh_from_db()
        self.assertEqual(overlapping.status, 'rejected')

    def test_an_unknown_status_is_refused(self):
        self.client.force_login(self.manager)
        booking = self.make_booking('Gala Night')
        self.post(booking, 'vanished')
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'pending')

    def test_someone_else_cannot_approve(self):
        self.client.force_login(self.outsider)
        booking = self.make_booking('Gala Night')
        self.post(booking, 'confirmed')
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'pending')
