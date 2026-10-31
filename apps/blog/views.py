from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_POST
from .models import (BlogPost, BlogReaction, BlogComment, BlogPostImage, 
                     BlogPostFile, BlogCommentImage, BlogCommentFile)
from .forms import BlogPostForm, BlogCommentForm


POSTS_PER_PAGE = 12

# The reactions offered on a post's page (the model also allows 'sad' and 'angry')
REACTION_CHOICES = [('like', 'Like'), ('love', 'Love'), ('haha', 'Haha'), ('wow', 'Wow')]


def blog_list(request):
    """Display all blog posts, newest first"""
    posts = BlogPost.objects.select_related('author', 'author__profile').prefetch_related(
        'reactions', 'comments', 'images', 'files'
    )
    page_obj = Paginator(posts, POSTS_PER_PAGE).get_page(request.GET.get('page'))

    # One query for the signed-in user's reactions on this page
    user_reactions = {}
    if request.user.is_authenticated:
        user_reactions = dict(
            BlogReaction.objects.filter(user=request.user, post__in=page_obj.object_list)
            .values_list('post_id', 'reaction_type')
        )

    context = {
        'page_obj': page_obj,
        'user_reactions': user_reactions,
    }
    return render(request, 'blog/blog_list.html', context)


@login_required
def blog_create(request):
    """Create a new blog post"""
    if request.method == 'POST':
        form = BlogPostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.save()
            
            # Handle multiple images
            images = request.FILES.getlist('images')
            for image in images:
                BlogPostImage.objects.create(post=post, image=image)
            
            # Handle multiple files
            files = request.FILES.getlist('files')
            for file in files:
                BlogPostFile.objects.create(
                    post=post,
                    file=file,
                    file_name=file.name,
                    file_size=file.size
                )
            
            messages.success(request, 'Blog post created successfully!')
            return redirect('blog:blog_list')
    else:
        form = BlogPostForm()
    
    return render(request, 'blog/blog_form.html', {'form': form})


def blog_detail(request, pk):
    """Display a single blog post with comments. Anyone can read; commenting needs an account."""
    post = get_object_or_404(BlogPost.objects.select_related('author', 'author__profile'), pk=pk)
    comments = post.comments.filter(parent__isnull=True).select_related('user', 'user__profile').prefetch_related(
        'images', 'files', 'replies'
    )
    
    # Get user's reaction
    user_reaction = None
    if request.user.is_authenticated:
        reaction = BlogReaction.objects.filter(post=post, user=request.user).first()
        if reaction:
            user_reaction = reaction.reaction_type
    
    # Handle comment submission
    if request.method == 'POST':
        if not request.user.is_authenticated:
            return redirect(f"{reverse('users:login')}?next={request.path}")
        comment_form = BlogCommentForm(request.POST, request.FILES)
        if comment_form.is_valid():
            comment = comment_form.save(commit=False)
            comment.post = post
            comment.user = request.user
            
            # Check if this is a reply to another comment
            parent_id = request.POST.get('parent_id')
            if parent_id:
                try:
                    parent_comment = BlogComment.objects.get(id=parent_id, post=post)
                    comment.parent = parent_comment
                except BlogComment.DoesNotExist:
                    pass
            
            comment.save()
            
            # Handle multiple images for comments
            images = request.FILES.getlist('comment_images')
            for image in images:
                BlogCommentImage.objects.create(comment=comment, image=image)
            
            # Handle multiple files for comments
            files = request.FILES.getlist('comment_files')
            for file in files:
                BlogCommentFile.objects.create(
                    comment=comment,
                    file=file,
                    file_name=file.name,
                    file_size=file.size
                )
            
            if parent_id:
                messages.success(request, 'Reply added successfully!')
            else:
                messages.success(request, 'Comment added successfully!')
            return redirect('blog:blog_detail', pk=pk)
    else:
        comment_form = BlogCommentForm()
    
    context = {
        'post': post,
        'comments': comments,
        'comment_form': comment_form,
        'user_reaction': user_reaction,
        'reaction_choices': REACTION_CHOICES,
        'was_edited': (post.updated_at - post.created_at).total_seconds() > 60,
    }
    return render(request, 'blog/blog_detail.html', context)


@login_required
@require_POST
def blog_react(request, pk):
    """Add or update a reaction to a blog post"""
    post = get_object_or_404(BlogPost, pk=pk)
    reaction_type = request.POST.get('reaction_type', 'like')
    if reaction_type not in dict(BlogReaction.REACTION_CHOICES):
        return JsonResponse({'status': 'error', 'message': 'Unknown reaction'}, status=400)
    
    # Get or create reaction
    reaction, created = BlogReaction.objects.get_or_create(
        post=post,
        user=request.user,
        defaults={'reaction_type': reaction_type}
    )
    
    if not created:
        # Update existing reaction
        if reaction.reaction_type == reaction_type:
            # Remove reaction if same type clicked again
            reaction.delete()
            return JsonResponse({
                'status': 'removed',
                'reactions_count': post.get_reactions_count()
            })
        else:
            # Update to new reaction type
            reaction.reaction_type = reaction_type
            reaction.save()
    
    return JsonResponse({
        'status': 'success',
        'reaction_type': reaction_type,
        'reactions_count': post.get_reactions_count()
    })


@login_required
@require_POST
def blog_comment_delete(request, pk):
    """Delete a comment (its author or staff). Answers JSON for comments.js."""
    comment = get_object_or_404(BlogComment, pk=pk)

    if comment.user != request.user and not request.user.is_staff:
        return JsonResponse({'success': False, 'status': 'error', 'error': 'You can only delete your own comments.'}, status=403)

    comment.delete()
    return JsonResponse({'success': True, 'status': 'success'})


@login_required
def blog_edit(request, pk):
    """Edit a blog post"""
    post = get_object_or_404(BlogPost, pk=pk)
    
    # Only allow author to edit
    if post.author != request.user:
        messages.error(request, 'You can only edit your own posts!')
        return redirect('blog:blog_detail', pk=pk)
    
    if request.method == 'POST':
        form = BlogPostForm(request.POST, request.FILES, instance=post)
        if form.is_valid():
            form.save()
            
            # Handle multiple images
            images = request.FILES.getlist('images')
            for image in images:
                BlogPostImage.objects.create(post=post, image=image)
            
            # Handle multiple files
            files = request.FILES.getlist('files')
            for file in files:
                BlogPostFile.objects.create(
                    post=post,
                    file=file,
                    file_name=file.name,
                    file_size=file.size
                )
            
            messages.success(request, 'Blog post updated successfully!')
            return redirect('blog:blog_detail', pk=pk)
    else:
        form = BlogPostForm(instance=post)
    
    return render(request, 'blog/blog_form.html', {'form': form, 'post': post})


@login_required
@require_POST
def blog_delete(request, pk):
    """Delete a blog post"""
    post = get_object_or_404(BlogPost, pk=pk)
    
    # Only allow author to delete
    if post.author != request.user:
        messages.error(request, 'You can only delete your own posts!')
        return redirect('blog:blog_detail', pk=pk)
    
    post.delete()
    messages.success(request, 'Blog post deleted successfully!')
    return redirect('blog:blog_list')
