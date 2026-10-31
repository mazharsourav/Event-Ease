"""The printed ticket: its reference, its PDF, and the page its QR code leads to."""
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from reportlab.lib.units import mm

from apps.payments.models import Payment

from .models import EventBooking
from .tests import make_event
from .tickets import (CARD_W, MARGIN, MIN_CARD_H, PAD, PAGE_H, STUB_W, _face_plan, _ticket_rows,
                      ticket_filename, ticket_pdf)

FACE_W = CARD_W - STUB_W - 2 * PAD


class TicketFixture:
    """One confirmed, paid booking for a paid event, plus the people around it."""

    @classmethod
    def setUpTestData(cls):
        cls.organiser = User.objects.create_user('organiser', password='pw', email='org@example.com')
        cls.organiser.profile.role = 'event_manager'
        cls.organiser.profile.save()

        cls.holder = User.objects.create_user('holder', password='pw', email='holder@example.com',
                                              first_name='Ayesha', last_name='Rahman')
        cls.stranger = User.objects.create_user('stranger', password='pw')
        cls.admin = User.objects.create_user('boss', password='pw')
        cls.admin.profile.role = 'admin'
        cls.admin.profile.save()

        cls.event = make_event(cls.organiser, 'Sunset Sessions')
        cls.booking = EventBooking.objects.create(
            event=cls.event, user=cls.holder, status='confirmed', attendees_count=2,
            attendee_name='Ayesha Rahman', attendee_email='holder@example.com',
            amount=1000, total_amount=1000,
        )
        Payment.objects.create(
            booking=cls.booking, user=cls.holder, amount=1000, payment_method='bkash',
            payment_status='completed', transaction_id='TRX-77001',
            billing_name='Ayesha Rahman', billing_email='holder@example.com',
        )

    def ticket_url(self, booking=None):
        return reverse('events:download_ticket', args=[(booking or self.booking).pk])


class BookingReferenceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organiser = User.objects.create_user('organiser', password='pw')
        cls.event = make_event(cls.organiser)

    def booking(self, **extra):
        user = User.objects.create_user(f'member{extra.pop("n", 1)}', password='pw')
        return EventBooking.objects.create(event=self.event, user=user, **extra)

    def test_a_reference_is_padded_and_prefixed(self):
        booking = self.booking()
        self.assertEqual(booking.reference, f'EE-{booking.pk:06d}')

    def test_a_reference_finds_its_booking_again(self):
        booking = self.booking()
        self.assertEqual(EventBooking.from_reference(booking.reference), booking)

    def test_lower_case_and_stray_spaces_are_forgiven(self):
        booking = self.booking()
        self.assertEqual(EventBooking.from_reference(f'  {booking.reference.lower()} '), booking)

    def test_anything_else_is_not_a_reference(self):
        for text in ['', None, 'EE-', 'hello', 'EE-12x', '12345', 'EE-0000001234567']:
            self.assertIsNone(EventBooking.from_reference(text), text)

    def test_a_reference_for_a_deleted_booking_finds_nothing(self):
        booking = self.booking()
        reference = booking.reference
        booking.delete()
        self.assertIsNone(EventBooking.from_reference(reference))

    def test_only_a_held_place_carries_a_ticket(self):
        self.assertTrue(self.booking(status='confirmed', n=2).has_ticket)
        self.assertTrue(self.booking(status='attended', n=3).has_ticket)
        self.assertFalse(self.booking(status='pending', n=4).has_ticket)
        self.assertFalse(self.booking(status='cancelled', n=5).has_ticket)


