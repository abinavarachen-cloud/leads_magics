from rest_framework import permissions

class IsOwnerOrAdmin(permissions.BasePermission):
    
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions are only allowed to the owner or admin
        if hasattr(obj, 'created_by'):
            return obj.created_by == request.user or request.user.is_staff
        return request.user.is_staff

class IsCampaignOwnerOrAdmin(permissions.BasePermission):
    
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        
        if hasattr(obj, 'campaign'):
            return obj.campaign.created_by == request.user or request.user.is_staff
        return request.user.is_staff