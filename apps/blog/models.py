from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class BlogPost(models.Model):
    """Blog post model"""
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blog_posts')
    title = models.CharField(max_length=255)
    content = models.TextField()
    image = models.ImageField(upload_to='blog_images/', null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def get_reactions_count(self):
        """Get total reactions count"""
        return self.reactions.count()

    def get_comments_count(self):
        """Get total comments count"""
        return self.comments.count()


class BlogPostImage(models.Model):
    """Multiple images for blog posts"""
    post = models.ForeignKey(BlogPost, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='blog_images/')
    caption = models.CharField(max_length=255, blank=True)
    uploaded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['uploaded_at']

    def __str__(self):
        return f"Image for {self.post.title}"


class BlogPostFile(models.Model):
    """Multiple files for blog posts"""
    post = models.ForeignKey(BlogPost, on_delete=models.CASCADE, related_name='files')
    file = models.FileField(upload_to='blog_files/')
    file_name = models.CharField(max_length=255)
    file_size = models.IntegerField(default=0)
    uploaded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['uploaded_at']

    def __str__(self):
        return f"{self.file_name} for {self.post.title}"

    def get_file_size_display(self):
        """Return human-readable file size"""
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"


class BlogReaction(models.Model):
    """Reactions to blog posts"""
    REACTION_CHOICES = [
        ('like', '👍 Like'),
        ('love', '❤️ Love'),
        ('haha', '😂 Haha'),
        ('wow', '😮 Wow'),
        ('sad', '😢 Sad'),
        ('angry', '😠 Angry'),
    ]
    
    post = models.ForeignKey(BlogPost, on_delete=models.CASCADE, related_name='reactions')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blog_reactions')
    reaction_type = models.CharField(max_length=10, choices=REACTION_CHOICES, default='like')
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ['post', 'user']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.reaction_type} on {self.post.title}"


class BlogComment(models.Model):
    """Comments on blog posts"""
    post = models.ForeignKey(BlogPost, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blog_comments')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, related_name='replies', null=True, blank=True)
    content = models.TextField()
    image = models.ImageField(upload_to='blog_comment_images/', null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Comment by {self.user.username} on {self.post.title}"
    
    def get_replies_count(self):
        """Get total replies count"""
        return self.replies.count()
    
    def is_reply(self):
        """Check if this is a reply to another comment"""
        return self.parent is not None


class BlogCommentImage(models.Model):
    """Multiple images for blog comments"""
    comment = models.ForeignKey(BlogComment, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='blog_comment_images/')
    uploaded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['uploaded_at']

    def __str__(self):
        return f"Image for comment by {self.comment.user.username}"


class BlogCommentFile(models.Model):
    """Multiple files for blog comments"""
    comment = models.ForeignKey(BlogComment, on_delete=models.CASCADE, related_name='files')
    file = models.FileField(upload_to='blog_comment_files/')
    file_name = models.CharField(max_length=255)
    file_size = models.IntegerField(default=0)
    uploaded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['uploaded_at']

    def __str__(self):
        return f"{self.file_name} for comment"

    def get_file_size_display(self):
        """Return human-readable file size"""
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
