from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Event, TicketCategory


def make_event(organizer, title='Sunset Sessions', **extra):
    start = timezone.now() + timedelta(days=10)
    fields = dict(
        title=title,
        description='An evening of live music.',
        event_type='concert',
        organizer=organizer,
        venue_name='Open Air Hall',
        venue_address='1 Main Road, Dhaka',
        start_date=start,
        end_date=start + timedelta(hours=4),
        max_attendees=100,
        ticket_price=500,
        is_free=False,
        contact_email='hello@example.com',
    )
    fields.update(extra)
    return Event.objects.create(**fields)


class EventListTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organiser = User.objects.create_user('organiser', password='pw')
        cls.paid = make_event(cls.organiser, 'Sunset Sessions')
        cls.free = make_event(cls.organiser, 'Open Mic Night', is_free=True, ticket_price=0)

    def test_lists_every_active_event_with_its_status_stamp(self):
        response = self.client.get(reverse('events:event_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sunset Sessions')
        self.assertContains(response, 'Open Mic Night')
        self.assertContains(response, 'Coming up')

    def test_free_filter_keeps_only_free_events(self):
        response = self.client.get(reverse('events:event_list'), {'free': 'true'})
        self.assertContains(response, 'Open Mic Night')
        self.assertNotContains(response, 'Sunset Sessions')

    def test_search_with_no_match_shows_the_empty_state(self):
        response = self.client.get(reverse('events:event_list'), {'q': 'zzzz'})
        self.assertContains(response, 'Nothing matches')

    def test_filter_chips_keep_the_other_filters(self):
        response = self.client.get(reverse('events:event_list'), {'q': 'sun', 'free': 'false'})
        self.assertContains(response, 'q=sun')

    def test_page_has_no_inline_scripts_styles_or_handlers(self):
        html = self.client.get(reverse('events:event_list')).content.decode()
        self.assertNotIn('<style', html)
        self.assertNotRegex(html, r'<script(?![^>]*\bsrc=)')
        self.assertNotIn('onclick=', html)


class EventDetailTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organiser = User.objects.create_user('organiser', password='pw')
        cls.member = User.objects.create_user('member', password='pw')
        cls.event = make_event(cls.organiser)

    def url(self, event=None):
        return reverse('events:event_detail', args=[(event or self.event).pk])

    def test_visitor_is_asked_to_log_in_to_book(self):
        response = self.client.get(self.url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Log in to book')
        self.assertContains(response, '&#2547;500')

    def test_member_sees_a_single_ticket_link_when_there_are_no_tiers(self):
        self.client.force_login(self.member)
        response = self.client.get(self.url())
        self.assertContains(response, reverse('events:event_book', args=[self.event.pk]))
        self.assertNotContains(response, 'data-ee-tickets')

    def test_tiers_render_a_stepper_for_each_available_category(self):
        TicketCategory.objects.create(event=self.event, name='General', price=500, quantity_available=10)
        TicketCategory.objects.create(event=self.event, name='VIP', price=1500, quantity_available=5)
        self.client.force_login(self.member)
        response = self.client.get(self.url())
        self.assertContains(response, 'data-ee-tickets')
        self.assertContains(response, 'data-qty', count=2)
        self.assertContains(response, 'VIP')
        self.assertContains(response, 'data-max-tickets="6"')

    def test_closed_registration_replaces_the_ticket_picker(self):
        event = make_event(self.organiser, 'Closed Night', registration_deadline=timezone.now() - timedelta(days=1))
        self.client.force_login(self.member)
        response = self.client.get(self.url(event))
        self.assertContains(response, 'Registration closed')
        self.assertNotContains(response, 'data-checkout')

    def test_only_the_organiser_sees_edit_and_delete(self):
        self.client.force_login(self.member)
        self.assertNotContains(self.client.get(self.url()), 'Edit event')
        self.client.force_login(self.organiser)
        self.assertContains(self.client.get(self.url()), 'Edit event')

    def test_comments_render_with_reply_and_like_hooks(self):
        from .models import EventComment
        EventComment.objects.create(event=self.event, user=self.member, comment='Is there parking?')
        self.client.force_login(self.organiser)
        response = self.client.get(self.url())
        self.assertContains(response, 'Is there parking?')
        self.assertContains(response, 'data-action="reply"')
        self.assertContains(response, 'data-action="like"')
        self.assertContains(response, 'data-ee-comments')

    def test_page_has_no_inline_scripts_styles_or_handlers(self):
        self.client.force_login(self.member)
        html = self.client.get(self.url()).content.decode()
        self.assertNotIn('<style', html)
        self.assertNotRegex(html, r'<script(?![^>]*\bsrc=)')
        self.assertNotIn('onclick=', html)
        self.assertNotIn(' style="', html)
