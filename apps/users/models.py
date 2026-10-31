from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('basic_user', 'Basic User'),
        ('event_manager', 'Event Manager'),
        ('venue_manager', 'Venue Manager'),
        ('admin', 'Admin'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='basic_user')
    phone = models.CharField(max_length=15, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    bio = models.TextField(max_length=500, blank=True, null=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.role}"

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()

class RoleUpgradeRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    requested_role = models.CharField(max_length=20, choices=UserProfile.ROLE_CHOICES)
    reason = models.TextField(help_text="Why do you want this role?")
    company_name = models.CharField(max_length=100, blank=True, null=True, help_text="Company/Organization name")
    experience = models.TextField(blank=True, null=True, help_text="Relevant experience")
    portfolio = models.URLField(blank=True, null=True, help_text="Portfolio or website URL")
    phone = models.CharField(max_length=15, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_requests')

    def __str__(self):
        return f"{self.user.username} - {self.requested_role} ({self.status})"


class FriendRequest(models.Model):
    """Model for handling friend requests between users"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
    ]
    
    from_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_friend_requests')
    to_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_friend_requests')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('from_user', 'to_user')
        
    def __str__(self):
        return f"{self.from_user.username} -> {self.to_user.username} ({self.status})"


class Friendship(models.Model):
    """Model for confirmed friendships between users"""
    user1 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='friendships_user1')
    user2 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='friendships_user2')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user1', 'user2')
        
    def __str__(self):
        return f"{self.user1.username} & {self.user2.username}"
    
    @classmethod
    def are_friends(cls, user1, user2):
        """Check if two users are friends"""
        return cls.objects.filter(
            models.Q(user1=user1, user2=user2) | 
            models.Q(user1=user2, user2=user1)
        ).exists()
    
    @classmethod
    def get_friends(cls, user):
        """Get all friends for a user"""
        friendships = cls.objects.filter(
            models.Q(user1=user) | models.Q(user2=user)
        ).select_related('user1', 'user2')
        
        friends = []
        for friendship in friendships:
            if friendship.user1 == user:
                friends.append(friendship.user2)
            else:
                friends.append(friendship.user1)
        return friends


class Message(models.Model):
    """Model for messages between friends"""
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
    # allow blank content for messages that only contain files
    content = models.TextField(blank=True, null=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['created_at']
        
    def __str__(self):
        return f"{self.sender.username} -> {self.receiver.username}: {self.content[:50]}..."
    
    @classmethod
    def get_conversation(cls, user1, user2):
        """Get conversation between two users"""
        return cls.objects.filter(
            models.Q(sender=user1, receiver=user2) | 
            models.Q(sender=user2, receiver=user1)
        ).order_by('created_at')
    
    @classmethod
    def get_recent_conversations(cls, user):
        """Get recent conversations for a user"""
        from django.db.models import Q, Max
        
        # Get latest message for each conversation
        conversations = {}
        messages = cls.objects.filter(
            Q(sender=user) | Q(receiver=user)
        ).select_related('sender', 'receiver').order_by('-created_at')
        
        for message in messages:
            other_user = message.receiver if message.sender == user else message.sender
            if other_user.id not in conversations:
                conversations[other_user.id] = {
                    'user': other_user,
                    'last_message': message,
                    'unread_count': 0
                }
        
        # Count unread messages for each conversation
        for conv in conversations.values():
            conv['unread_count'] = cls.objects.filter(
                sender=conv['user'], receiver=user, is_read=False
            ).count()
        
        return list(conversations.values())


class MessageFile(models.Model):
    """Files/attachments uploaded for messages"""
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='files')
    file = models.FileField(upload_to='message_files/%Y/%m/%d/')
    original_name = models.CharField(max_length=255, blank=True)
    file_size = models.BigIntegerField(default=0)
    file_type = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.original_name or self.file.name} ({self.file_size} bytes)"

    @property
    def url(self):
        try:
            return self.file.url
        except Exception:
            return ''

    @property
    def is_image(self):
        return self.file_type.startswith('image') if self.file_type else False
