#!/usr/bin/env python
"""
Demo script to showcase the social features
Creates sample data for testing
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from apps.users.models import FriendRequest, Friendship, Message
import random

class Command(BaseCommand):
    help = 'Create demo data for social features'

    def handle(self, *args, **options):
        self.stdout.write("🎭 Creating Social Features Demo Data...")
        
        # Create demo users
        demo_users = [
            ('alice_social', 'Alice', 'Johnson', 'alice@demo.com'),
            ('bob_social', 'Bob', 'Smith', 'bob@demo.com'),
            ('charlie_social', 'Charlie', 'Brown', 'charlie@demo.com'),
            ('diana_social', 'Diana', 'Wilson', 'diana@demo.com'),
            ('eve_social', 'Eve', 'Davis', 'eve@demo.com'),
        ]
        
        users = []
        for username, first_name, last_name, email in demo_users:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'first_name': first_name,
                    'last_name': last_name,
                    'email': email
                }
            )
            if created:
                user.set_password('demo123')
                user.save()
                self.stdout.write(f"✅ Created demo user: {user.username}")
            users.append(user)
        
        # Clear existing social data for clean demo
        FriendRequest.objects.filter(from_user__in=users).delete()
        Friendship.objects.filter(user1__in=users).delete()
        Message.objects.filter(sender__in=users).delete()
        
        # Create friendships
        alice, bob, charlie, diana, eve = users
        
        # Alice is friends with Bob and Charlie
        for friend in [bob, charlie]:
            if not Friendship.are_friends(alice, friend):
                Friendship.objects.create(user1=alice, user2=friend)
                Friendship.objects.create(user1=friend, user2=alice)
                self.stdout.write(f"✅ Created friendship: {alice.username} ↔ {friend.username}")
        
        # Bob is friends with Diana
        if not Friendship.are_friends(bob, diana):
            Friendship.objects.create(user1=bob, user2=diana)
            Friendship.objects.create(user1=diana, user2=bob)
            self.stdout.write(f"✅ Created friendship: {bob.username} ↔ {diana.username}")
        
        # Create pending friend requests
        # Eve sends request to Alice
        FriendRequest.objects.create(from_user=eve, to_user=alice)
        self.stdout.write(f"✅ Created friend request: {eve.username} → {alice.username}")
        
        # Diana sends request to Charlie
        FriendRequest.objects.create(from_user=diana, to_user=charlie)
        self.stdout.write(f"✅ Created friend request: {diana.username} → {charlie.username}")
        
        # Create sample messages
        messages_data = [
            (alice, bob, "Hey Bob! How's the event planning going? 🎉"),
            (bob, alice, "Hi Alice! It's going great, thanks for asking! The venue is all set."),
            (alice, bob, "Awesome! Can't wait to see the final setup. Need any help with anything?"),
            (charlie, alice, "Alice, thanks for connecting me with that amazing photographer!"),
            (alice, charlie, "You're welcome! Sarah does incredible work. I'm glad it worked out! 📸"),
            (charlie, alice, "The photos from last weekend's event turned out perfect!"),
        ]
        
        for sender, receiver, content in messages_data:
            Message.objects.create(sender=sender, receiver=receiver, content=content)
            self.stdout.write(f"✅ Created message: {sender.username} → {receiver.username}")
        
        # Create some unread messages for demo
        unread_messages = [
            (bob, diana, "Diana! Did you see the new venue options I sent over?"),
            (diana, bob, "Yes! The waterfront location looks amazing! 🌊"),
            (eve, alice, "Hi Alice! I saw your profile in the search. Would love to connect!"),
        ]
        
        for sender, receiver, content in unread_messages:
            Message.objects.create(sender=sender, receiver=receiver, content=content, is_read=False)
            self.stdout.write(f"✅ Created unread message: {sender.username} → {receiver.username}")
        
        self.stdout.write("\n📊 Demo Data Summary:")
        self.stdout.write(f"👥 Users created: {len(users)}")
        self.stdout.write(f"🤝 Friendships: {Friendship.objects.filter(user1__in=users).count() // 2}")
        self.stdout.write(f"📤 Friend requests: {FriendRequest.objects.filter(from_user__in=users).count()}")
        self.stdout.write(f"💬 Messages: {Message.objects.filter(sender__in=users).count()}")
        
        self.stdout.write("\n🎯 Demo Testing Guide:")
        self.stdout.write("1. Login as 'alice_social' (password: demo123)")
        self.stdout.write("   - Has friends: Bob, Charlie")
        self.stdout.write("   - Has pending request from: Eve")
        self.stdout.write("   - Has messages with: Bob, Charlie")
        self.stdout.write("   - Search for 'diana_social' to send friend request")
        
        self.stdout.write("\n2. Login as 'bob_social' (password: demo123)")
        self.stdout.write("   - Has friends: Alice, Diana")
        self.stdout.write("   - Has messages with: Alice, Diana")
        self.stdout.write("   - Has unread messages from Diana")
        
        self.stdout.write("\n3. Login as 'eve_social' (password: demo123)")
        self.stdout.write("   - Has sent friend request to Alice")
        self.stdout.write("   - Can search for other users to connect")
        
        self.stdout.write("\n🚀 Ready for demo! Start the server and test the social features!")
        self.stdout.write("✨ The notification badges should show real counts!")
        self.stdout.write("🔍 Use the search feature to find and connect with users!")
        self.stdout.write("💬 Test the messaging system between friends!")