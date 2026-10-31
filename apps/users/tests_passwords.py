"""Signing in, signing up and getting back in after forgetting a password."""
import re

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase
from django.urls import reverse


def assert_clean(test, html):
    test.assertNotIn('<style', html)
    test.assertNotRegex(html, r'<script(?![^>]*\bsrc=)')
    test.assertNotIn('onclick=', html)
    test.assertNotIn(' style="', html)


class PasswordResetTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            'forgetful', email='forgetful@example.com', password='the-old-password-1', first_name='Fara')

    def ask_for_a_link(self, email='forgetful@example.com'):
        return self.client.post(reverse('users:password_reset'), {'email': email})

    @staticmethod
    def link_from_the_email():
        return re.search(r'https?://[^\s]+', mail.outbox[0].body).group(0).split('testserver')[-1]

    def test_the_login_page_offers_a_way_out(self):
        response = self.client.get(reverse('users:login'))
        self.assertContains(response, reverse('users:password_reset'))
        assert_clean(self, response.content.decode())

    def test_the_whole_round_trip(self):
        self.assertRedirects(self.ask_for_a_link(), reverse('users:password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, 'Reset your EventEase password')
        self.assertEqual(mail.outbox[0].to, ['forgetful@example.com'])
        self.assertIn('Fara', mail.outbox[0].body)

        # The emailed link redirects to the page that takes a new password
        set_password_page = self.client.get(self.link_from_the_email())['Location']
        self.assertContains(self.client.get(set_password_page), 'New password')

        response = self.client.post(set_password_page, {
            'new_password1': 'a-brand-new-password-9', 'new_password2': 'a-brand-new-password-9'})
        self.assertRedirects(response, reverse('users:password_reset_complete'))

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('a-brand-new-password-9'))
        self.assertTrue(self.client.login(username='forgetful', password='a-brand-new-password-9'))

    def test_a_link_only_works_once(self):
        self.ask_for_a_link()
        link = self.link_from_the_email()
        set_password_page = self.client.get(link)['Location']
        self.client.post(set_password_page, {
            'new_password1': 'a-brand-new-password-9', 'new_password2': 'a-brand-new-password-9'})

        self.assertContains(self.client.get(link), 'Link expired')

    def test_an_invented_token_is_refused(self):
        response = self.client.get(reverse('users:password_reset_confirm', args=['MTc', 'made-up-token']))
        self.assertContains(response, 'Link expired')

    def test_an_unknown_address_says_the_same_thing_and_sends_nothing(self):
        """Answering differently would reveal which addresses have accounts."""
        self.assertRedirects(self.ask_for_a_link('nobody@example.com'), reverse('users:password_reset_done'))
        self.assertEqual(len(mail.outbox), 0)

    def test_the_two_new_passwords_have_to_match(self):
        self.ask_for_a_link()
        set_password_page = self.client.get(self.link_from_the_email())['Location']
        response = self.client.post(set_password_page, {
            'new_password1': 'a-brand-new-password-9', 'new_password2': 'something-else-entirely'})

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('the-old-password-1'))

    def test_every_page_in_the_flow_is_markup_only(self):
        self.ask_for_a_link()
        pages = [reverse('users:password_reset'), reverse('users:password_reset_done'),
                 reverse('users:password_reset_complete'), self.link_from_the_email()]
        for page in pages:
            response = self.client.get(page, follow=True)
            self.assertEqual(response.status_code, 200, page)
            assert_clean(self, response.content.decode())


class PasswordChangeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('member', email='member@example.com', password='the-old-password-1')

    def test_a_visitor_is_sent_to_log_in(self):
        response = self.client.get(reverse('users:password_change'))
        self.assertIn(reverse('users:login'), response['Location'])

    def test_a_member_changes_their_password(self):
        self.client.force_login(self.user)
        page = self.client.get(reverse('users:password_change'))
        self.assertEqual(page.status_code, 200)
        assert_clean(self, page.content.decode())

        response = self.client.post(reverse('users:password_change'), {
            'old_password': 'the-old-password-1',
            'new_password1': 'a-brand-new-password-9',
            'new_password2': 'a-brand-new-password-9',
        })
        self.assertRedirects(response, reverse('users:password_change_done'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('a-brand-new-password-9'))

    def test_the_current_password_has_to_be_right(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('users:password_change'), {
            'old_password': 'not-the-old-one',
            'new_password1': 'a-brand-new-password-9',
            'new_password2': 'a-brand-new-password-9',
        })
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('the-old-password-1'))

    def test_the_profile_page_links_to_it(self):
        self.client.force_login(self.user)
        self.assertContains(self.client.get(reverse('users:profile')), reverse('users:password_change'))


class EmailAddressIsUniqueTests(TestCase):
    """One address means one account, because that is what a password reset is sent to."""

    def signup(self, username, email):
        return self.client.post(reverse('users:signup'), {
            'first_name': 'Sam', 'last_name': 'Ray', 'username': username, 'email': email,
            'password1': 'long-enough-password', 'password2': 'long-enough-password',
        })

    def test_a_second_account_cannot_reuse_an_address(self):
        self.signup('first', 'shared@example.com')
        self.client.logout()

        response = self.signup('second', 'shared@example.com')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'already uses that email')
        self.assertEqual(User.objects.filter(email__iexact='shared@example.com').count(), 1)

    def test_the_check_ignores_capitals(self):
        self.signup('first', 'shared@example.com')
        self.client.logout()
        self.signup('second', 'SHARED@EXAMPLE.COM')
        self.assertEqual(User.objects.filter(email__iexact='shared@example.com').count(), 1)

    def test_a_taken_username_is_reported_plainly(self):
        self.signup('taken', 'one@example.com')
        self.client.logout()
        response = self.signup('taken', 'two@example.com')
        self.assertContains(response, 'username is taken')

    def test_logging_in_by_email_survives_accounts_that_already_share_one(self):
        """Accounts made before the rule, or through the Django admin, can still collide."""
        User.objects.create_user('older', email='same@example.com', password='password-for-older')
        User.objects.create_user('newer', email='same@example.com', password='password-for-newer')

        response = self.client.post(reverse('users:login'),
                                    {'username': 'same@example.com', 'password': 'password-for-newer'})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(int(self.client.session['_auth_user_id']), User.objects.get(username='newer').pk)
