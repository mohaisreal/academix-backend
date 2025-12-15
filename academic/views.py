from rest_framework import viewsets, status, views
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Avg, Count, Q, Sum
from decimal import Decimal
from .models import Career, Subject, AcademicPeriod, StudyPlan, StudyPlanSubject, Classroom
from .serializers import (
    CareerSerializer, SubjectSerializer, AcademicPeriodSerializer,
    StudyPlanSerializer, StudyPlanSubjectSerializer, ClassroomSerializer,
    StudentAcademicRecordSerializer, AcademicStatisticsSerializer,
    SubjectStatisticsSerializer
)
from users.models import Student, Teacher
from enrollment.models import SubjectEnrollment, SubjectGroup
from grades.models import FinalGrade
from authentication.permissions import IsStudentUser, IsTeacherUser, IsAdminUser


class CareerViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing careers
    Only admins can create, update, or delete careers
    """
    queryset = Career.objects.all()
    serializer_class = CareerSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        """
        Set permissions based on action
        - list, retrieve: Any authenticated user
        - create, update, partial_update, destroy: Admin only
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAuthenticated, IsAdminUser]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = super().get_queryset()
        is_active = self.request.query_params.get('is_active', None)

        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')

        return queryset

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Get career statistics
        """
        from enrollment.models import Enrollment
        from users.models import Student

        total_careers = Career.objects.filter(is_active=True).count()
        total_students = Student.objects.count()
        total_subjects = Subject.objects.filter(is_active=True).count()

        careers_data = []
        for career in Career.objects.filter(is_active=True):
            # This is a simplification - you would need to adjust according to your data model
            careers_data.append({
                'id': career.id,
                'name': career.name,
                'code': career.code,
                'students_enrolled': 0  # Here you should count actual students
            })

        return Response({
            'total': total_careers,
            'total_students': total_students,
            'total_subjects': total_subjects,
            'careers': careers_data
        })


class SubjectViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing subjects
    Only admins can create, update, or delete subjects
    """
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        """
        Set permissions based on action
        - list, retrieve: Any authenticated user
        - create, update, partial_update, destroy: Admin only
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAuthenticated, IsAdminUser]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = super().get_queryset()
        course_year = self.request.query_params.get('course_year', None)
        semester = self.request.query_params.get('semester', None)
        is_active = self.request.query_params.get('is_active', None)

        if course_year:
            queryset = queryset.filter(course_year=course_year)
        if semester:
            queryset = queryset.filter(semester=semester)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')

        return queryset

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Get subject statistics
        """
        total = Subject.objects.filter(is_active=True).count()
        by_course = {}

        for i in range(1, 5):
            by_course[f'course{i}'] = Subject.objects.filter(
                course_year=i,
                is_active=True
            ).count()

        return Response({
            'total': total,
            **by_course
        })


class AcademicPeriodViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing academic periods
    Only admins can create, update, or delete academic periods
    """
    queryset = AcademicPeriod.objects.all()
    serializer_class = AcademicPeriodSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        """
        Set permissions based on action
        - list, retrieve, current: Any authenticated user
        - create, update, partial_update, destroy: Admin only
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAuthenticated, IsAdminUser]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = super().get_queryset()
        is_active = self.request.query_params.get('is_active', None)

        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')

        return queryset.order_by('-start_date')

    @action(detail=False, methods=['get'])
    def current(self, request):
        """
        Get current academic period
        """
        from datetime import date
        today = date.today()

        current_period = AcademicPeriod.objects.filter(
            start_date__lte=today,
            end_date__gte=today
        ).first()

        if current_period:
            serializer = self.get_serializer(current_period)
            return Response(serializer.data)

        return Response({'detail': 'No hay periodo académico activo'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Get academic period statistics
        """
        from datetime import date
        today = date.today()

        total = AcademicPeriod.objects.count()
        active = AcademicPeriod.objects.filter(
            start_date__lte=today,
            end_date__gte=today
        ).count()
        upcoming = AcademicPeriod.objects.filter(start_date__gt=today).count()
        completed = AcademicPeriod.objects.filter(end_date__lt=today).count()

        return Response({
            'total': total,
            'active': active,
            'upcoming': upcoming,
            'completed': completed
        })


# Academic Reports Views

class StudentAcademicRecordView(views.APIView):
    """
    View for retrieving student academic record
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, student_id=None):
        # If student_id is provided, check permissions
        if student_id:
            # Admins can access any student's record
            if request.user.role == 'admin':
                pass
            # Teachers can only access their students' records
            elif request.user.role == 'teacher':
                try:
                    teacher = request.user.teacher_profile
                    # Check if the student is enrolled in any of the teacher's subject groups
                    student_enrollments = SubjectEnrollment.objects.filter(
                        student_id=student_id,
                        subject_group__teacher=teacher,
                        status='enrolled'
                    )
                    if not student_enrollments.exists():
                        return Response(
                            {'error': 'No tienes permisos para ver el expediente de este estudiante'},
                            status=status.HTTP_403_FORBIDDEN
                        )
                except AttributeError:
                    return Response(
                        {'error': 'Perfil de profesor no encontrado'},
                        status=status.HTTP_404_NOT_FOUND
                    )
            else:
                return Response(
                    {'error': 'No tienes permisos para ver el expediente de otro estudiante'},
                    status=status.HTTP_403_FORBIDDEN
                )

            try:
                student = Student.objects.get(id=student_id)
            except Student.DoesNotExist:
                return Response({'error': 'Estudiante no encontrado'}, status=status.HTTP_404_NOT_FOUND)
        else:
            # Get the current user's student profile (only for students)
            if request.user.role != 'student':
                return Response(
                    {'error': 'Debes especificar un ID de estudiante'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            try:
                student = request.user.student_profile
            except AttributeError:
                return Response(
                    {'error': 'Perfil de estudiante no encontrado'},
                    status=status.HTTP_404_NOT_FOUND
                )

        # Get all enrollments with final grades
        enrollments = SubjectEnrollment.objects.filter(
            student=student
        ).select_related(
            'subject_group__subject',
            'subject_group__academic_period',
            'career_enrollment__career'
        ).prefetch_related('final_grade')

        # Get all career enrollments
        from enrollment.models import CareerEnrollment
        career_enrollments = CareerEnrollment.objects.filter(
            student=student
        ).select_related('career').order_by('-enrollment_date')

        # Calculate overall statistics
        total_credits_attempted = 0
        total_credits_earned = 0
        total_score = Decimal('0.0')
        subjects_with_grades = 0
        passed_subjects = 0
        failed_subjects = 0
        pending_subjects = 0

        for enrollment in enrollments:
            credits = enrollment.subject_group.subject.credits
            total_credits_attempted += credits

            try:
                final_grade = enrollment.final_grade
                if final_grade.final_score is not None:
                    total_score += final_grade.final_score
                    subjects_with_grades += 1

                if final_grade.status == 'passed':
                    total_credits_earned += credits
                    passed_subjects += 1
                elif final_grade.status == 'failed':
                    failed_subjects += 1
                else:
                    pending_subjects += 1
            except FinalGrade.DoesNotExist:
                pending_subjects += 1

        # Calculate overall GPA
        overall_gpa = (total_score / subjects_with_grades) if subjects_with_grades > 0 else Decimal('0.0')

        # Group enrollments by career and period
        careers_data = []
        for career_enrollment in career_enrollments:
            career_info = {
                'career_id': career_enrollment.career.id,
                'career_name': career_enrollment.career.name,
                'career_code': career_enrollment.career.code,
                'enrollment_date': career_enrollment.enrollment_date,
                'status': career_enrollment.status,
                'status_display': career_enrollment.get_status_display(),
                'periods': []
            }

            # Get enrollments for this career grouped by period
            career_subject_enrollments = enrollments.filter(career_enrollment=career_enrollment)

            # Group by period
            periods_dict = {}
            for enrollment in career_subject_enrollments:
                period = enrollment.subject_group.academic_period
                period_key = period.id

                if period_key not in periods_dict:
                    periods_dict[period_key] = {
                        'period_id': period.id,
                        'period_name': period.name,
                        'period_code': period.code,
                        'start_date': period.start_date,
                        'end_date': period.end_date,
                        'enrollments': [],
                        'credits_attempted': 0,
                        'credits_earned': 0,
                        'period_gpa': Decimal('0.0'),
                        'passed_count': 0,
                        'failed_count': 0,
                        'pending_count': 0,
                        'total_score': Decimal('0.0'),
                        'graded_count': 0
                    }

                # Add enrollment data
                credits = enrollment.subject_group.subject.credits
                periods_dict[period_key]['credits_attempted'] += credits

                enrollment_data = {
                    'id': enrollment.id,
                    'subject_code': enrollment.subject_group.subject.code,
                    'subject_name': enrollment.subject_group.subject.name,
                    'credits': credits,
                    'enrollment_date': enrollment.enrollment_date
                }

                try:
                    final_grade = enrollment.final_grade
                    enrollment_data['final_score'] = final_grade.final_score
                    enrollment_data['status'] = final_grade.status
                    enrollment_data['status_display'] = final_grade.get_status_display()

                    if final_grade.final_score is not None:
                        periods_dict[period_key]['total_score'] += final_grade.final_score
                        periods_dict[period_key]['graded_count'] += 1

                    if final_grade.status == 'passed':
                        periods_dict[period_key]['credits_earned'] += credits
                        periods_dict[period_key]['passed_count'] += 1
                    elif final_grade.status == 'failed':
                        periods_dict[period_key]['failed_count'] += 1
                    else:
                        periods_dict[period_key]['pending_count'] += 1
                except FinalGrade.DoesNotExist:
                    enrollment_data['final_score'] = None
                    enrollment_data['status'] = 'pending'
                    enrollment_data['status_display'] = 'Pendiente'
                    periods_dict[period_key]['pending_count'] += 1

                periods_dict[period_key]['enrollments'].append(enrollment_data)

            # Calculate period GPAs and prepare periods list
            for period_data in periods_dict.values():
                if period_data['graded_count'] > 0:
                    period_data['period_gpa'] = float(round(period_data['total_score'] / period_data['graded_count'], 2))
                else:
                    period_data['period_gpa'] = 0.0

                # Remove temporary calculation fields
                del period_data['total_score']
                del period_data['graded_count']

                career_info['periods'].append(period_data)

            # Sort periods by start date (most recent first)
            career_info['periods'].sort(key=lambda x: x['start_date'], reverse=True)

            careers_data.append(career_info)

        data = {
            'student_id': student.id,
            'student_name': student.user.get_full_name(),
            'student_code': student.student_id,
            'total_credits_attempted': total_credits_attempted,
            'total_credits_earned': total_credits_earned,
            'overall_gpa': float(round(overall_gpa, 2)),
            'passed_subjects': passed_subjects,
            'failed_subjects': failed_subjects,
            'pending_subjects': pending_subjects,
            'careers': careers_data
        }

        return Response(data)


class AcademicStatisticsView(views.APIView):
    """
    View for retrieving academic statistics (Admin only)
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        # Overall statistics
        total_students = Student.objects.count()
        total_subjects = Subject.objects.filter(is_active=True).count()
        total_enrollments = SubjectEnrollment.objects.count()

        # Calculate average GPA
        final_grades = FinalGrade.objects.filter(
            final_score__isnull=False
        ).aggregate(avg_gpa=Avg('final_score'))
        average_gpa = final_grades['avg_gpa'] or Decimal('0.0')

        # Pass/Fail rates
        grade_counts = FinalGrade.objects.aggregate(
            passed=Count('id', filter=Q(status='passed')),
            failed=Count('id', filter=Q(status='failed')),
            total=Count('id', filter=Q(status__in=['passed', 'failed']))
        )

        pass_rate = (grade_counts['passed'] / grade_counts['total'] * 100) if grade_counts['total'] > 0 else 0
        fail_rate = (grade_counts['failed'] / grade_counts['total'] * 100) if grade_counts['total'] > 0 else 0

        # Statistics by career
        by_career = {}
        from enrollment.models import CareerEnrollment
        for career in Career.objects.filter(is_active=True):
            # Get students enrolled in this career
            career_student_ids = CareerEnrollment.objects.filter(
                career=career,
                status='active'
            ).values_list('student_id', flat=True)
            career_students = Student.objects.filter(id__in=career_student_ids).count()
            career_enrollments = SubjectEnrollment.objects.filter(student_id__in=career_student_ids)

            career_grades = FinalGrade.objects.filter(
                subject_enrollment__student_id__in=career_student_ids,
                final_score__isnull=False
            ).aggregate(
                avg_gpa=Avg('final_score'),
                passed=Count('id', filter=Q(status='passed')),
                failed=Count('id', filter=Q(status='failed')),
                total=Count('id', filter=Q(status__in=['passed', 'failed']))
            )

            by_career[career.name] = {
                'students': career_students,
                'enrollments': career_enrollments.count(),
                'average_gpa': round(career_grades['avg_gpa'] or 0, 2),
                'pass_rate': round((career_grades['passed'] / career_grades['total'] * 100) if career_grades['total'] > 0 else 0, 2)
            }

        # Statistics by period
        by_period = {}
        for period in AcademicPeriod.objects.all()[:5]:  # Last 5 periods
            period_enrollments = SubjectEnrollment.objects.filter(subject_group__academic_period=period)

            period_grades = FinalGrade.objects.filter(
                subject_enrollment__subject_group__academic_period=period,
                final_score__isnull=False
            ).aggregate(
                avg_gpa=Avg('final_score'),
                passed=Count('id', filter=Q(status='passed')),
                failed=Count('id', filter=Q(status='failed')),
                total=Count('id', filter=Q(status__in=['passed', 'failed']))
            )

            by_period[period.name] = {
                'enrollments': period_enrollments.count(),
                'average_gpa': round(period_grades['avg_gpa'] or 0, 2),
                'pass_rate': round((period_grades['passed'] / period_grades['total'] * 100) if period_grades['total'] > 0 else 0, 2)
            }

        data = {
            'total_students': total_students,
            'total_subjects': total_subjects,
            'total_enrollments': total_enrollments,
            'average_gpa': float(round(average_gpa, 2)),
            'pass_rate': float(round(pass_rate, 2)),
            'fail_rate': float(round(fail_rate, 2)),
            'by_career': by_career,
            'by_period': by_period,
        }

        return Response(data)


class TeacherSubjectStudentsView(views.APIView):
    """
    View for teachers to see students enrolled in their subjects
    """
    permission_classes = [IsAuthenticated, IsTeacherUser]

    def get(self, request, subject_group_id):
        try:
            teacher = request.user.teacher_profile
        except AttributeError:
            return Response({'error': 'Perfil de profesor no encontrado'}, status=status.HTTP_404_NOT_FOUND)

        # Verify teacher teaches this subject group
        try:
            subject_group = SubjectGroup.objects.get(id=subject_group_id, teacher=teacher)
        except SubjectGroup.DoesNotExist:
            return Response({'error': 'Grupo no encontrado o no autorizado'}, status=status.HTTP_404_NOT_FOUND)

        # Get enrolled students
        enrollments = SubjectEnrollment.objects.filter(
            subject_group=subject_group,
            status='enrolled'
        ).select_related(
            'student__user'
        ).prefetch_related('grades', 'final_grade')

        # Get all student IDs to fetch their careers in one query
        from enrollment.models import CareerEnrollment
        student_ids = [enrollment.student_id for enrollment in enrollments]
        career_enrollments = CareerEnrollment.objects.filter(
            student_id__in=student_ids,
            status='active'
        ).select_related('career')

        # Create a dictionary mapping student_id to career name
        student_careers = {
            ce.student_id: ce.career.name
            for ce in career_enrollments
        }

        students_data = []
        for enrollment in enrollments:
            student = enrollment.student

            # Calculate current average
            grades = enrollment.grades.filter(score__isnull=False)
            total_score = Decimal('0.0')
            total_weight = Decimal('0.0')

            for grade in grades:
                if grade.evaluation.is_published:
                    weight = grade.evaluation.weight / 100
                    normalized_score = (grade.score / grade.evaluation.max_score) * 10
                    total_score += normalized_score * weight
                    total_weight += weight

            current_average = total_score if total_weight > 0 else None

            # Get final grade if exists
            final_grade = None
            final_status = None
            try:
                final = enrollment.final_grade
                final_grade = final.final_score
                final_status = final.get_status_display()
            except FinalGrade.DoesNotExist:
                pass

            students_data.append({
                'enrollment_id': enrollment.id,
                'student_id': student.id,
                'student_code': student.student_id,
                'student_name': student.user.get_full_name(),
                'student_email': student.user.email,
                'career': student_careers.get(student.id, 'N/A'),
                'current_average': round(current_average, 2) if current_average else None,
                'final_grade': final_grade,
                'status': final_status,
                'enrolled_at': enrollment.enrolled_at
            })

        return Response({
            'subject_group': {
                'id': subject_group.id,
                'subject_code': subject_group.subject.code,
                'subject_name': subject_group.subject.name,
                'group_code': subject_group.group_code,
                'academic_period': subject_group.academic_period.name,
            },
            'total_students': len(students_data),
            'students': students_data
        })


class SubjectStatisticsView(views.APIView):
    """
    View for subject-specific statistics (Teachers and Admin)
    """
    permission_classes = [IsAuthenticated, IsTeacherUser | IsAdminUser]

    def get(self, request, subject_id):
        try:
            subject = Subject.objects.get(id=subject_id)
        except Subject.DoesNotExist:
            return Response({'error': 'Asignatura no encontrada'}, status=status.HTTP_404_NOT_FOUND)

        # Get all enrollments for this subject across all groups
        enrollments = SubjectEnrollment.objects.filter(
            subject_group__subject=subject
        )

        total_enrollments = enrollments.count()

        # Get grade statistics
        final_grades = FinalGrade.objects.filter(
            subject_enrollment__subject_group__subject=subject
        )

        grade_stats = final_grades.aggregate(
            avg_grade=Avg('final_score', filter=Q(final_score__isnull=False)),
            passed=Count('id', filter=Q(status='passed')),
            failed=Count('id', filter=Q(status='failed')),
            pending=Count('id', filter=Q(status='pending'))
        )

        average_grade = grade_stats['avg_grade'] or Decimal('0.0')
        passed_count = grade_stats['passed']
        failed_count = grade_stats['failed']
        pending_count = grade_stats['pending']

        total_graded = passed_count + failed_count
        pass_rate = (passed_count / total_graded * 100) if total_graded > 0 else 0

        data = {
            'subject_id': subject.id,
            'subject_code': subject.code,
            'subject_name': subject.name,
            'total_enrollments': total_enrollments,
            'passed_count': passed_count,
            'failed_count': failed_count,
            'pending_count': pending_count,
            'average_grade': float(round(average_grade, 2)),
            'pass_rate': float(round(pass_rate, 2)),
        }

        return Response(data)


# Additional ViewSets for complete CRUD
class StudyPlanViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing study plans
    """
    queryset = StudyPlan.objects.all()
    serializer_class = StudyPlanSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAuthenticated, IsAdminUser]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = super().get_queryset()
        career_id = self.request.query_params.get('career', None)
        is_active = self.request.query_params.get('is_active', None)

        if career_id:
            queryset = queryset.filter(career_id=career_id)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')

        return queryset.order_by('-start_year')

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsAdminUser])
    def add_subject(self, request, pk=None):
        """Add subject to study plan"""
        study_plan = self.get_object()
        subject_id = request.data.get('subject_id')
        prerequisite_ids = request.data.get('prerequisites', [])

        try:
            subject = Subject.objects.get(id=subject_id)
        except Subject.DoesNotExist:
            return Response({'error': 'Asignatura no encontrada'}, status=status.HTTP_404_NOT_FOUND)

        # Check if subject already in study plan
        if StudyPlanSubject.objects.filter(study_plan=study_plan, subject=subject).exists():
            return Response({'error': 'La asignatura ya está en el plan de estudios'}, status=status.HTTP_400_BAD_REQUEST)

        # Create study plan subject
        study_plan_subject = StudyPlanSubject.objects.create(
            study_plan=study_plan,
            subject=subject
        )

        # Add prerequisites
        if prerequisite_ids:
            prerequisites = Subject.objects.filter(id__in=prerequisite_ids)
            study_plan_subject.prerequisites.set(prerequisites)

        serializer = StudyPlanSubjectSerializer(study_plan_subject)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['delete'], permission_classes=[IsAuthenticated, IsAdminUser])
    def remove_subject(self, request, pk=None):
        """Remove subject from study plan"""
        study_plan = self.get_object()
        subject_id = request.data.get('subject_id')

        try:
            study_plan_subject = StudyPlanSubject.objects.get(
                study_plan=study_plan,
                subject_id=subject_id
            )
            study_plan_subject.delete()
            return Response({'message': 'Asignatura eliminada del plan de estudios'}, status=status.HTTP_204_NO_CONTENT)
        except StudyPlanSubject.DoesNotExist:
            return Response({'error': 'Asignatura no encontrada en el plan de estudios'}, status=status.HTTP_404_NOT_FOUND)


class ClassroomViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing classrooms
    """
    queryset = Classroom.objects.all()
    serializer_class = ClassroomSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAuthenticated, IsAdminUser]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = super().get_queryset()
        building = self.request.query_params.get('building', None)
        has_projector = self.request.query_params.get('has_projector', None)
        has_computers = self.request.query_params.get('has_computers', None)
        is_active = self.request.query_params.get('is_active', None)

        if building:
            queryset = queryset.filter(building__icontains=building)
        if has_projector is not None:
            queryset = queryset.filter(has_projector=has_projector.lower() == 'true')
        if has_computers is not None:
            queryset = queryset.filter(has_computers=has_computers.lower() == 'true')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')

        return queryset

    @action(detail=False, methods=['get'])
    def availability(self, request):
        """Check classroom availability for a specific time slot"""
        time_slot_id = request.query_params.get('time_slot')
        academic_period_id = request.query_params.get('period')

        if not time_slot_id or not academic_period_id:
            return Response(
                {'error': 'Se requieren time_slot y period'},
                status=status.HTTP_400_BAD_REQUEST
            )

        from schedules.models import Schedule
        occupied_classroom_ids = Schedule.objects.filter(
            time_slot_id=time_slot_id,
            subject_group__academic_period_id=academic_period_id,
            is_active=True
        ).values_list('classroom_id', flat=True)

        available_classrooms = Classroom.objects.filter(
            is_active=True
        ).exclude(id__in=occupied_classroom_ids)

        serializer = self.get_serializer(available_classrooms, many=True)
        return Response(serializer.data)
