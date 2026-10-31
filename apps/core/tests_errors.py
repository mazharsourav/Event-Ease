from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.views.defaults import server_error


def assert_clean(test, html):
    test.assertNotIn('<style', html)
    test.assertNotRegex(html, r'<script(?![^>]*\bsrc=)')
    test.assertNotIn('onclick=', html)
    test.assertNotIn(' style="', html)


@override_settings(DEBUG=False, ALLOWED_HOSTS=['testserver'])
class ErrorPageTests(TestCase):
    def test_missing_page_uses_the_site_frame(self):
        response = self.client.get('/no-such-page/')
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, '404.html')
        self.assertTemplateUsed(response, 'layout/header.html')
        self.assertContains(response, 'Page not found', status_code=404)
        assert_clean(self, response.content.decode())

    def test_missing_object_uses_the_same_page(self):
        response = self.client.get(reverse('events:event_detail', args=[999999]))
        self.assertTemplateUsed(response, '404.html')

    def test_forbidden_page_explains_and_offers_a_way_on(self):
        member = User.objects.create_user('member', password='pw')
        self.client.force_login(member)
        response = self.client.get(reverse('users:admin_comments_management'))
        self.assertIn(response.status_code, (302, 403))
        if response.status_code == 403:
            self.assertTemplateUsed(response, '403.html')
            assert_clean(self, response.content.decode())

    def test_server_error_page_stands_alone(self):
        response = server_error(RequestFactory().get('/'))
        html = response.content.decode()
        self.assertEqual(response.status_code, 500)
        self.assertIn('Something went wrong', html)
        self.assertNotIn('ee-nav', html)
        assert_clean(self, html)
