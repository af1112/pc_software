from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsHRMSManagerOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True

        if request.method in SAFE_METHODS:
            return True

        profile = getattr(request.user, 'profile', None)
        role = getattr(profile, 'role', None)
        return role in {'admin', 'supervisor'}


class IsHRMSManager(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        profile = getattr(request.user, 'profile', None)
        role = getattr(profile, 'role', None)
        return role in {'admin', 'supervisor'}


class IsEmployeeSelfService(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)


class IsExecutiveOrHRManager(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        profile = getattr(request.user, 'profile', None)
        role = getattr(profile, 'role', None)
        return role in {'admin', 'supervisor', 'executive'}
