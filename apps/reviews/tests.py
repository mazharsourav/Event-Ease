from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.events.models import EventBooking
from apps.events.tests import make_event
from apps.venues.models import VenueBooking
from apps.venues.tests import make_venue

from .models import EventReview, Review, VenueReview


def assert_clean(test, html):
    test.assertNotIn('<style', html)
    test.assertNotRegex(html, r'<script(?![^>]*\bsrc=)')
    test.assertNotIn('onclick=', html)
    test.assertNotIn(' style="', html)


class SiteReviewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.member = User.objects.create_user('member', password='pw', first_name='Mina', last_name='Das')

    def test_wall_shows_the_average_and_notes(self):
        Review.objects.create(user=self.member, rating=4, title='Easy booking', content='Found and booked in minutes.')
        response = self.client.get(reverse('reviews:all_reviews'))
        self.assertContains(response, 'Easy booking')
        self.assertContains(response, '4.0')
        self.assertContains(response, 'Log in to write a review')
        assert_clean(self, response.content.decode())

    def test_empty_wall_has_its_own_state(self):
        self.assertContains(self.client.get(reverse('reviews:all_reviews')), 'No reviews yet')

    def test_form_uses_star_radios_with_none_preselected(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('reviews:submit_review'))
        html = response.content.decode()
        self.assertEqual(html.count('name="rating"'), 5)
        self.assertNotIn('checked', html.split('ee-rate-stars')[1].split('</fieldset>')[0])
        assert_clean(self, html)

    def test_member_posts_then_edits_their_single_review(self):
        self.client.force_login(self.member)
        url = reverse('reviews:submit_review')
        self.client.post(url, {'rating': '5', 'title': 'Brilliant', 'content': 'Loved it'})
        self.client.post(url, {'rating': '3', 'title': 'Fine', 'content': 'Still good'})
        review = Review.objects.get(user=self.member)
        self.assertEqual((review.rating, review.title), (3, 'Fine'))

    def test_missing_rating_is_reported_on_the_form(self):
        self.client.force_login(self.member)
        response = self.client.post(reverse('reviews:submit_review'), {'title': 'No stars', 'content': 'Oops'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'This field is required')
        self.assertFalse(Review.objects.exists())

    def test_delete_is_post_only_and_own_review_only(self):
        review = Review.objects.create(user=self.member, rating=5, title='Great', content='Yes')
        url = reverse('reviews:delete_review', args=[review.pk])
        other = User.objects.create_user('other', password='pw')
        self.client.force_login(other)
        self.assertEqual(self.client.post(url).status_code, 404)
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.post(url)
        self.assertFalse(Review.objects.exists())


class EventReviewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organiser = User.objects.create_user('organiser', password='pw')
        cls.guest = User.objects.create_user('guest', password='pw', first_name='Gina')
        cls.stranger = User.objects.create_user('stranger', password='pw')
        start = timezone.now() - timedelta(days=3)
        cls.event = make_event(cls.organiser, 'Riverside Jazz', start_date=start, end_date=start + timedelta(hours=3))
        EventBooking.objects.create(event=cls.event, user=cls.guest, status='confirmed', attendee_name='Gina')
        cls.form_url = reverse('reviews:submit_event_review', args=[cls.event.pk])
        cls.data = {
            'rating': '5', 'organization_rating': '4', 'venue_rating': '5', 'value_rating': '3',
            'title': 'A lovely night', 'comment': 'Great sound, easy entry.',
        }

    def test_attendee_sees_a_form_with_four_star_rows(self):
        self.client.force_login(self.guest)
        response = self.client.get(self.form_url)
        self.assertEqual(response.status_code, 200)
        for name in ('rating', 'organization_rating', 'venue_rating', 'value_rating'):
            self.assertContains(response, f'name="{name}"', count=5)
        self.assertContains(response, 'Riverside Jazz')
        assert_clean(self, response.content.decode())

    def test_someone_who_did_not_book_is_turned_away(self):
        self.client.force_login(self.stranger)
        response = self.client.post(self.form_url, self.data)
        self.assertRedirects(response, reverse('events:event_detail', args=[self.event.pk]))
        self.assertFalse(EventReview.objects.exists())

    def test_review_is_saved_and_shown_with_its_breakdown(self):
        self.client.force_login(self.guest)
        self.client.post(self.form_url, self.data)
        self.assertEqual(EventReview.objects.get().organization_rating, 4)

        html = self.client.get(reverse('reviews:event_reviews', args=[self.event.pk])).content.decode()
        self.assertIn('A lovely night', html)
        self.assertIn('Organisation', html)
        self.assertIn('Value for money', html)
        self.assertIn('Delete', html)
        assert_clean(self, html)

    def test_only_the_author_can_delete(self):
        review = EventReview.objects.create(event=self.event, user=self.guest, booking=EventBooking.objects.get(),
                                            rating=5, organization_rating=4, venue_rating=5, value_rating=3, title='Nice')
        url = reverse('reviews:delete_event_review', args=[review.pk])
        self.client.force_login(self.stranger)
        self.assertEqual(self.client.post(url).status_code, 404)
        self.client.force_login(self.guest)
        self.client.post(url)
        self.assertFalse(EventReview.objects.exists())

    def test_event_without_reviews_shows_an_empty_state(self):
        self.assertContains(self.client.get(reverse('reviews:event_reviews', args=[self.event.pk])), 'No reviews yet')


class VenueReviewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user('manager', password='pw')
        cls.client_user = User.objects.create_user('hirer', password='pw')
        cls.venue = make_venue(cls.manager, 'Lakeside Hall')
        start = timezone.now() - timedelta(days=5)
        cls.booking = VenueBooking.objects.create(
            venue=cls.venue, user=cls.client_user, event_title='Wedding', event_description='A wedding',
            start_date=start, end_date=start + timedelta(hours=6), total_amount=15000, status='completed',
            contact_email='h@example.com', contact_phone='01711',
        )
        cls.form_url = reverse('reviews:submit_venue_review', args=[cls.venue.pk])

    def test_old_booking_review_link_goes_to_the_venue_review_form(self):
        self.client.force_login(self.client_user)
        response = self.client.get(reverse('venues:submit_review', args=[self.booking.pk]))
        self.assertRedirects(response, self.form_url)

    def test_form_and_post(self):
        self.client.force_login(self.client_user)
        response = self.client.get(self.form_url)
        self.assertContains(response, 'name="ambience_rating"', count=5)
        assert_clean(self, response.content.decode())

        response = self.client.post(self.form_url, {
            'rating': '4', 'ambience_rating': '5', 'service_rating': '4', 'cleanliness_rating': '4', 'value_rating': '3',
            'title': 'Roomy and clean', 'comment': 'Staff were helpful.',
        })
        self.assertRedirects(response, reverse('venues:venue_detail', args=[self.venue.pk]))
        self.assertEqual(VenueReview.objects.get().ambience_rating, 5)

        page = self.client.get(reverse('reviews:venue_reviews', args=[self.venue.pk])).content.decode()
        self.assertIn('Roomy and clean', page)
        self.assertIn('Ambience', page)
        self.assertIn('Cleanliness', page)
        assert_clean(self, page)
