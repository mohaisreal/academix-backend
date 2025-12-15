from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CareerEnrollmentViewSet, SubjectGroupViewSet, SubjectEnrollmentViewSet,
    EnrollmentProcessView, BulkEnrollmentView
)

router = DefaultRouter()
router.register(r'career-enrollments', CareerEnrollmentViewSet, basename='career-enrollment')
router.register(r'subject-groups', SubjectGroupViewSet, basename='subject-group')
router.register(r'subject-enrollments', SubjectEnrollmentViewSet, basename='subject-enrollment')

urlpatterns = [
    path('', include(router.urls)),
    path('enrollment-process/', EnrollmentProcessView.as_view(), name='enrollment-process'),
    path('bulk-enrollment/', BulkEnrollmentView.as_view(), name='bulk-enrollment'),
]