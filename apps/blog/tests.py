import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import BlogComment, BlogPost, BlogReaction


def assert_clean(test, html):
    test.assertNotIn('<style', html)
    test.assertNotRegex(html, r'<script(?![^>]*\bsrc=)')
    test.assertNotIn('onclick=', html)
    test.assertNotIn(' style="', html)


class BlogTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = User.objects.create_user('author', password='pw', first_name='Ada', last_name='Lovelace')
        cls.reader = User.objects.create_user('reader', password='pw')
        cls.post = BlogPost.objects.create(author=cls.author, title='Ten tips for a first festival', content='Bring water.\n\nWear comfy shoes.')


class BlogListTests(BlogTestCase):
    def test_anyone_can_read_the_list(self):
        response = self.client.get(reverse('blog:blog_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ten tips for a first festival')
        self.assertContains(response, 'Log in to write a post')
        assert_clean(self, response.content.decode())

    def test_signed_in_member_gets_reaction_buttons_and_a_write_link(self):
        BlogReaction.objects.create(post=self.post, user=self.reader, reaction_type='like')
        self.client.force_login(self.reader)
        response = self.client.get(reverse('blog:blog_list'))
        self.assertContains(response, 'data-react')
        self.assertContains(response, 'aria-pressed="true"')
        self.assertContains(response, reverse('blog:blog_create'))

    def test_empty_list_has_its_own_state(self):
        BlogPost.objects.all().delete()
        self.assertContains(self.client.get(reverse('blog:blog_list')), 'No posts yet')


class BlogDetailTests(BlogTestCase):
    def test_visitor_can_read_a_post_but_is_asked_to_log_in_to_comment(self):
        response = self.client.get(reverse('blog:blog_detail', args=[self.post.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Wear comfy shoes.')
        self.assertContains(response, 'to join the conversation')
        assert_clean(self, response.content.decode())

    def test_visitor_cannot_post_a_comment(self):
        response = self.client.post(reverse('blog:blog_detail', args=[self.post.pk]), {'content': 'Hi'})
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('users:login'), response['Location'])
        self.assertEqual(BlogComment.objects.count(), 0)

    def test_member_comments_and_replies(self):
        self.client.force_login(self.reader)
        url = reverse('blog:blog_detail', args=[self.post.pk])
        self.client.post(url, {'content': 'Great list!'})
        top = BlogComment.objects.get()
        self.client.post(url, {'content': 'Thank you', 'parent_id': top.pk})

        reply = BlogComment.objects.exclude(pk=top.pk).get()
        self.assertEqual(reply.parent, top)
        html = self.client.get(url).content.decode()
        self.assertIn('Great list!', html)
        self.assertIn('Thank you', html)
        assert_clean(self, html)

    def test_only_the_author_sees_edit_and_delete(self):
        url = reverse('blog:blog_detail', args=[self.post.pk])
        self.client.force_login(self.reader)
        self.assertNotContains(self.client.get(url), 'Edit post')
        self.client.force_login(self.author)
        self.assertContains(self.client.get(url), 'Edit post')


class BlogReactionTests(BlogTestCase):
    def setUp(self):
        self.client.force_login(self.reader)
        self.url = reverse('blog:blog_react', args=[self.post.pk])

    def test_reacting_twice_with_the_same_type_removes_it(self):
        first = json.loads(self.client.post(self.url, {'reaction_type': 'love'}).content)
        self.assertEqual((first['status'], first['reactions_count']), ('success', 1))
        second = json.loads(self.client.post(self.url, {'reaction_type': 'love'}).content)
        self.assertEqual((second['status'], second['reactions_count']), ('removed', 0))

    def test_unknown_reaction_is_refused(self):
        response = self.client.post(self.url, {'reaction_type': 'bogus'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(BlogReaction.objects.count(), 0)


class BlogCommentDeleteTests(BlogTestCase):
    def setUp(self):
        self.comment = BlogComment.objects.create(post=self.post, user=self.reader, content='Nice')
        self.url = reverse('blog:blog_comment_delete', args=[self.comment.pk])

    def test_author_can_delete_their_comment(self):
        self.client.force_login(self.reader)
        data = json.loads(self.client.post(self.url).content)
        self.assertTrue(data['success'])
        self.assertFalse(BlogComment.objects.exists())

    def test_someone_else_cannot(self):
        self.client.force_login(self.author)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 403)
        self.assertTrue(BlogComment.objects.exists())

    def test_staff_can_moderate(self):
        staff = User.objects.create_user('mod', password='pw', is_staff=True)
        self.client.force_login(staff)
        self.assertTrue(json.loads(self.client.post(self.url).content)['success'])


class BlogWriteTests(BlogTestCase):
    def test_form_page_is_markup_only(self):
        self.client.force_login(self.reader)
        response = self.client.get(reverse('blog:blog_create'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="images"')
        assert_clean(self, response.content.decode())

    def test_member_publishes_a_post(self):
        self.client.force_login(self.reader)
        response = self.client.post(reverse('blog:blog_create'), {'title': 'My first post', 'content': 'Hello there'})
        self.assertRedirects(response, reverse('blog:blog_list'))
        self.assertTrue(BlogPost.objects.filter(title='My first post', author=self.reader).exists())

    def test_only_the_author_can_edit(self):
        self.client.force_login(self.reader)
        url = reverse('blog:blog_edit', args=[self.post.pk])
        self.assertRedirects(self.client.get(url), reverse('blog:blog_detail', args=[self.post.pk]))

        self.client.force_login(self.author)
        response = self.client.post(url, {'title': 'Twelve tips', 'content': 'Updated'})
        self.assertRedirects(response, reverse('blog:blog_detail', args=[self.post.pk]))
        self.post.refresh_from_db()
        self.assertEqual(self.post.title, 'Twelve tips')

    def test_delete_needs_post_and_the_author(self):
        url = reverse('blog:blog_delete', args=[self.post.pk])
        self.client.force_login(self.reader)
        self.client.post(url)
        self.assertTrue(BlogPost.objects.filter(pk=self.post.pk).exists())
        self.client.force_login(self.author)
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.post(url)
        self.assertFalse(BlogPost.objects.filter(pk=self.post.pk).exists())
