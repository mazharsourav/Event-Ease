from django.contrib import messages
from django.contrib.auth.models import User
from django.template import Context, Template
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from .context_processors import site_frame


def make_request(user=None, path='/'):
    request = RequestFactory().get(path)
    request.user = user or _Anonymous()
    return request


class _Anonymous:
    is_authenticated = False


def make_user(role=None, **extra):
    user = User.objects.create_user(username=f'u-{role or "member"}', password='pw', **extra)
    if role:
        user.profile.role = role
        user.profile.save()
    return user


class SiteFrameTests(TestCase):
    def test_visitor_sees_the_three_public_links_and_signs_up_to_list(self):
        frame = site_frame(make_request())
        self.assertEqual([link['label'] for link in frame['nav_links']], ['Events', 'Venues', 'Blog'])
        self.assertEqual(frame['list_event_url'], reverse('users:signup'))
        self.assertEqual(frame['list_venue_url'], reverse('users:signup'))
        self.assertFalse(frame['can_list'])

    def test_member_without_a_role_is_sent_to_the_upgrade_form(self):
        frame = site_frame(make_request(make_user()))
        self.assertEqual(frame['list_event_url'], reverse('users:request_upgrade'))
        self.assertEqual(frame['list_venue_url'], reverse('users:request_upgrade'))
        self.assertFalse(frame['can_list'])

    def test_event_manager_can_create_events_but_not_venues(self):
        frame = site_frame(make_request(make_user('event_manager')))
        labels = [link['label'] for link in frame['nav_links']]
        self.assertIn('Create event', labels)
        self.assertNotIn('Add venue', labels)
        self.assertEqual(frame['list_event_url'], reverse('events:event_create'))
        self.assertEqual(frame['list_venue_url'], reverse('users:request_upgrade'))
        self.assertTrue(frame['can_list'])

    def test_current_section_is_marked(self):
        frame = site_frame(make_request(path=reverse('events:event_list')))
        current = {link['label']: link['current'] for link in frame['nav_links']}
        self.assertTrue(current['Events'])
        self.assertFalse(current['Venues'])


class AssetTagTests(TestCase):
    @override_settings(ASSET_VERSION='42')
    def test_asset_appends_the_release_version(self):
        html = Template("{% load core_tags %}{% asset 'css/core/base.css' %}").render(Context())
        self.assertTrue(html.endswith('/css/core/base.css?v=42'))


class FramePageTests(TestCase):
    def test_home_renders_the_shared_frame(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/home.html')
        self.assertTemplateUsed(response, 'layout/header.html')
        self.assertTemplateUsed(response, 'layout/footer.html')

    def test_frame_has_no_inline_scripts_or_styles(self):
        html = self.client.get(reverse('home')).content.decode()
        self.assertNotIn('<style', html)
        self.assertNotRegex(html, r'<script(?![^>]*\bsrc=)')
        self.assertNotIn(' style="', html)

    def test_signed_in_header_carries_the_badge_endpoints(self):
        self.client.force_login(make_user())
        html = self.client.get(reverse('home')).content.decode()
        self.assertIn('data-ee-badges', html)
        self.assertIn(reverse('notifications:notification_count_api'), html)

    def test_messages_render_as_toasts(self):
        self.client.force_login(make_user())
        session = self.client.session
        session.save()
        response = self.client.get(reverse('home'))
        request = response.wsgi_request
        messages.success(request, 'Saved.')
        html = Template("{% include 'layout/toasts.html' %}").render(Context({'messages': messages.get_messages(request)}))
        self.assertIn('ee-toast--success', html)
        self.assertIn('Saved.', html)