class TicketPdfTests(TicketFixture, TestCase):
    def test_the_pdf_is_a_pdf_and_is_not_empty(self):
        pdf = ticket_pdf(self.booking, 'https://example.com/events/ticket/EE-000001/')

        self.assertTrue(pdf.startswith(b'%PDF'))
        self.assertTrue(pdf.rstrip().endswith(b'%%EOF'))
        self.assertGreater(len(pdf), 3000)  # the QR image alone is bigger than a text-only page

    def test_the_rows_say_what_the_gate_and_the_holder_need(self):
        rows = dict(_ticket_rows(self.booking))

        self.assertEqual(rows['Ticket holder'], 'Ayesha Rahman')
        self.assertIn('Open Air Hall', rows['Where'])
        self.assertIn('BDT 1,000.00', rows['Paid'])
        self.assertIn('bKash', rows['Paid'])
        self.assertIn(self.booking.reference, rows['Booking'])
        self.assertEqual(rows['Transaction'], 'TRX-77001')

    def test_a_free_booking_has_no_payment_to_print(self):
        free_event = make_event(self.organiser, 'Open Mic Night', is_free=True, ticket_price=0)
        booking = EventBooking.objects.create(event=free_event, user=self.stranger, status='confirmed',
                                              attendees_count=1, amount=0, total_amount=0)

        rows = dict(_ticket_rows(booking))

        self.assertEqual(rows['Paid'], 'Free event')
        self.assertEqual(rows['Transaction'], 'Not applicable')
        self.assertTrue(ticket_pdf(booking, 'https://example.com/').startswith(b'%PDF'))

    def test_a_long_title_shrinks_to_two_lines(self):
        self.event.title = 'The Very Long Winter Jazz And Poetry Marathon Of Greater Dhaka 2026'
        plan = _face_plan(self.booking, FACE_W)

        self.assertLessEqual(len(plan['title_lines']), 2)
        self.assertLess(plan['size'], 26)  # it had to come down from the largest size

    def test_a_crowded_ticket_grows_the_card_instead_of_spilling_off_it(self):
        """The card is drawn to fit what is on it, so a long address cannot fall off the bottom."""
        plain = _face_plan(self.booking, FACE_W)

        self.event.title = 'The Winter Jazz And Poetry Marathon Of Greater Dhaka 2026'
        self.event.venue_name = 'International Convention City Bashundhara, Hall Four'
        self.event.venue_address = 'Purbachal Express Highway, Kuril, Dhaka 1229, Bangladesh'
        self.booking.attendee_name = 'Mohammad Shahriar Kabir Chowdhury'
        crowded = _face_plan(self.booking, FACE_W)

        self.assertGreater(crowded['height'], plain['height'])
        card_height = max(MIN_CARD_H, crowded['height'] + 2 * PAD)
        # The masthead takes 14mm above the card, and the notes and footer 70mm below it.
        self.assertLess(card_height, PAGE_H - 2 * MARGIN - 14 * mm - 70 * mm)
        self.assertTrue(ticket_pdf(self.booking, 'https://example.com/').startswith(b'%PDF'))

    def test_the_filename_carries_the_reference(self):
        self.assertEqual(ticket_filename(self.booking), f'EventEase-ticket-{self.booking.reference}.pdf')


