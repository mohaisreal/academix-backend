from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    FormTemplateViewSet,
    FormPhaseViewSet,
    FormFieldViewSet,
    FormSubmissionViewSet,
    FileUploadView,
    CreatePaymentIntent,
    StripeWebhookView,
)
from .academic_validation import (
    ValidatePrerequisitesView,
    CheckScheduleConflictsView,
    CheckCourseCapacityView,
    GetAvailableCoursesView,
    CalculateTotalCreditsView,
)

router = DefaultRouter()
router.register(r'templates', FormTemplateViewSet, basename='form-template')
router.register(r'phases', FormPhaseViewSet, basename='form-phase')
router.register(r'fields', FormFieldViewSet, basename='form-field')
router.register(r'submissions', FormSubmissionViewSet, basename='form-submission')

urlpatterns = [
    path('', include(router.urls)),
    path('upload/', FileUploadView.as_view(), name='file-upload'),
    path('payment/create/', CreatePaymentIntent.as_view(), name='create-payment'),
    path('payment/webhook/', StripeWebhookView.as_view(), name='stripe-webhook'),

    # Academic validation endpoints for course selector
    path('validate/prerequisites/', ValidatePrerequisitesView.as_view(), name='validate-prerequisites'),
    path('validate/schedule-conflicts/', CheckScheduleConflictsView.as_view(), name='check-schedule-conflicts'),
    path('validate/capacity/', CheckCourseCapacityView.as_view(), name='check-capacity'),
    path('validate/available-courses/', GetAvailableCoursesView.as_view(), name='available-courses'),
    path('validate/total-credits/', CalculateTotalCreditsView.as_view(), name='total-credits'),
]
