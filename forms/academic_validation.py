"""
Academic validation views for course selection in forms
These endpoints are used by the course_selector field type
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.shortcuts import get_object_or_404

from enrollment.models import SubjectGroup, SubjectEnrollment, CareerEnrollment
from academic.models import Subject, StudyPlanSubject, AcademicPeriod
from users.models import Student
from grades.models import FinalGrade


class ValidatePrerequisitesView(APIView):
    """
    Validate if a student meets prerequisites for a subject
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        """
        POST /api/forms/validate/prerequisites/
        Body: {
            "student_id": 123,
            "subject_id": 456,
            "career_enrollment_id": 789
        }
        """
        student_id = request.data.get('student_id')
        subject_id = request.data.get('subject_id')
        career_enrollment_id = request.data.get('career_enrollment_id')

        if not all([student_id, subject_id, career_enrollment_id]):
            return Response(
                {'error': 'student_id, subject_id, and career_enrollment_id are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            student = Student.objects.get(id=student_id)
            subject = Subject.objects.get(id=subject_id)
            career_enrollment = CareerEnrollment.objects.get(id=career_enrollment_id)
        except (Student.DoesNotExist, Subject.DoesNotExist, CareerEnrollment.DoesNotExist):
            return Response(
                {'error': 'Invalid student, subject, or career enrollment ID.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Get prerequisites for this subject in the student's study plan
        try:
            study_plan_subject = StudyPlanSubject.objects.get(
                study_plan=career_enrollment.study_plan,
                subject=subject
            )
        except StudyPlanSubject.DoesNotExist:
            return Response({
                'valid': False,
                'error': 'Subject not found in study plan.'
            })

        # Get all prerequisites
        prerequisites = study_plan_subject.prerequisites.all()

        if not prerequisites.exists():
            return Response({
                'valid': True,
                'message': 'No prerequisites required.',
                'missing_prerequisites': []
            })

        # Check which prerequisites are missing
        missing_prerequisites = []

        for prerequisite in prerequisites:
            # Check if student has passed this prerequisite
            passed = FinalGrade.objects.filter(
                subject_enrollment__student=student,
                subject_enrollment__subject_group__subject=prerequisite,
                status='passed',
                is_published=True
            ).exists()

            if not passed:
                missing_prerequisites.append({
                    'id': prerequisite.id,
                    'code': prerequisite.code,
                    'name': prerequisite.name
                })

        if missing_prerequisites:
            return Response({
                'valid': False,
                'message': f'Missing {len(missing_prerequisites)} prerequisite(s).',
                'missing_prerequisites': missing_prerequisites
            })

        return Response({
            'valid': True,
            'message': 'All prerequisites met.',
            'missing_prerequisites': []
        })


class CheckScheduleConflictsView(APIView):
    """
    Check for schedule conflicts when selecting courses
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        """
        POST /api/forms/validate/schedule-conflicts/
        Body: {
            "student_id": 123,
            "subject_group_ids": [1, 2, 3],
            "academic_period_id": 456
        }
        """
        student_id = request.data.get('student_id')
        subject_group_ids = request.data.get('subject_group_ids', [])
        academic_period_id = request.data.get('academic_period_id')

        if not all([student_id, subject_group_ids, academic_period_id]):
            return Response(
                {'error': 'student_id, subject_group_ids, and academic_period_id are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            student = Student.objects.get(id=student_id)
            academic_period = AcademicPeriod.objects.get(id=academic_period_id)
            subject_groups = SubjectGroup.objects.filter(id__in=subject_group_ids)
        except (Student.DoesNotExist, AcademicPeriod.DoesNotExist):
            return Response(
                {'error': 'Invalid student or academic period ID.'},
                status=status.HTTP_404_NOT_FOUND
            )

        if not subject_groups.exists():
            return Response(
                {'error': 'No valid subject groups found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Get all schedules for the selected groups
        from schedules.models import Schedule

        conflicts = []
        schedules_by_group = {}

        for group in subject_groups:
            schedules = Schedule.objects.filter(
                subject_group=group,
                is_active=True
            ).select_related('time_slot', 'subject_group__subject')
            schedules_by_group[group.id] = list(schedules)

        # Check for conflicts between each pair of groups
        group_ids = list(schedules_by_group.keys())
        for i in range(len(group_ids)):
            for j in range(i + 1, len(group_ids)):
                group1_id = group_ids[i]
                group2_id = group_ids[j]

                schedules1 = schedules_by_group[group1_id]
                schedules2 = schedules_by_group[group2_id]

                for schedule1 in schedules1:
                    for schedule2 in schedules2:
                        if self._schedules_overlap(schedule1, schedule2):
                            conflicts.append({
                                'subject1': {
                                    'id': schedule1.subject_group.subject.id,
                                    'name': schedule1.subject_group.subject.name,
                                    'code': schedule1.subject_group.subject.code,
                                    'group': schedule1.subject_group.code
                                },
                                'subject2': {
                                    'id': schedule2.subject_group.subject.id,
                                    'name': schedule2.subject_group.subject.name,
                                    'code': schedule2.subject_group.subject.code,
                                    'group': schedule2.subject_group.code
                                },
                                'day': schedule1.time_slot.get_day_of_week_display(),
                                'time': f"{schedule1.time_slot.start_time} - {schedule1.time_slot.end_time}"
                            })

        if conflicts:
            return Response({
                'has_conflicts': True,
                'conflicts': conflicts,
                'message': f'Found {len(conflicts)} schedule conflict(s).'
            })

        return Response({
            'has_conflicts': False,
            'conflicts': [],
            'message': 'No schedule conflicts found.'
        })

    def _schedules_overlap(self, schedule1, schedule2):
        """Check if two schedules overlap"""
        if schedule1.time_slot.day_of_week != schedule2.time_slot.day_of_week:
            return False

        start1 = schedule1.time_slot.start_time
        end1 = schedule1.time_slot.end_time
        start2 = schedule2.time_slot.start_time
        end2 = schedule2.time_slot.end_time

        return (start1 < end2 and end1 > start2)


class CheckCourseCapacityView(APIView):
    """
    Check if courses have available capacity
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        """
        POST /api/forms/validate/capacity/
        Body: {
            "subject_group_ids": [1, 2, 3]
        }
        """
        subject_group_ids = request.data.get('subject_group_ids', [])

        if not subject_group_ids:
            return Response(
                {'error': 'subject_group_ids is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        subject_groups = SubjectGroup.objects.filter(id__in=subject_group_ids).select_related('subject')

        if not subject_groups.exists():
            return Response(
                {'error': 'No valid subject groups found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        capacity_info = []
        all_have_capacity = True

        for group in subject_groups:
            has_capacity = group.has_capacity()
            available_slots = group.max_capacity - group.current_enrollment

            if not has_capacity:
                all_have_capacity = False

            capacity_info.append({
                'subject_group_id': group.id,
                'subject': {
                    'id': group.subject.id,
                    'name': group.subject.name,
                    'code': group.subject.code
                },
                'group_code': group.code,
                'has_capacity': has_capacity,
                'max_capacity': group.max_capacity,
                'current_enrollment': group.current_enrollment,
                'available_slots': available_slots
            })

        return Response({
            'all_have_capacity': all_have_capacity,
            'capacity_info': capacity_info
        })


class GetAvailableCoursesView(APIView):
    """
    Get available courses for a student in a given academic period
    with prerequisite and capacity information
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """
        GET /api/forms/validate/available-courses/?student_id=123&academic_period_id=456&career_enrollment_id=789
        """
        student_id = request.query_params.get('student_id')
        academic_period_id = request.query_params.get('academic_period_id')
        career_enrollment_id = request.query_params.get('career_enrollment_id')

        if not all([student_id, academic_period_id, career_enrollment_id]):
            return Response(
                {'error': 'student_id, academic_period_id, and career_enrollment_id are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            student = Student.objects.get(id=student_id)
            academic_period = AcademicPeriod.objects.get(id=academic_period_id)
            career_enrollment = CareerEnrollment.objects.get(id=career_enrollment_id)
        except (Student.DoesNotExist, AcademicPeriod.DoesNotExist, CareerEnrollment.DoesNotExist):
            return Response(
                {'error': 'Invalid student, academic period, or career enrollment ID.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Get all subjects in the study plan
        study_plan_subjects = StudyPlanSubject.objects.filter(
            study_plan=career_enrollment.study_plan
        ).select_related('subject').prefetch_related('prerequisites')

        # Get subject groups for this academic period
        available_courses = []

        for study_plan_subject in study_plan_subjects:
            subject = study_plan_subject.subject

            # Get groups for this subject in this period
            groups = SubjectGroup.objects.filter(
                subject=subject,
                academic_period=academic_period,
                is_active=True
            )

            if not groups.exists():
                continue

            # Check if student already passed this subject
            already_passed = FinalGrade.objects.filter(
                subject_enrollment__student=student,
                subject_enrollment__subject_group__subject=subject,
                status='passed',
                is_published=True
            ).exists()

            if already_passed:
                continue

            # Check prerequisites
            prerequisites = study_plan_subject.prerequisites.all()
            missing_prerequisites = []

            for prerequisite in prerequisites:
                passed = FinalGrade.objects.filter(
                    subject_enrollment__student=student,
                    subject_enrollment__subject_group__subject=prerequisite,
                    status='passed',
                    is_published=True
                ).exists()

                if not passed:
                    missing_prerequisites.append({
                        'id': prerequisite.id,
                        'code': prerequisite.code,
                        'name': prerequisite.name
                    })

            # Get group information
            groups_info = []
            for group in groups:
                groups_info.append({
                    'id': group.id,
                    'code': group.code,
                    'has_capacity': group.has_capacity(),
                    'max_capacity': group.max_capacity,
                    'current_enrollment': group.current_enrollment,
                    'available_slots': group.max_capacity - group.current_enrollment
                })

            available_courses.append({
                'subject': {
                    'id': subject.id,
                    'code': subject.code,
                    'name': subject.name,
                    'credits': subject.credits,
                    'type': subject.type,
                    'course_year': subject.course_year,
                    'semester': subject.semester
                },
                'groups': groups_info,
                'can_enroll': len(missing_prerequisites) == 0,
                'missing_prerequisites': missing_prerequisites
            })

        return Response({
            'academic_period': {
                'id': academic_period.id,
                'name': academic_period.name,
                'code': academic_period.code
            },
            'available_courses': available_courses
        })


class CalculateTotalCreditsView(APIView):
    """
    Calculate total credits for selected courses
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        """
        POST /api/forms/validate/total-credits/
        Body: {
            "subject_group_ids": [1, 2, 3]
        }
        """
        subject_group_ids = request.data.get('subject_group_ids', [])

        if not subject_group_ids:
            return Response({'total_credits': 0})

        subject_groups = SubjectGroup.objects.filter(
            id__in=subject_group_ids
        ).select_related('subject')

        total_credits = sum(group.subject.credits for group in subject_groups)

        subjects_info = [{
            'id': group.subject.id,
            'code': group.subject.code,
            'name': group.subject.name,
            'credits': group.subject.credits
        } for group in subject_groups]

        return Response({
            'total_credits': total_credits,
            'subjects': subjects_info
        })
