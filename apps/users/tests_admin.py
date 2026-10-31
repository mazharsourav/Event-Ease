from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.events.models import EventBooking, EventComment
from apps.events.tests import make_event
from apps.payments.models import Payment
from apps.payments.reporting import platform_revenue
from apps.reviews import moderation as review_moderation
from apps.reviews.models import EventReview, Review, VenueReview
from apps.venues.models import VenueBooking, VenueComment
from apps.venues.tests import make_venue
from .models import RoleUpgradeRequest


def assert_clean(test, html):
    test.assertNotIn('<style', html)
    test.assertNotRegex(html, r'<script(?![^>]*\bsrc=)')
    test.assertNotIn('onclick=', html)
    test.assertNotIn(' style="', html)


class AdminTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user('boss', password='pw', first_name='Bea', last_name='Boss')
        cls.admin.profile.role = 'admin'
        cls.admin.profile.save()
        cls.member = User.objects.create_user('member', password='pw', first_name='Mo', last_name='Member', email='mo@example.com')
        cls.organiser = User.objects.create_user('organiser', password='pw')
        cls.event = make_event(cls.organiser, 'Sunset Sessions')
        cls.venue = make_venue(cls.organiser, 'Grand Hall')


class AdminDashboardTests(AdminTestCase):
    def test_members_are_kept_out(self):
        self.client.force_login(self.member)
        self.assertNotEqual(self.client.get(reverse('users:admin_dashboard')).status_code, 200)

    def test_dashboard_shows_people_content_and_requests(self):
        RoleUpgradeRequest.objects.create(user=self.member, requested_role='event_manager', reason='I run a society')
        self.client.force_login(self.admin)
        response = self.client.get(reverse('users:admin_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sunset Sessions')
        self.assertContains(response, 'Grand Hall')
        self.assertContains(response, 'mo@example.com')
        self.assertContains(response, 'I run a society')
        self.assertContains(response, 'name="action" value="approve"')
        assert_clean(self, response.content.decode())

    def test_every_table_cell_carries_its_phone_label(self):
        self.client.force_login(self.admin)
        html = self.client.get(reverse('users:admin_dashboard')).content.decode()
        self.assertIn('data-label="Person"', html)
        self.assertIn('data-label="Bookings"', html)


class CommentModerationTests(AdminTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.event_comment = EventComment.objects.create(event=cls.event, user=cls.member, comment='Is there parking nearby?')
        cls.venue_comment = VenueComment.objects.create(venue=cls.venue, user=cls.member, comment='Is the hall accessible?')

    def setUp(self):
        self.client.force_login(self.admin)

    def test_lists_both_kinds(self):
        response = self.client.get(reverse('users:admin_comments_management'))
        self.assertContains(response, 'Is there parking nearby?')
        self.assertContains(response, 'Is the hall accessible?')
        assert_clean(self, response.content.decode())

    def test_filter_by_type_and_search(self):
        url = reverse('users:admin_comments_management')
        only_venue = self.client.get(url, {'type': 'venue'})
        self.assertContains(only_venue, 'Is the hall accessible?')
        self.assertNotContains(only_venue, 'Is there parking nearby?')

        searched = self.client.get(url, {'search': 'parking'})
        self.assertContains(searched, 'Is there parking nearby?')
        self.assertNotContains(searched, 'Is the hall accessible?')

        self.assertContains(self.client.get(url, {'search': 'zzzz'}), 'Nothing matches')

    def test_delete_removes_the_comment(self):
        self.client.post(reverse('users:delete_comment'), {'comment_id': self.event_comment.pk, 'comment_type': 'event'})
        self.assertFalse(EventComment.objects.exists())
        self.assertTrue(VenueComment.objects.exists())

class ReviewModerationTests(AdminTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # A review only exists where somebody went, so the fixture books and attends first.
        past = timezone.now() - timedelta(days=3)
        cls.past_event = make_event(cls.organiser, 'Riverside Jazz', start_date=past,
                                    end_date=past + timedelta(hours=3))
        EventBooking.objects.create(event=cls.past_event, user=cls.member, status='confirmed')
        VenueBooking.objects.create(
            venue=cls.venue, user=cls.member, event_title='Wedding', event_description='A wedding',
            start_date=past, end_date=past + timedelta(hours=6), total_amount=15000,
            status='completed', contact_email='mo@example.com', contact_phone='01711')

        cls.event_review = EventReview.objects.create(
            event=cls.past_event, user=cls.member, rating=4, organization_rating=4, venue_rating=5,
            value_rating=3, title='Well run', comment='The sound was excellent.')
        cls.venue_review = VenueReview.objects.create(
            venue=cls.venue, user=cls.member, rating=2, ambience_rating=2, service_rating=3,
            cleanliness_rating=1, value_rating=2, title='Needs a clean', comment='Dusty floors throughout.')
        cls.site_review = Review.objects.create(
            user=cls.member, rating=5, title='Booking was easy', content='Found a venue in ten minutes.')

    def setUp(self):
        self.client.force_login(self.admin)

    def test_members_are_kept_out(self):
        self.client.force_login(self.member)
        self.assertNotEqual(self.client.get(reverse('users:admin_reviews_management')).status_code, 200)

    def test_all_three_kinds_are_listed_together(self):
        response = self.client.get(reverse('users:admin_reviews_management'))

        self.assertContains(response, 'Well run')
        self.assertContains(response, 'Needs a clean')
        self.assertContains(response, 'Booking was easy')
        self.assertContains(response, 'Riverside Jazz')
        self.assertContains(response, 'Grand Hall')
        assert_clean(self, response.content.decode())

    def test_the_rating_is_shown_as_a_number_and_as_stars(self):
        response = self.client.get(reverse('users:admin_reviews_management'), {'type': 'venue'})
        self.assertContains(response, '2/5')
        self.assertContains(response, 'aria-label="2.0 out of 5"')

    def test_filtering_by_kind(self):
        url = reverse('users:admin_reviews_management')

        only_venue = self.client.get(url, {'type': 'venue'})
        self.assertContains(only_venue, 'Needs a clean')
        self.assertNotContains(only_venue, 'Well run')

        only_site = self.client.get(url, {'type': 'site'})
        self.assertContains(only_site, 'Booking was easy')
        self.assertNotContains(only_site, 'Needs a clean')

    def test_an_invented_filter_falls_back_to_everything(self):
        response = self.client.get(reverse('users:admin_reviews_management'), {'type': 'nonsense'})
        self.assertContains(response, 'Well run')
        self.assertContains(response, 'Booking was easy')

    def test_searching_words_people_wrote(self):
        url = reverse('users:admin_reviews_management')

        searched = self.client.get(url, {'search': 'dusty'})
        self.assertContains(searched, 'Needs a clean')
        self.assertNotContains(searched, 'Well run')

        self.assertContains(self.client.get(url, {'search': 'zzzz'}), 'Nothing matches')

    def test_searching_by_the_person_who_wrote_it(self):
        response = self.client.get(reverse('users:admin_reviews_management'), {'search': 'Member'})
        self.assertContains(response, 'Well run')

    def test_deleting_an_event_review_leaves_the_others_alone(self):
        self.client.post(reverse('users:delete_review'),
                         {'review_id': self.event_review.pk, 'review_type': 'event'})

        self.assertFalse(EventReview.objects.exists())
        self.assertTrue(VenueReview.objects.exists())
        self.assertTrue(Review.objects.exists())

    def test_deleting_a_review_of_the_site(self):
        self.client.post(reverse('users:delete_review'),
                         {'review_id': self.site_review.pk, 'review_type': 'site'})
        self.assertFalse(Review.objects.exists())

    def test_deleting_something_that_is_already_gone_says_so(self):
        response = self.client.post(reverse('users:delete_review'),
                                    {'review_id': 9999, 'review_type': 'event'}, follow=True)
        self.assertContains(response, 'no longer exists')

    def test_a_made_up_kind_deletes_nothing(self):
        self.client.post(reverse('users:delete_review'),
                         {'review_id': self.event_review.pk, 'review_type': 'nonsense'})
        self.assertTrue(EventReview.objects.exists())

    def test_a_member_cannot_delete_a_review(self):
        self.client.force_login(self.member)
        self.client.post(reverse('users:delete_review'),
                         {'review_id': self.event_review.pk, 'review_type': 'event'})
        self.assertTrue(EventReview.objects.exists())

    def test_the_dashboard_links_to_this_page_and_counts_all_three_kinds(self):
        response = self.client.get(reverse('users:admin_dashboard'))

        self.assertContains(response, reverse('users:admin_reviews_management'))
        self.assertEqual(review_moderation.counts(), {'event': 1, 'venue': 1, 'site': 1, 'total': 3})

    def test_every_table_cell_carries_its_phone_label(self):
        html = self.client.get(reverse('users:admin_reviews_management')).content.decode()
        for label in ('On', 'Person', 'Rating', 'Review', 'Posted'):
            self.assertIn('data-label="%s"' % label, html)


class PlatformRevenueTests(AdminTestCase):
    """What the admin dashboard says EventEase has taken."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.booking = EventBooking.objects.create(
            event=cls.event, user=cls.member, status='confirmed', attendees_count=2,
            amount=3000, total_amount=3000)
        cls.payment = Payment.objects.create(
            booking=cls.booking, user=cls.member, amount=3000, payment_method='bkash',
            payment_status='completed', paid_at=timezone.now(), transaction_id='TRX-1',
            billing_name='Mo Member', billing_email='mo@example.com')

        start = timezone.now() + timedelta(days=20)
        cls.hire = VenueBooking.objects.create(
            venue=cls.venue, user=cls.member, event_title='Annual dinner', event_description='A dinner',
            start_date=start, end_date=start + timedelta(hours=5), total_amount=12000,
            contact_email='mo@example.com', contact_phone='01711', status='confirmed')

    def test_tickets_and_venue_hire_are_added_up(self):
        money = platform_revenue()

        self.assertEqual(money['tickets'], {'count': 1, 'amount': 3000})
        self.assertEqual(money['venues']['amount'], 12000)
        self.assertEqual(money['total'], 15000)

    def test_a_payment_that_never_completed_is_not_revenue(self):
        other = User.objects.create_user('other', password='pw')
        booking = EventBooking.objects.create(event=self.event, user=other, status='pending', amount=500,
                                              total_amount=500)
        Payment.objects.create(booking=booking, user=other, amount=500, payment_method='nagad',
                               payment_status='pending', billing_name='O', billing_email='o@example.com')

        money = platform_revenue()

        self.assertEqual(money['total'], 15000)
        self.assertEqual(money['awaiting'], 500)

    def test_a_venue_request_nobody_accepted_is_not_revenue(self):
        start = timezone.now() + timedelta(days=30)
        VenueBooking.objects.create(venue=self.venue, user=self.organiser, event_title='Maybe',
                                    event_description='A maybe', start_date=start,
                                    end_date=start + timedelta(hours=2), total_amount=9000,
                                    contact_email='o@example.com', contact_phone='017', status='pending')
        self.assertEqual(platform_revenue()['total'], 15000)

    def test_the_best_earners_are_ranked(self):
        money = platform_revenue()

        self.assertEqual([event.title for event in money['top_events']], ['Sunset Sessions'])
        self.assertEqual(money['top_events'][0].taken, 3000)
        self.assertEqual([venue.name for venue in money['top_venues']], ['Grand Hall'])

    def test_an_empty_platform_reports_nothing_rather_than_breaking(self):
        Payment.objects.all().delete()
        VenueBooking.objects.all().delete()

        money = platform_revenue()

        self.assertEqual(money['total'], 0)
        self.assertEqual(list(money['top_events']), [])

    def test_the_dashboard_shows_the_totals(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse('users:admin_dashboard'))

        self.assertContains(response, '15,000')  # taken altogether
        self.assertContains(response, '12,000')  # venue hire
        self.assertContains(response, 'Ticket payments')
        assert_clean(self, response.content.decode())
