from django.contrib import admin
from .models import (BlogPost, BlogReaction, BlogComment, BlogPostImage, 
                     BlogPostFile, BlogCommentImage, BlogCommentFile)


class BlogPostImageInline(admin.TabularInline):
    model = BlogPostImage
    extra = 1


class BlogPostFileInline(admin.TabularInline):
    model = BlogPostFile
    extra = 1


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = ['title', 'author', 'created_at', 'get_reactions_count', 'get_comments_count']
    list_filter = ['created_at', 'author']
    search_fields = ['title', 'content', 'author__username']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [BlogPostImageInline, BlogPostFileInline]


@admin.register(BlogPostImage)
class BlogPostImageAdmin(admin.ModelAdmin):
    list_display = ['post', 'caption', 'uploaded_at']
    list_filter = ['uploaded_at']
    search_fields = ['post__title', 'caption']


@admin.register(BlogPostFile)
class BlogPostFileAdmin(admin.ModelAdmin):
    list_display = ['post', 'file_name', 'get_file_size_display', 'uploaded_at']
    list_filter = ['uploaded_at']
    search_fields = ['post__title', 'file_name']


@admin.register(BlogReaction)
class BlogReactionAdmin(admin.ModelAdmin):
    list_display = ['user', 'post', 'reaction_type', 'created_at']
    list_filter = ['reaction_type', 'created_at']
    search_fields = ['user__username', 'post__title']


class BlogCommentImageInline(admin.TabularInline):
    model = BlogCommentImage
    extra = 1


class BlogCommentFileInline(admin.TabularInline):
    model = BlogCommentFile
    extra = 1


@admin.register(BlogComment)
class BlogCommentAdmin(admin.ModelAdmin):
    list_display = ['user', 'post', 'content_preview', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__username', 'post__title', 'content']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [BlogCommentImageInline, BlogCommentFileInline]

    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Content Preview'


@admin.register(BlogCommentImage)
class BlogCommentImageAdmin(admin.ModelAdmin):
    list_display = ['comment', 'uploaded_at']
    list_filter = ['uploaded_at']


@admin.register(BlogCommentFile)
class BlogCommentFileAdmin(admin.ModelAdmin):
    list_display = ['comment', 'file_name', 'get_file_size_display', 'uploaded_at']
    list_filter = ['uploaded_at']
    search_fields = ['file_name']
