from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CareerViewSet, SubjectViewSet, AcademicPeriodViewSet,
    StudyPlanViewSet, ClassroomViewSet,
    StudentAcademicRecordView, AcademicStatisticsView,
    TeacherSubjectStudentsView, SubjectStatisticsView
)

router = DefaultRouter()
router.register(r'careers', CareerViewSet, basename='career')
router.register(r'subjects', SubjectViewSet, basename='subject')
router.register(r'periods', AcademicPeriodViewSet, basename='academic-period')
router.register(r'study-plans', StudyPlanViewSet, basename='study-plan')
router.register(r'classrooms', ClassroomViewSet, basename='classroom')

urlpatterns = [
    path('', include(router.urls)),
    # Academic Reports
    path('reports/academic-record/', StudentAcademicRecordView.as_view(), name='student-academic-record'),
    path('reports/academic-record/<int:student_id>/', StudentAcademicRecordView.as_view(), name='student-academic-record-detail'),
    path('reports/statistics/', AcademicStatisticsView.as_view(), name='academic-statistics'),
    path('reports/subject-statistics/<int:subject_id>/', SubjectStatisticsView.as_view(), name='subject-statistics'),
    path('reports/subject-students/<int:subject_group_id>/', TeacherSubjectStudentsView.as_view(), name='teacher-subject-students'),
]
