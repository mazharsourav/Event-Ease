from django import forms
from .models import BlogPost, BlogComment


class BlogPostForm(forms.ModelForm):
    class Meta:
        model = BlogPost
        fields = ['title', 'content', 'image']
        labels = {
            'title': 'Title',
            'content': 'Your post',
            'image': 'Cover photo',
        }
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'A short, clear title', 'maxlength': 255}),
            'content': forms.Textarea(attrs={'placeholder': 'Write your post here…', 'rows': 10}),
            'image': forms.FileInput(attrs={'accept': 'image/*'}),
        }


class BlogCommentForm(forms.ModelForm):
    class Meta:
        model = BlogComment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={'placeholder': 'Write your comment…', 'rows': 3}),
        }
