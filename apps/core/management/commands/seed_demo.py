"""Empty the database and fill it with demo data that exercises every feature of the site.

    python manage.py seed_demo --yes

This DELETES EVERYTHING (users, events, bookings, messages, sessions...). Take a copy of db.sqlite3 first if
you might want it back. Uploaded files already in media/ are left alone; the demo adds its own generated pictures.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.blog.models import BlogComment, BlogCommentImage, BlogPost, BlogPostFile, BlogPostImage, BlogReaction
from apps.core.demo import art, content
from apps.events.models import (BookingTicketItem, Event, EventBooking, EventComment, EventCommentLike, TicketCategory)
from apps.notifications.models import Notification
from apps.payments.models import Payment
from apps.reviews.models import EventReview, Review, VenueReview
from apps.users.models import FriendRequest, Friendship, Message, MessageFile, RoleUpgradeRequest
from apps.venues.models import Venue, VenueBooking, VenueComment, VenueCommentLike, VenueImage

AMENITY_FIELDS = {
    'parking': 'has_parking', 'wifi': 'has_wifi', 'catering': 'has_catering',
    'av': 'has_av_equipment', 'ac': 'has_air_conditioning', 'access': 'has_accessibility',
}


class Command(BaseCommand):
    help = 'Delete all data and create demo data for every feature (users, events, venues, bookings, reviews, blog, chat...).'

    def add_arguments(self, parser):
        parser.add_argument('--yes', action='store_true', help='Confirm that all existing data may be deleted.')

    def handle(self, *args, **options):
        if not options['yes']:
            raise CommandError('This deletes all data. Run again with --yes to confirm.')

        self.now = timezone.now()
        self.stdout.write('Emptying the database...')
        call_command('flush', interactive=False, verbosity=0)

        with transaction.atomic():
            self.users = self.make_users()
            self.venues = self.make_venues()
            self.events = self.make_events()
            self.make_event_bookings()
            self.make_venue_bookings()
            self.make_reviews()
            self.make_comments()
            self.make_blog()
            self.make_social()
            self.make_requests_and_notifications()

        self.report()

    # ---- helpers -------------------------------------------------------------------------------------------

    def at(self, days=0, hours=0):
        """A whole hour in the site's own timezone, so a replaced hour is the hour people read."""
        local = timezone.localtime(self.now + timedelta(days=days, hours=hours))
        return local.replace(minute=0, second=0, microsecond=0)

    @staticmethod
    def backdate(obj, **fields):
        """Set auto_now_add fields, which a normal save would overwrite."""
        type(obj).objects.filter(pk=obj.pk).update(**fields)

    def done(self, label):
        self.stdout.write(f'  {label}')

    # ---- people --------------------------------------------------------------------------------------------

    def make_users(self):
        users = {}
        for index, (username, first, last, role, phone, bio) in enumerate(content.PEOPLE):
            is_admin = username == 'admin'
            user = User.objects.create_user(
                username=username, email=f'{username}@example.com',
                password=content.ADMIN_PASSWORD if is_admin else content.PASSWORD,
                first_name=first, last_name=last, is_staff=is_admin, is_superuser=is_admin,
            )
            profile = user.profile
            profile.role = role
            profile.phone = phone
            profile.bio = bio
            profile.address = 'House 12, Road 5, Dhanmondi, Dhaka'
            if username != 'newbie':
                profile.avatar.save(f'{username}.jpg', art.avatar_file(f'{username}.jpg', first[0] + last[0], index), save=False)
            profile.save()
            users[username] = user
        self.done(f'{len(users)} people')
        return users

    # ---- venues --------------------------------------------------------------------------------------------

    def make_venues(self):
        venues = {}
        for index, (key, name, kind, city, state, zipcode, capacity, hour, day, amenities, manager, description) in enumerate(content.VENUES):
            flags = {AMENITY_FIELDS[a]: True for a in amenities}
            venue = Venue.objects.create(
                name=name, description=description, venue_type=kind, manager=self.users[manager],
                address=f'{10 + index * 7} Main Road, {city}', city=city, state=state, zipcode=zipcode, country='Bangladesh',
                capacity=capacity, price_per_hour=hour, price_per_day=day,
                contact_email=f'{key}@venues.example.com', contact_phone=f'0171200{index:04d}',
                website=f'https://{key}.example.com',
                min_booking_hours=2, max_booking_days=14,
                rules_and_regulations='No smoking indoors.\nMusic must stop by 11 pm.\nDecorations must not damage walls.',
                cancellation_policy='Free cancellation up to 7 days before. 50% refund up to 48 hours before.',
                **flags,
            )
            venue.main_image.save(f'{key}.jpg', art.hall_file(f'{key}.jpg', name, palette=index), save=True)
            for shot in range(3):
                photo = VenueImage(venue=venue, caption=['Main hall', 'Entrance', 'Stage and lighting'][shot], is_primary=shot == 0)
                photo.image.save(f'{key}-{shot}.jpg', art.hall_file(f'{key}-{shot}.jpg', name, palette=index + shot + 1, seed=f'{key}{shot}'), save=True)
            venues[key] = venue
        self.done(f'{len(venues)} venues with photos')
        return venues

    # ---- events --------------------------------------------------------------------------------------------

    def make_events(self):
        organisers = [self.users['rafiq_events'], self.users['nusrat_org']]
        events = {}
        for index, (key, title, kind, venue_key, days, hours, maximum, price, free, tiers, palette, description) in enumerate(content.EVENTS):
            venue = self.venues.get(venue_key)
            # An explicit hour per event, so the demo never shows a concert at breakfast time.
            start = self.at(days=days).replace(hour=content.START_HOURS.get(key, 19))
            event = Event.objects.create(
                title=title, description=description, event_type=kind, organizer=organisers[index % 2],
                venue=venue, venue_name=venue.name if venue else 'Old Dhaka walking route',
                venue_address=f'{venue.address}, {venue.city}' if venue else 'Meet at Shankhari Bazar, Old Dhaka',
                start_date=start, end_date=start + timedelta(hours=hours),
                registration_deadline=(start - timedelta(hours=18)) if key in ('talk', 'jazz', 'photo') else None,
                max_attendees=maximum, ticket_price=price, is_free=free,
                contact_email='hello@eventease.example.com', contact_phone='01700000000',
                website='https://eventease.example.com',
                requirements='Please bring a photo ID. Gates close 30 minutes after the start.',
            )
            event.image.save(f'{key}.jpg', art.poster_file(f'{key}.jpg', title, start.strftime('%d %b %Y'), palette), save=True)
            for name, category, tier_price, quantity in tiers:
                TicketCategory.objects.create(event=event, name=name, category_type=category, price=tier_price,
                                              quantity_available=quantity, description=f'{name} entry for {title}.')
            events[key] = event
        gala = self.at(days=25).replace(hour=19)
        hidden = Event.objects.create(
            title='Cancelled Charity Gala', description='Hidden from listings: the organiser switched this event off.',
            event_type='party', organizer=organisers[0], venue_name='To be announced', venue_address='Dhaka',
            start_date=gala, end_date=gala + timedelta(hours=4), max_attendees=100, ticket_price=1000,
            is_free=False, contact_email='hello@eventease.example.com', is_active=False,
        )
        events['hidden'] = hidden
        self.done(f'{len(events)} events (upcoming, on now, finished, one hidden)')
        return events

    # ---- event bookings and payments -----------------------------------------------------------------------

    def book(self, event_key, username, status='confirmed', quantity=1, tier=None, method=None, pay=True):
        """One booking. Paid events get a payment record unless `pay` is false (a booking still waiting)."""
        event = self.events[event_key]
        user = self.users[username]
        name = user.get_full_name()
        booking = EventBooking.objects.create(
            event=event, user=user, status='pending', attendees_count=quantity, attendee_name=name,
            attendee_email=user.email, attendee_phone=user.profile.phone,
            special_requests='Wheelchair access please.' if username == 'sadia' else '',
            amount=0 if event.is_free else event.ticket_price * quantity,
            total_amount=0 if event.is_free else event.ticket_price * quantity,
        )
        if tier:
            category = TicketCategory.objects.get(event=event, name=tier)
            BookingTicketItem.objects.create(booking=booking, ticket_category=category, quantity=quantity,
                                             price_per_ticket=category.price)
            booking.refresh_from_db()

        paid = not event.is_free and pay and status in ('confirmed', 'attended', 'no_show')
        if paid:
            payment = Payment.objects.create(
                booking=booking, user=user, amount=booking.total_amount, payment_method=method or 'bkash',
                payment_gateway=method or 'bkash', transaction_id=f'TXN{event.pk:03d}{booking.pk:05d}',
                billing_name=name, billing_email=user.email, billing_phone=user.profile.phone,
                billing_address=user.profile.address,
            )
            payment.mark_as_paid()
        elif status in ('confirmed', 'attended', 'no_show'):
            EventBooking.objects.filter(pk=booking.pk).update(status='confirmed', payment_status='completed' if event.is_free else 'pending')
        if status in ('attended', 'no_show', 'cancelled'):
            EventBooking.objects.filter(pk=booking.pk).update(status=status)
        return booking

    def make_event_bookings(self):
        book = self.book
        # Jazz night: three tiers, every state
        book('jazz', 'ayesha', quantity=2, tier='VIP', method='bkash')
        book('jazz', 'mim', tier='General', method='nagad')
        book('jazz', 'farhan', quantity=2, tier='Early Bird', method='bkash')
        book('jazz', 'sabbir', quantity=3, tier='General', status='pending', pay=False)
        book('jazz', 'tasnia', tier='General', status='cancelled', pay=False)
        # Summit
        book('summit', 'kamal', tier='Student', method='nagad')
        book('summit', 'nabila', tier='General', method='bkash')
        book('summit', 'rubel', tier='General', status='pending', pay=False)
        # Free events
        for name in ('ayesha', 'mim', 'sabbir', 'farhan'):
            book('openmic', name)
        for name in ('ayesha', 'kamal'):
            book('run', name)
        book('art', 'sadia')
        for name in ('ayesha', 'farhan'):
            book('talk', name)
        # Almost full workshop (7 of 8) and a sold-out festival (6 of 6)
        for index, name in enumerate(('mim', 'sabbir', 'tasnia', 'kamal', 'farhan', 'nabila', 'rubel')):
            book('photo', name, method='nagad' if index % 2 else 'bkash')
        for name in ('mim', 'sabbir', 'tasnia', 'kamal', 'farhan', 'nabila'):
            book('rockfest', name, method='bkash')
        # On now
        book('bookfair', 'ayesha', quantity=2, method='nagad')
        book('bookfair', 'mim', method='bkash')
        # Finished: attended, a no-show, and one that stayed confirmed
        book('eid', 'ayesha', status='attended', method='bkash')
        book('eid', 'mim', status='attended', method='nagad')
        book('eid', 'sabbir', status='attended', method='bkash')
        book('eid', 'farhan')
        book('eid', 'tasnia', status='no_show', method='bkash')
        for name in ('kamal', 'nabila', 'rubel'):
            book('leadership', name, status='attended', method='bkash')
        for name in ('ayesha', 'sadia'):
            book('expo', name, status='attended')
        # A failed payment: the booking is cancelled and the payment keeps the reason
        booking = book('summit', 'sadia', tier='General', status='pending', pay=False)
        failed = Payment.objects.create(
            booking=booking, user=booking.user, amount=booking.total_amount, payment_method='nagad', payment_gateway='nagad',
            billing_name=booking.user.get_full_name(), billing_email=booking.user.email,
        )
        failed.mark_as_failed('Wallet balance too low')
        self.done(f'{EventBooking.objects.count()} event bookings, {Payment.objects.count()} payments')

    # ---- venue bookings ------------------------------------------------------------------------------------

    def hire(self, venue_key, username, title, days, hours, status, payment='pending', note='', hour=18):
        venue = self.venues[venue_key]
        user = self.users[username]
        start = self.at(days=days).replace(hour=hour)
        booking = VenueBooking.objects.create(
            venue=venue, user=user, event_title=title, event_description=f'{title}, hosted by {user.get_full_name()}.',
            start_date=start, end_date=start + timedelta(hours=hours), total_amount=venue.price_per_hour * hours,
            contact_email=user.email, contact_phone=user.profile.phone, special_requirements=note,
        )
        if status != 'pending' or payment != 'pending':
            booking.status = status
            booking.payment_status = payment
            booking.save()
        return booking

    def make_venue_bookings(self):
        hire = self.hire
        # Waiting for a manager's decision, approved, rejected, cancelled, paid and not yet paid
        hire('ballroom', 'ayesha', 'Engagement party', 25, 6, 'pending', hour=19, note='Need a small stage and flower arches.')
        hire('lakeview', 'sadia', 'Bridal shower', 33, 4, 'pending', hour=16)
        hire('auditorium', 'nusrat_org', 'Annual corporate gala', 30, 5, 'pending', hour=19, note='Two rehearsals the day before.')
        hire('rooftop', 'ayesha', 'Birthday dinner', 14, 4, 'confirmed', 'paid', hour=20)
        hire('lakeview', 'rafiq_events', 'Artist meet and greet', 18, 3, 'confirmed', 'pending', hour=17)
        hire('arena', 'mim', 'Photography festival', 40, 8, 'rejected', hour=15, note='Outdoor dates clash with a local fair.')
        hire('sports', 'sabbir', 'Office cricket day', 10, 6, 'cancelled', hour=8)
        # Finished bookings that people can now review
        past = {
            'lakeview': ('ayesha', 'Book club annual meet', -20, 5, 16),
            'ballroom': ('kamal', 'Family wedding reception', -35, 6, 19),
            'rooftop': ('farhan', 'Acoustic launch party', -12, 4, 20),
            'auditorium': ('nabila', 'Design school showcase', -45, 5, 10),
            'arena': ('rafiq_events', 'Spring open-air concert', -60, 8, 17),
        }
        for venue_key, (username, title, days, hours, hour) in past.items():
            hire(venue_key, username, title, days, hours, 'completed', 'paid', hour=hour)
        # Left unreviewed on purpose, so the "Write a review" button can be tried
        hire('sports', 'ayesha', 'Friends football match', -8, 3, 'completed', 'paid', hour=7)
        self.done(f'{VenueBooking.objects.count()} venue bookings')

    # ---- reviews -------------------------------------------------------------------------------------------

    def make_reviews(self):
        for username, rating, title, body, featured in content.SITE_REVIEWS:
            Review.objects.create(user=self.users[username], rating=rating, title=title, content=body, is_featured=featured)
        for event_key, rows in content.EVENT_REVIEWS.items():
            event = self.events[event_key]
            for username, overall, organisation, venue, value, title, body in rows:
                booking = EventBooking.objects.get(event=event, user=self.users[username])
                EventReview.objects.create(
                    event=event, user=self.users[username], booking=booking, rating=overall, organization_rating=organisation,
                    venue_rating=venue, value_rating=value, title=title, comment=body,
                )
        for venue_key, username, _title, ratings, title, body in content.VENUE_REVIEWS:
            overall, ambience, service, clean, value = ratings
            VenueReview.objects.create(
                venue=self.venues[venue_key], user=self.users[username], rating=overall, ambience_rating=ambience,
                service_rating=service, cleanliness_rating=clean, value_rating=value, title=title, comment=body,
            )
        self.done(f'{Review.objects.count()} site, {EventReview.objects.count()} event and {VenueReview.objects.count()} venue reviews')

    # ---- comments, replies and likes on events and venues --------------------------------------------------

    def make_comments(self):
        u = self.users
        threads = [
            (EventComment, 'event', self.events['jazz'], EventCommentLike, [
                ('ayesha', 'Is there parking at the ballroom?', 'rafiq_events', 'Yes, 200 spaces on site, free for ticket holders.', ['mim', 'sabbir']),
                ('mim', 'Can I swap my General ticket for VIP later?', 'rafiq_events', 'Write to us before the 10th and we will upgrade you for the difference.', ['ayesha']),
            ]),
            (EventComment, 'event', self.events['summit'], EventCommentLike, [
                ('kamal', 'Will the talks be recorded?', 'nusrat_org', 'Yes. Recordings go to every ticket holder within a week.', ['nabila']),
            ]),
            (EventComment, 'event', self.events['photo'], EventCommentLike, [
                ('farhan', 'Is a phone camera fine?', 'nusrat_org', 'Absolutely. Bring whatever you shoot with.', ['mim', 'kamal', 'nabila']),
            ]),
            (VenueComment, 'venue', self.venues['ballroom'], VenueCommentLike, [
                ('sadia', 'Is outside catering allowed?', 'tanvir_venues', 'Outside caterers are welcome with a small kitchen fee.', ['ayesha']),
            ]),
            (VenueComment, 'venue', self.venues['rooftop'], VenueCommentLike, [
                ('ayesha', 'Does the rooftop have cover if it rains?', 'shirin_hall', 'Half of it does, and we can close the glass side.', ['farhan', 'mim']),
            ]),
        ]
        for model, kind, subject, like_model, rows in threads:
            for asker, question, answerer, answer, likers in rows:
                top = model.objects.create(**{kind: subject}, user=u[asker], comment=question)
                reply = model.objects.create(**{kind: subject}, user=u[answerer], parent=top, comment=answer)
                follow = model.objects.create(**{kind: subject}, user=u[asker], parent=reply, comment='Thank you, that helps!')
                for name in likers:
                    like_model.objects.create(comment=top, user=u[name])
                like_model.objects.create(comment=reply, user=u[asker])
                self.backdate(top, created_at=self.at(days=-3))
                self.backdate(reply, created_at=self.at(days=-2))
                self.backdate(follow, created_at=self.at(days=-2, hours=-3))
        photo_comment = EventComment.objects.create(event=self.events['eid'], user=u['ayesha'], comment='Some shots from the evening!')
        photo_comment.image.save('eid-night.jpg', art.photo_file('eid-night.jpg', 'Eid night', 0), save=True)
        self.done(f'{EventComment.objects.count()} event and {VenueComment.objects.count()} venue comments')

    # ---- blog ----------------------------------------------------------------------------------------------

    def make_blog(self):
        u = self.users
        readers = ['ayesha', 'mim', 'sabbir', 'kamal', 'farhan', 'nabila']
        kinds = ['like', 'love', 'haha', 'wow', 'like', 'love']
        for index, (title, author, days_ago, paragraphs, images, has_file) in enumerate(content.BLOG_POSTS):
            post = BlogPost.objects.create(author=u[author], title=title, content='\n\n'.join(paragraphs),
                                           created_at=self.at(days=-days_ago))
            post.image.save(f'blog-{index}.jpg', art.photo_file(f'blog-{index}.jpg', title, index), save=True)
            for shot in range(images):
                gallery = BlogPostImage(post=post, caption='')
                gallery.image.save(f'blog-{index}-{shot}.jpg', art.photo_file(f'blog-{index}-{shot}.jpg', title, index + shot + 1, seed=f'{index}{shot}'), save=True)
            if has_file:
                body = f'{title}\n\n' + '\n\n'.join(paragraphs)
                attachment = BlogPostFile(post=post, file_name=f'notes-{index}.txt', file_size=len(body.encode()))
                attachment.file.save(f'notes-{index}.txt', art.text_file(f'notes-{index}.txt', body), save=True)
            for reader, kind in list(zip(readers, kinds))[: 3 + index]:
                if reader != author:
                    BlogReaction.objects.create(post=post, user=u[reader], reaction_type=kind)
            first = BlogComment.objects.create(post=post, user=u[readers[index % len(readers)]], content='Really useful, thank you for sharing.')
            BlogComment.objects.create(post=post, user=u[author], parent=first, content='Glad it helped! Tell me what you would add.')
            second = BlogComment.objects.create(post=post, user=u[readers[(index + 2) % len(readers)]], content='Posting a photo from last time.')
            comment_photo = BlogCommentImage(comment=second)
            comment_photo.image.save(f'blog-comment-{index}.jpg', art.photo_file(f'blog-comment-{index}.jpg', 'From the crowd', index + 3), save=True)
        self.done(f'{BlogPost.objects.count()} blog posts with photos, files, reactions and comments')

    # ---- friends and chat ----------------------------------------------------------------------------------

    def make_social(self):
        u = self.users
        pairs = [('ayesha', 'mim'), ('ayesha', 'sabbir'), ('ayesha', 'farhan'), ('mim', 'sabbir'), ('rafiq_events', 'ayesha')]
        for first, second in pairs:
            FriendRequest.objects.create(from_user=u[first], to_user=u[second], status='accepted')
            Friendship.objects.create(user1=u[first], user2=u[second])
        FriendRequest.objects.create(from_user=u['tasnia'], to_user=u['ayesha'], status='pending')
        FriendRequest.objects.create(from_user=u['kamal'], to_user=u['ayesha'], status='pending')
        FriendRequest.objects.create(from_user=u['ayesha'], to_user=u['nabila'], status='pending')
        FriendRequest.objects.create(from_user=u['rubel'], to_user=u['ayesha'], status='rejected')

        chats = [
            ('ayesha', 'mim', [
                ('mim', 'Are you going to the jazz night?', True),
                ('ayesha', 'Yes! I got VIP tickets. Want to come along?', True),
                ('mim', 'I already booked a General one. Let us meet at the entrance.', True),
                ('ayesha', 'Perfect. Doors open at 6.', True),
                ('mim', 'Also, are you free Saturday for the photo walk?', False),
                ('mim', 'Bring the 50mm lens if you can.', False),
            ]),
            ('ayesha', 'sabbir', [
                ('sabbir', 'Did you see the Django talk is on Thursday?', True),
                ('ayesha', 'Booked already. Saving you a seat.', True),
                ('sabbir', 'Great. I will bring coffee.', False),
            ]),
            ('rafiq_events', 'ayesha', [
                ('rafiq_events', 'Thanks for the review. Would you volunteer at the next festival?', True),
                ('ayesha', 'Happy to. Send me the dates.', True),
            ]),
            ('mim', 'sabbir', [('mim', 'Match on Sunday?', False)]),
        ]
        minutes = 600
        for first, second, lines in chats:
            for sender, text, read in lines:
                receiver = second if sender == first else first
                message = Message.objects.create(sender=u[sender], receiver=u[receiver], content=text, is_read=read)
                self.backdate(message, created_at=self.now - timedelta(minutes=minutes))
                minutes -= 7
        image_message = Message.objects.create(sender=u['rafiq_events'], receiver=u['ayesha'], content='Here is the stage plan.', is_read=False)
        attachment = MessageFile(message=image_message, original_name='stage-plan.jpg', file_type='image/jpeg')
        content_file = art.photo_file('stage-plan.jpg', 'Stage plan', 2)
        attachment.file_size = content_file.size
        attachment.file.save('stage-plan.jpg', content_file, save=True)
        self.done(f'{Friendship.objects.count()} friendships, {FriendRequest.objects.filter(status="pending").count()} pending requests, {Message.objects.count()} messages')

    # ---- role requests and notifications -------------------------------------------------------------------

    def make_requests_and_notifications(self):
        u = self.users
        admin = u['admin']
        RoleUpgradeRequest.objects.create(
            user=u['tasnia'], requested_role='event_manager', status='pending', company_name='Tasnia Events',
            reason='I have run three college festivals and want to sell tickets properly.',
            experience='Organised festivals of 500 people, managed volunteers and sponsors.',
            portfolio='https://tasnia.example.com', phone='01911000009', address='Mirpur, Dhaka',
        )
        RoleUpgradeRequest.objects.create(
            user=u['kamal'], requested_role='venue_manager', status='pending', company_name='Kamal Catering Hall',
            reason='We own a 200-seat hall and want to rent it out on weekdays.', phone='01911000010', address='Uttara, Dhaka',
        )
        RoleUpgradeRequest.objects.create(
            user=u['nusrat_org'], requested_role='event_manager', status='approved', reviewed_by=admin,
            reason='Corporate events and expos.', company_name='Jahan Events',
        )
        RoleUpgradeRequest.objects.create(
            user=u['sadia'], requested_role='venue_manager', status='rejected', reviewed_by=admin,
            reason='I would like to list a hall.', experience='None yet.',
        )
        samples = [
            ('ayesha', 'Welcome to EventEase', 'Your account is ready. Browse events and book your first ticket.', 'system', True),
            ('ayesha', 'Upcoming Event Reminder', 'Don\'t forget! "Tech Talk: Django at Scale" is happening in 3 days.', 'upcoming_event', False),
            ('ayesha', 'Venue Booking Status Update', 'Your venue booking for "The Rooftop Lounge" has been confirmed.', 'venue_booking_status', False),
            ('rafiq_events', 'New Event Registration', 'Mim Chowdhury has registered for "Dhaka Jazz Night".', 'event_registration', False),
            ('tanvir_venues', 'New Venue Booking Request', 'A new booking request has been received for "Grand Ballroom Gulshan".', 'venue_booking_request', False),
        ]
        for username, title, message, kind, read in samples:
            Notification.create_notification(u[username], title, message, kind, is_read=read)
        self.done(f'{RoleUpgradeRequest.objects.count()} role requests, {Notification.objects.count()} notifications')

    # ---- summary -------------------------------------------------------------------------------------------

    def report(self):
        self.stdout.write(self.style.SUCCESS('\nDemo data is ready. Log in with:'))
        rows = [
            ('admin', content.ADMIN_PASSWORD, 'admin dashboard, comment moderation, role requests'),
            ('rafiq_events', content.PASSWORD, 'organiser: jazz night, rock fest, expo; revenue and bookings'),
            ('nusrat_org', content.PASSWORD, 'organiser: summit, photo workshop, art exhibition'),
            ('tanvir_venues', content.PASSWORD, 'venue manager: ballroom, lakeview, sports; pending requests'),
            ('shirin_hall', content.PASSWORD, 'venue manager: arena, rooftop, auditorium'),
            ('ayesha', content.PASSWORD, 'busy member: bookings, friends, chat, requests, reviews to write'),
            ('mim', content.PASSWORD, 'member with friends and bookings'),
            ('tasnia', content.PASSWORD, 'member with a pending organiser request'),
            ('newbie', content.PASSWORD, 'brand-new member: try booking, paying, and upgrading'),
        ]
        for username, password, note in rows:
            self.stdout.write(f'  {username:<14} {password:<12} {note}')
        self.stdout.write('  (every other member uses password ' + content.PASSWORD + ')')
