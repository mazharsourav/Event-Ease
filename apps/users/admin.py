from django.contrib import admin
from .models import UserProfile, RoleUpgradeRequest

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'created_at')
    list_filter = ('role', 'created_at')
    search_fields = ('user__username', 'user__email', 'user__first_name', 'user__last_name')

@admin.register(RoleUpgradeRequest)
class RoleUpgradeRequestAdmin(admin.ModelAdmin):
    list_display = ('user', 'requested_role', 'status', 'created_at')
    list_filter = ('status', 'requested_role', 'created_at')
    search_fields = ('user__username', 'user__email')
    actions = ['approve_requests', 'reject_requests']
    
    def approve_requests(self, request, queryset):
        for req in queryset:
            req.status = 'approved'
            req.reviewed_by = request.user
            req.save()
            # Update user role
            req.user.profile.role = req.requested_role
            req.user.profile.save()
        self.message_user(request, f'{queryset.count()} requests approved.')
    
    def reject_requests(self, request, queryset):
        for req in queryset:
            req.status = 'rejected'
            req.reviewed_by = request.user
            req.save()
        self.message_user(request, f'{queryset.count()} requests rejected.')
    
    approve_requests.short_description = "Approve selected requests"
    reject_requests.short_description = "Reject selected requests"
