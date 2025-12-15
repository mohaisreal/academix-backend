from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    GradingCategoryViewSet,
    AssignmentViewSet,
    SubmissionViewSet,
    GradeViewSet,
    GradebookViewSet,
    FinalGradeConfigViewSet,
    FinalGradeViewSet,
    CourseMaterialViewSet,
    StudentDashboardView,
    AcademicRecordView,
    GradeTranscriptView,
    ProgressReportView,
    QuizViewSet,
    QuestionViewSet,
    QuestionOptionViewSet,
    QuizAttemptViewSet,
)

app_name = 'grades'

router = DefaultRouter()
router.register(r'categories', GradingCategoryViewSet, basename='grading-category')
router.register(r'assignments', AssignmentViewSet, basename='assignment')
router.register(r'submissions', SubmissionViewSet, basename='submission')
router.register(r'grades', GradeViewSet, basename='grade')
router.register(r'gradebook', GradebookViewSet, basename='gradebook')
router.register(r'final-grade-config', FinalGradeConfigViewSet, basename='final-grade-config')
router.register(r'final-grades', FinalGradeViewSet, basename='final-grade')
router.register(r'materials', CourseMaterialViewSet, basename='course-material')

# Quiz endpoints (Phase 4)
router.register(r'quizzes', QuizViewSet, basename='quiz')
router.register(r'questions', QuestionViewSet, basename='question')
router.register(r'question-options', QuestionOptionViewSet, basename='question-option')
router.register(r'quiz-attempts', QuizAttemptViewSet, basename='quiz-attempt')

urlpatterns = [
    path('student-dashboard/', StudentDashboardView.as_view(), name='student-dashboard'),

    # Academic Record Endpoints (Phase 3)
    path('academic-record/', AcademicRecordView.as_view(), name='academic-record'),
    path('academic-record/<int:student_id>/', AcademicRecordView.as_view(), name='academic-record-detail'),
    path('grade-transcript/', GradeTranscriptView.as_view(), name='grade-transcript'),
    path('grade-transcript/<int:student_id>/', GradeTranscriptView.as_view(), name='grade-transcript-detail'),
    path('progress-report/', ProgressReportView.as_view(), name='progress-report'),
    path('progress-report/<int:student_id>/', ProgressReportView.as_view(), name='progress-report-detail'),

    path('', include(router.urls)),
]
