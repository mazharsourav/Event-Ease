from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Event, EventBooking, TicketCategory
from .tests import make_event

DETAIL_PAGES = (
    'events_created_detail', 'event_bookings_detail', 'revenue_detail', 'tickets_sold_detail',
    'events_live_detail', 'events_upcoming_detail', 'events_completed_detail', 'venue_bookings_detail',
)


class OrganiserPagesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organiser = User.objects.create_user('organiser', password='pw')
        cls.organiser.profile.role = 'event_manager'
        cls.organiser.profile.save()
        cls.event = make_event(cls.organiser, 'Sunset Sessions')
        TicketCategory.objects.create(event=cls.event, name='General', price=500, quantity_available=20)

    def setUp(self):
        self.client.force_login(self.organiser)

    def assert_clean(self, response):
        html = response.content.decode()
        self.assertNotIn('<style', html)
        self.assertNotRegex(html, r'<script(?![^>]*\bsrc=)')
        self.assertNotIn('onclick=', html)
        self.assertNotIn(' style="', html)

    def test_dashboard_links_to_every_detail_page(self):
        response = self.client.get(reverse('events:my_events'))
        self.assertEqual(response.status_code, 200)
        for name in DETAIL_PAGES:
            self.assertContains(response, reverse('events:' + name))
        self.assertContains(response, 'Sunset Sessions')
        self.assert_clean(response)

    def test_a_member_sees_their_bookings_not_the_organiser_dashboard(self):
        member = User.objects.create_user('member', password='pw')
        self.client.force_login(member)
        response = self.client.get(reverse('events:my_events'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No tickets yet')

    def test_stat_detail_pages_render(self):
        for name in DETAIL_PAGES:
            response = self.client.get(reverse('events:' + name))
            self.assertEqual(response.status_code, 200, name)
            self.assert_clean(response)

    def test_event_form_has_a_tier_template_with_the_formset_prefix(self):
        response = self.client.get(reverse('events:event_create'))
        self.assertContains(response, 'data-prefix="tickets"')
        self.assertContains(response, 'tickets-__prefix__-name')
        self.assertContains(response, 'name="tickets-TOTAL_FORMS"')
        self.assert_clean(response)

    def test_creating_an_event_with_a_tier(self):
        start = timezone.now() + timedelta(days=5)
        response = self.client.post(reverse('events:event_create'), {
            'title': 'Tier Test', 'description': 'd', 'event_type': 'concert', 'venue_name': 'Hall',
            'venue_address': 'Road 1', 'start_date': start.strftime('%Y-%m-%dT%H:%M'),
            'end_date': (start + timedelta(hours=3)).strftime('%Y-%m-%dT%H:%M'),
            'max_attendees': 50, 'ticket_price': '100', 'contact_email': 'x@example.com',
            'tickets-TOTAL_FORMS': 1, 'tickets-INITIAL_FORMS': 0, 'tickets-MIN_NUM_FORMS': 0, 'tickets-MAX_NUM_FORMS': 5,
            'tickets-0-name': 'General', 'tickets-0-category_type': 'general', 'tickets-0-price': '250',
            'tickets-0-quantity_available': '30', 'tickets-0-description': '',
        })
        created = Event.objects.get(title='Tier Test')
        self.assertRedirects(response, reverse('events:event_detail', args=[created.pk]))
        self.assertEqual(created.ticket_categories.get().price, 250)

    def test_edit_and_delete_pages(self):
        edit = self.client.get(reverse('events:event_edit', args=[self.event.pk]))
        self.assertContains(edit, 'Save changes')
        self.assertNotContains(edit, 'data-tiers')
        delete = self.client.get(reverse('events:event_delete', args=[self.event.pk]))
        self.assertContains(delete, 'Yes, delete this event')
        self.assert_clean(edit)
        self.assert_clean(delete)


class RevenuePageTests(TestCase):
    """The revenue page draws a bar per event scaled against the best earner."""

    @classmethod
    def setUpTestData(cls):
        cls.organiser = User.objects.create_user('earner', password='pw')
        cls.organiser.profile.role = 'event_manager'
        cls.organiser.profile.save()
        cls.big = make_event(cls.organiser, 'Sold Out Show')
        cls.small = make_event(cls.organiser, 'Quiet Evening')

        for index, (event, amount) in enumerate(((cls.big, 4000), (cls.big, 2000), (cls.small, 500))):
            EventBooking.objects.create(
                event=event, user=User.objects.create_user(f'buyer{index}', password='pw'),
                status='confirmed', attendee_name=f'Buyer {index}',
                amount=Decimal(amount), total_amount=Decimal(amount),
            )

    def test_page_renders_with_a_bar_for_each_earning_event(self):
        self.client.force_login(self.organiser)
        response = self.client.get(reverse('events:revenue_detail'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sold Out Show')
        self.assertContains(response, 'Quiet Evening')
        # Both bars are measured against the best event, so neither can exceed its own max
        self.assertContains(response, 'max="6000"', count=2)
        self.assertNotContains(response, 'max="0"')
