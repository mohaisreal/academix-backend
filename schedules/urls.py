"""
URL configuration for schedules app
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Create router and register viewsets
router = DefaultRouter()

# Schedule management endpoints
router.register(r'time-slots', views.TimeSlotViewSet, basename='timeslot')
router.register(r'schedules', views.ScheduleViewSet, basename='schedule')
router.register(r'teacher-assignments', views.TeacherAssignmentViewSet, basename='teacher-assignment')

# Teacher roles and preferences
router.register(r'teacher-roles', views.TeacherRoleViewSet, basename='teacher-role')
router.register(r'teacher-role-assignments', views.TeacherRoleAssignmentViewSet, basename='teacher-role-assignment')
router.register(r'teacher-availability', views.TeacherAvailabilityViewSet, basename='teacher-availability')
router.register(r'teacher-preferences', views.TeacherPreferencesViewSet, basename='teacher-preferences')

# Schedule generation
router.register(r'configurations', views.ScheduleConfigurationViewSet, basename='schedule-configuration')
router.register(r'generations', views.ScheduleGenerationViewSet, basename='schedule-generation')
router.register(r'sessions', views.ScheduleSessionViewSet, basename='schedule-session')
router.register(r'blocked-time-slots', views.BlockedTimeSlotViewSet, basename='blocked-time-slot')

app_name = 'schedules'

urlpatterns = [
    path('', include(router.urls)),
]
