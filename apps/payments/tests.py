from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.events.models import BookingTicketItem, EventBooking, TicketCategory
from apps.events.tests import make_event
from apps.venues.models import VenueBooking
from apps.venues.tests import make_venue

from .models import Payment


def assert_clean(test, html):
    """The shared frame's rule: markup only, no inline CSS, JS or handlers."""
    test.assertNotIn('<style', html)
    test.assertNotRegex(html, r'<script(?![^>]*\bsrc=)')
    test.assertNotIn('onclick=', html)
    test.assertNotIn(' style="', html)


class BookingFixture:
    """A member, an event with two ticket tiers, and a helper that books two General tickets."""

    @classmethod
    def setUpTestData(cls):
        cls.organiser = User.objects.create_user('organiser', password='pw')
        cls.member = User.objects.create_user('member', password='pw', email='m@example.com')
        cls.event = make_event(cls.organiser, 'Sunset Sessions')
        cls.general = TicketCategory.objects.create(event=cls.event, name='General', price=500, quantity_available=20)
        cls.vip = TicketCategory.objects.create(event=cls.event, name='VIP', price=1500, quantity_available=5)

    def setUp(self):
        self.client.force_login(self.member)

    def booking(self, **extra):
        fields = dict(
            event=self.event, user=self.member, attendee_name='Member One', attendee_email='m@example.com',
            attendee_phone='01700000000', amount=Decimal('1000'), total_amount=Decimal('1000'), attendees_count=2,
        )
        fields.update(extra)
        booking = EventBooking.objects.create(**fields)
        BookingTicketItem.objects.create(booking=booking, ticket_category=self.general, quantity=2, price_per_ticket=500)
        return booking