class TicketDownloadTests(TicketFixture, TestCase):
    def test_the_holder_downloads_their_ticket(self):
        self.client.force_login(self.holder)

        response = self.client.get(self.ticket_url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn(self.booking.reference, response['Content-Disposition'])
        self.assertTrue(response.content.startswith(b'%PDF'))

    def test_the_organiser_can_print_a_copy(self):
        self.client.force_login(self.organiser)
        self.assertEqual(self.client.get(self.ticket_url()).status_code, 200)

    def test_an_admin_can_print_a_copy(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(self.ticket_url()).status_code, 200)

    def test_nobody_else_is_told_the_booking_exists(self):
        self.client.force_login(self.stranger)
        self.assertEqual(self.client.get(self.ticket_url()).status_code, 404)

    def test_a_visitor_is_sent_to_log_in(self):
        response = self.client.get(self.ticket_url())
        self.assertIn(reverse('users:login'), response['Location'])

    def test_an_unconfirmed_booking_has_no_ticket_yet(self):
        self.booking.status = 'pending'
        self.booking.save()
        self.client.force_login(self.holder)

        response = self.client.get(self.ticket_url(), follow=True)

        self.assertRedirects(response, reverse('events:my_events'))
        self.assertContains(response, 'issued once the booking is confirmed')

    def test_the_qr_code_holds_the_address_of_the_gate_check(self):
        self.client.force_login(self.holder)

        with patch('apps.events.views.ticket_pdf', return_value=b'%PDF-stub') as pdf:
            self.client.get(self.ticket_url())

        _, verify_url = pdf.call_args.args
        self.assertEqual(verify_url,
                         'http://testserver' + reverse('events:ticket_check', args=[self.booking.reference]))


class GateCheckTests(TicketFixture, TestCase):
    def check_url(self, reference=None):
        return reverse('events:ticket_check', args=[reference or self.booking.reference])

    def test_the_organiser_is_told_to_admit_the_party(self):
        self.client.force_login(self.organiser)

        response = self.client.get(self.check_url())

        self.assertContains(response, 'Admit 2')
        self.assertContains(response, 'Ayesha Rahman')
        self.assertContains(response, 'Sunset Sessions')

    def test_a_cancelled_booking_is_refused_at_the_gate(self):
        self.booking.status = 'cancelled'
        self.booking.save()
        self.client.force_login(self.organiser)

        response = self.client.get(self.check_url())

        self.assertContains(response, 'Do not admit')
        self.assertContains(response, 'box office')

    def test_the_holder_sees_their_own_ticket(self):
        self.client.force_login(self.holder)
        response = self.client.get(self.check_url())
        self.assertContains(response, 'This is your own booking')

    def test_anyone_else_is_told_nothing_about_the_booking(self):
        self.client.force_login(self.stranger)

        response = self.client.get(self.check_url())

        self.assertContains(response, 'Only the organiser can check this')
        self.assertNotContains(response, 'Ayesha Rahman')
        self.assertNotContains(response, 'Admit')

    def test_an_invented_reference_is_not_one_of_ours(self):
        self.client.force_login(self.organiser)
        self.assertContains(self.client.get(self.check_url('EE-999999')), 'Not a ticket we issued')

    def test_a_reference_that_is_not_even_the_right_shape(self):
        self.client.force_login(self.organiser)
        self.assertContains(self.client.get(self.check_url('nonsense')), 'Not a ticket we issued')

    def test_a_visitor_is_sent_to_log_in(self):
        response = self.client.get(self.check_url())
        self.assertIn(reverse('users:login'), response['Location'])

    def test_the_page_is_markup_only(self):
        self.client.force_login(self.organiser)
        html = self.client.get(self.check_url()).content.decode()

        self.assertNotIn('<style', html)
        self.assertNotRegex(html, r'<script(?![^>]*\bsrc=)')
        self.assertNotIn('onclick=', html)
        self.assertNotIn(' style="', html)


class TicketLinkTests(TicketFixture, TestCase):
    def test_my_events_offers_the_ticket_for_a_confirmed_booking(self):
        self.client.force_login(self.holder)
        self.assertContains(self.client.get(reverse('events:my_events')), self.ticket_url())

    def test_my_events_offers_nothing_to_print_while_a_booking_waits(self):
        self.booking.status = 'pending'
        self.booking.save()
        self.client.force_login(self.holder)
        self.assertNotContains(self.client.get(reverse('events:my_events')), self.ticket_url())

    def test_the_payment_received_page_links_the_ticket(self):
        self.client.force_login(self.holder)
        payment = self.booking.payment

        response = self.client.get(reverse('payments:payment_success', args=[payment.pk]))

        self.assertContains(response, self.ticket_url())
        self.assertContains(response, 'QR code')

    def test_the_confirmation_email_points_at_the_ticket(self):
        from apps.notifications.emails import send_event_booking_confirmation
        from django.core import mail

        mail.outbox.clear()
        send_event_booking_confirmation(self.booking)

        self.assertIn(self.booking.reference, mail.outbox[0].body)
        self.assertIn('QR code', mail.outbox[0].body)
