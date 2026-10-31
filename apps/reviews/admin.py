from django.contrib import admin
from .models import Review

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['user', 'rating', 'title', 'created_at', 'is_featured']
    list_filter = ['rating', 'is_featured', 'created_at']
    search_fields = ['user__username', 'user__first_name', 'user__last_name', 'title', 'content']
    readonly_fields = ['created_at', 'updated_at']
    list_editable = ['is_featured']
    ordering = ['-created_at']
    
    fieldsets = (
        (None, {
            'fields': ('user', 'rating', 'title', 'content')
        }),
        ('Settings', {
            'fields': ('is_featured',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