class BookingFlowPagesTests(BookingFixture, TestCase):
    def test_booking_form_without_a_selection_shows_the_ticket_steppers(self):
        response = self.client.get(reverse('events:event_book', args=[self.event.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-ee-tickets')
        self.assertContains(response, 'name="quantity_%d"' % self.general.pk)
        assert_clean(self, response.content.decode())

    def test_checkout_shows_the_chosen_tickets_and_total(self):
        url = reverse('events:event_book', args=[self.event.pk])
        response = self.client.get(url, {'quantity_%d' % self.general.pk: 2, 'quantity_%d' % self.vip.pk: 1})
        self.assertContains(response, 'General &times; 2', html=False)
        self.assertContains(response, '&#2547;2,500')
        self.assertContains(response, 'type="hidden" name="quantity_%d" value="1"' % self.vip.pk)
        self.assertNotContains(response, 'data-ee-tickets')

    def test_posting_the_checkout_creates_a_booking_and_goes_to_payment(self):
        url = reverse('events:event_book', args=[self.event.pk])
        response = self.client.post(url, {
            'attendee_name': 'Member One', 'attendee_email': 'm@example.com', 'attendee_phone': '01700000000',
            'quantity_%d' % self.general.pk: 2,
        })
        booking = EventBooking.objects.get(event=self.event, user=self.member)
        self.assertRedirects(response, reverse('payments:payment_process', args=[booking.pk]))

    def test_invalid_booking_form_keeps_the_field_errors(self):
        url = reverse('events:event_book', args=[self.event.pk])
        response = self.client.post(url, {'attendee_name': '', 'quantity_%d' % self.general.pk: 1})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'ee-form-error')

    def test_cancel_booking_page(self):
        booking = self.booking()
        response = self.client.get(reverse('events:cancel_booking', args=[booking.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Yes, cancel my booking')
        assert_clean(self, response.content.decode())

    def test_payment_page_lists_the_methods_and_the_order(self):
        booking = self.booking()
        response = self.client.get(reverse('payments:payment_process', args=[booking.pk]))
        self.assertEqual(response.status_code, 200)
        for method in ('bkash', 'nagad', 'credit_card', 'debit_card', 'paypal'):
            self.assertContains(response, 'value="%s"' % method)
        self.assertContains(response, 'General &times; 2')
        assert_clean(self, response.content.decode())

    def test_wallet_pages_post_to_their_processors(self):
        booking = self.booking()
        bkash = self.client.get(reverse('payments:bkash_payment', args=[booking.pk]))
        self.assertContains(bkash, reverse('payments:bkash_process', args=[booking.pk]))
        self.assertContains(bkash, 'data-pin-length="5"')
        nagad = self.client.get(reverse('payments:nagad_payment', args=[booking.pk]))
        self.assertContains(nagad, reverse('payments:nagad_process', args=[booking.pk]))
        self.assertContains(nagad, 'data-pin-length="6"')
        assert_clean(self, bkash.content.decode())
        assert_clean(self, nagad.content.decode())

    def test_payment_success_and_cancel_pages(self):
        booking = self.booking()
        payment = Payment.objects.create(
            booking=booking, user=self.member, amount=1000, payment_method='bkash', payment_status='completed',
            transaction_id='TXN123', billing_name='Member One', billing_email='m@example.com',
        )
        payment.mark_as_paid()

        success = self.client.get(reverse('payments:payment_success', args=[payment.pk]))
        self.assertContains(success, 'TXN123')
        self.assertContains(success, booking.reference)
        self.assertContains(success, reverse('events:download_ticket', args=[booking.pk]))
        cancel = self.client.get(reverse('payments:payment_cancel', args=[booking.pk]))
        self.assertContains(cancel, 'Try again')
        assert_clean(self, success.content.decode())
        assert_clean(self, cancel.content.decode())


class VenueBookingPagesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user('owner', password='pw')
        cls.organiser = User.objects.create_user('organiser', password='pw')
        cls.organiser.profile.role = 'event_manager'
        cls.organiser.profile.save()
        cls.venue = make_venue(cls.owner)
        start = timezone.now() + timedelta(days=20)
        cls.booking = VenueBooking.objects.create(
            venue=cls.venue, user=cls.organiser, event_title='Launch Night', event_description='A launch.',
            start_date=start, end_date=start + timedelta(hours=5), total_amount=12500,
            contact_email='o@example.com', contact_phone='01711111111',
        )

    def test_venue_booking_form_carries_the_rates_for_the_estimate(self):
        self.client.force_login(self.organiser)
        response = self.client.get(reverse('venues:venue_book', args=[self.venue.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-hourly="2500.00"')
        self.assertContains(response, 'name="accept_terms"')
        assert_clean(self, response.content.decode())

    def test_booking_details_page_and_pop_up_share_the_facts(self):
        self.client.force_login(self.organiser)
        url = reverse('venues:booking_details', args=[self.booking.pk])
        page = self.client.get(url)
        self.assertContains(page, 'Launch Night')
        self.assertContains(page, 'Cancel booking')
        assert_clean(self, page.content.decode())
        popup = self.client.get(url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertContains(popup, 'Launch Night')
        self.assertNotContains(popup, '<html')


class QuickPayTests(BookingFixture, TestCase):
    """Quick pay marks a booking paid with no gateway, so it must exist only in development."""

    def test_button_is_hidden_and_endpoint_refuses_outside_debug(self):
        booking = self.booking()
        page = self.client.get(reverse('payments:payment_process', args=[booking.pk]))
        self.assertNotContains(page, 'Quick pay')

        response = self.client.post(reverse('payments:quick_pay', args=[booking.pk]))
        self.assertEqual(response.status_code, 404)
        booking.refresh_from_db()
        self.assertNotEqual(booking.payment_status, 'completed')

    @override_settings(DEBUG=True)
    def test_in_development_the_button_shows_and_the_booking_is_paid(self):
        booking = self.booking()
        page = self.client.get(reverse('payments:payment_process', args=[booking.pk]))
        self.assertContains(page, 'data-url="%s"' % reverse('payments:quick_pay', args=[booking.pk]))

        response = self.client.post(reverse('payments:quick_pay', args=[booking.pk]))
        self.assertEqual(response.status_code, 200)
        booking.refresh_from_db()
        self.assertEqual(booking.payment_status, 'completed')
        self.assertEqual(booking.status, 'confirmed')

def gateway_response(payload):
    """A stand-in for what `requests` hands back from SSLCommerz."""
    reply = Mock()
    reply.status_code = 200
    reply.json.return_value = payload
    reply.text = str(payload)
    return reply


class WalletFormTests(BookingFixture, TestCase):
    """bKash and Nagad collect a number and a PIN before anything reaches the gateway."""

    def test_a_bad_mobile_number_never_reaches_the_gateway(self):
        booking = self.booking()

        with patch('apps.payments.views.requests.post') as post:
            response = self.client.post(reverse('payments:bkash_process', args=[booking.pk]),
                                        {'mobile': '55', 'pin': '12345'}, follow=True)

        post.assert_not_called()
        self.assertContains(response, 'valid mobile number')

    def test_a_short_bkash_pin_is_refused(self):
        booking = self.booking()

        with patch('apps.payments.views.requests.post') as post:
            response = self.client.post(reverse('payments:bkash_process', args=[booking.pk]),
                                        {'mobile': '1711223344', 'pin': '12'}, follow=True)

        post.assert_not_called()
        self.assertContains(response, '5-digit bKash PIN')

    def test_nagad_will_not_go_on_without_the_terms(self):
        booking = self.booking()

        with patch('apps.payments.views.requests.post') as post:
            response = self.client.post(reverse('payments:nagad_process', args=[booking.pk]),
                                        {'mobile': '1711223344', 'pin': '123456'}, follow=True)

        post.assert_not_called()
        self.assertContains(response, 'Terms &amp; Conditions')

    def test_a_filled_in_bkash_form_opens_a_gateway_session(self):
        booking = self.booking()
        reply = gateway_response({'status': 'SUCCESS', 'GatewayPageURL': 'https://sandbox.sslcommerz.com/pay/abc'})

        with patch('apps.payments.views.requests.post', return_value=reply) as post:
            response = self.client.post(reverse('payments:bkash_process', args=[booking.pk]),
                                        {'mobile': '1711223344', 'pin': '12345'})

        self.assertEqual(response['Location'], 'https://sandbox.sslcommerz.com/pay/abc')
        sent = post.call_args.kwargs['data']
        self.assertEqual(sent['total_amount'], '1000.00')
        self.assertEqual(sent['currency'], 'BDT')
        self.assertEqual(sent['value_a'], str(booking.pk))

        payment = Payment.objects.get(booking=booking)
        self.assertEqual(payment.payment_method, 'bkash')
        self.assertEqual(payment.payment_status, 'pending')
        self.assertEqual(payment.billing_phone, '8801711223344')
        self.assertTrue(payment.transaction_id.startswith('SSL_'))

    def test_a_refused_session_sends_the_person_back_to_the_payment_page(self):
        booking = self.booking()
        reply = gateway_response({'status': 'FAILED', 'failedreason': 'Store is inactive'})

        with patch('apps.payments.views.requests.post', return_value=reply):
            response = self.client.post(reverse('payments:bkash_process', args=[booking.pk]),
                                        {'mobile': '1711223344', 'pin': '12345'}, follow=True)

        self.assertContains(response, 'Store is inactive')
        self.assertEqual(Payment.objects.get(booking=booking).payment_status, 'pending')

    def test_an_unreachable_gateway_leaves_the_booking_alone(self):
        booking = self.booking()

        with patch('apps.payments.views.requests.post', side_effect=OSError('connection refused')):
            with self.assertLogs('apps.payments.views', level='ERROR'):
                response = self.client.post(reverse('payments:nagad_process', args=[booking.pk]),
                                            {'mobile': '1711223344', 'pin': '123456', 'terms': 'on'}, follow=True)

        self.assertContains(response, 'Payment gateway error')
        booking.refresh_from_db()
        self.assertNotEqual(booking.payment_status, 'completed')


class SslCallbackTests(BookingFixture, TestCase):
    """What the gateway sends back, and what it is allowed to change."""

    def setUp(self):
        super().setUp()
        self.booking_record = self.booking()
        self.payment = Payment.objects.create(
            booking=self.booking_record, user=self.member, amount=Decimal('1000'), payment_method='bkash',
            payment_status='pending', transaction_id='SSL_TEST123', payment_gateway='sslcommerz',
            billing_name='Member One', billing_email='m@example.com')

    def callback(self, url_name, validation, **post):
        fields = {'tran_id': 'SSL_TEST123', 'val_id': 'VAL1', 'bank_tran_id': 'BANK1'}
        fields.update(post)
        with patch('apps.payments.views.requests.get', return_value=gateway_response(validation)):
            return self.client.post(reverse(url_name), fields, follow=True)

    def test_a_validated_payment_confirms_the_booking(self):
        response = self.callback('payments:ssl_success', {'status': 'VALID', 'amount': '1000.00'})

        self.payment.refresh_from_db()
        self.booking_record.refresh_from_db()
        self.assertEqual(self.payment.payment_status, 'completed')
        self.assertEqual(self.payment.bank_transaction_id, 'BANK1')
        self.assertIsNotNone(self.payment.paid_at)
        self.assertEqual(self.booking_record.status, 'confirmed')
        self.assertContains(response, 'Payment successful')

    def test_a_callback_that_reports_too_little_money_pays_for_nothing(self):
        """The success callback arrives through the customer's own browser."""
        with self.assertLogs('apps.payments.views', level='ERROR'):
            response = self.callback('payments:ssl_success', {'status': 'VALID', 'amount': '1.00'})

        self.payment.refresh_from_db()
        self.assertEqual(self.payment.payment_status, 'pending')
        self.assertContains(response, 'did not match this booking')

    def test_a_validation_that_fails_pays_for_nothing(self):
        self.callback('payments:ssl_success', {'status': 'INVALID_TRANSACTION', 'amount': '1000.00'})

        self.payment.refresh_from_db()
        self.assertEqual(self.payment.payment_status, 'pending')

    def test_a_transaction_we_do_not_know_is_reported_not_crashed(self):
        response = self.callback('payments:ssl_success', {'status': 'VALID', 'amount': '1000.00'},
                                 tran_id='SSL_SOMEONE_ELSE')

        self.assertContains(response, 'Payment record not found')
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.payment_status, 'pending')

    def test_a_failed_payment_is_marked_failed(self):
        self.client.post(reverse('payments:ssl_fail'), {'tran_id': 'SSL_TEST123'})

        self.payment.refresh_from_db()
        self.booking_record.refresh_from_db()
        self.assertEqual(self.payment.payment_status, 'failed')
        self.assertEqual(self.booking_record.status, 'cancelled')

    def test_backing_out_leaves_the_payment_where_it_was(self):
        response = self.client.post(reverse('payments:ssl_cancel'), {'tran_id': 'SSL_TEST123'}, follow=True)

        self.payment.refresh_from_db()
        self.booking_record.refresh_from_db()
        self.assertEqual(self.payment.payment_status, 'pending')
        self.assertEqual(self.booking_record.status, 'pending')
        self.assertContains(response, 'cancelled')

    def test_the_ipn_pays_a_booking_whose_browser_never_came_back(self):
        """The IPN is the reliable half of the gateway: it must work on its own."""
        with patch('apps.payments.views.requests.get',
                   return_value=gateway_response({'status': 'VALID', 'amount': '1000.00'})):
            response = self.client.post(reverse('payments:ssl_ipn'), {'tran_id': 'SSL_TEST123', 'val_id': 'VAL1'})

        self.assertEqual(response.json(), {'status': 'ok'})
        self.payment.refresh_from_db()
        self.booking_record.refresh_from_db()
        self.assertEqual(self.payment.payment_status, 'completed')
        self.assertEqual(self.booking_record.status, 'confirmed')

    def test_the_ipn_answers_even_when_it_cannot_make_sense_of_the_call(self):
        with patch('apps.payments.views.requests.get', side_effect=OSError('gateway down')):
            with self.assertLogs('apps.payments.views', level='ERROR'):
                response = self.client.post(reverse('payments:ssl_ipn'), {'tran_id': 'SSL_TEST123'})

        self.assertEqual(response.json(), {'status': 'ok'})
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.payment_status, 'pending')

    def test_an_ipn_for_an_amount_that_is_too_small_pays_nothing(self):
        with patch('apps.payments.views.requests.get',
                   return_value=gateway_response({'status': 'VALID', 'amount': '5.00'})):
            self.client.post(reverse('payments:ssl_ipn'), {'tran_id': 'SSL_TEST123', 'val_id': 'VAL1'})

        self.payment.refresh_from_db()
        self.assertEqual(self.payment.payment_status, 'pending')
