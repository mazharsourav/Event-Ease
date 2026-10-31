from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Venue


def make_venue(manager, name='Grand Hall', **extra):
    fields = dict(
        name=name,
        description='A large hall in the middle of the city.',
        venue_type='conference_hall',
        manager=manager,
        address='1 Main Road',
        city='Dhaka',
        state='Dhaka',
        zipcode='1207',
        capacity=500,
        price_per_hour=2500,
        price_per_day=18000,
        has_parking=True,
        contact_email='owner@example.com',
        contact_phone='01700000000',
    )
    fields.update(extra)
    return Venue.objects.create(**fields)


class VenueListTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user('owner', password='pw')
        cls.hall = make_venue(cls.manager, 'Grand Hall')
        cls.ground = make_venue(cls.manager, 'Riverside Ground', capacity=5000, venue_type='outdoor_space')

    def test_lists_venues_with_price_and_capacity(self):
        response = self.client.get(reverse('venues:venue_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Grand Hall')
        self.assertContains(response, '&#2547;18,000 / day')

    def test_capacity_filter(self):
        response = self.client.get(reverse('venues:venue_list'), {'min_capacity': '1000'})
        self.assertContains(response, 'Riverside Ground')
        self.assertNotContains(response, 'Grand Hall')

    def test_no_match_shows_the_empty_state(self):
        response = self.client.get(reverse('venues:venue_list'), {'q': 'zzzz'})
        self.assertContains(response, 'Nothing matches')


class VenueDetailTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user('owner', password='pw')
        cls.venue = make_venue(cls.manager)

    def url(self):
        return reverse('venues:venue_detail', args=[self.venue.pk])

    def test_visitor_sees_price_amenities_and_a_login_prompt(self):
        response = self.client.get(self.url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '&#2547;18,000')
        self.assertContains(response, 'Parking')
        self.assertContains(response, 'Log in to book')

    def test_member_without_the_organiser_role_is_pointed_to_the_upgrade(self):
        member = User.objects.create_user('member', password='pw')
        self.client.force_login(member)
        response = self.client.get(self.url())
        self.assertContains(response, 'Become an organiser to book')
        self.assertNotContains(response, reverse('venues:venue_book', args=[self.venue.pk]))

    def test_organiser_can_request_a_booking(self):
        organiser = User.objects.create_user('organiser', password='pw')
        organiser.profile.role = 'event_manager'
        organiser.profile.save()
        self.client.force_login(organiser)
        response = self.client.get(self.url())
        self.assertContains(response, reverse('venues:venue_book', args=[self.venue.pk]))

    def test_only_the_owner_sees_edit_and_delete(self):
        member = User.objects.create_user('member', password='pw')
        self.client.force_login(member)
        self.assertNotContains(self.client.get(self.url()), 'Edit venue')
        self.client.force_login(self.manager)
        self.assertContains(self.client.get(self.url()), 'Edit venue')

    def test_page_has_no_inline_scripts_styles_or_handlers(self):
        html = self.client.get(self.url()).content.decode()
        self.assertNotIn('<style', html)
        self.assertNotRegex(html, r'<script(?![^>]*\bsrc=)')
        self.assertNotIn('onclick=', html)
        self.assertNotIn(' style="', html)
