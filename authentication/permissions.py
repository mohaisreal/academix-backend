from rest_framework import permissions


class IsAdminUser(permissions.BasePermission):
    """
    Custom permission that only allows access to users with admin role
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == 'admin'


class IsTeacherUser(permissions.BasePermission):
    """
    Custom permission that only allows access to users with teacher role
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == 'teacher'


class IsStudentUser(permissions.BasePermission):
    """
    Custom permission that only allows access to users with student role
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == 'student'


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Custom permission that allows access to the object owner or an admin
    """
    def has_object_permission(self, request, view, obj):
        # Admins have full access
        if request.user.role == 'admin':
            return True

        # User must be the object owner
        # Assumes the object has a 'user' attribute
        if hasattr(obj, 'user'):
            return obj.user == request.user

        # If the object is the user itself
        return obj == request.user


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Custom permission that allows read-only access to everyone (public),
    but write access only to admins
    """
    def has_permission(self, request, view):
        # Allow read access to everyone (including anonymous users)
        if request.method in permissions.SAFE_METHODS:
            return True

        # Allow write access only to admins
        return request.user and request.user.is_authenticated and request.user.role == 'admin'


class IsTeacherOrAdmin(permissions.BasePermission):
    """
    Custom permission that allows access to teachers and admins
    """
    def has_permission(self, request, view):
        return (request.user and request.user.is_authenticated and
                request.user.role in ['teacher', 'admin'])
