from rest_framework import viewsets, status, views
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Count
from django.db import transaction
from django.utils import timezone
from datetime import date

from .models import CareerEnrollment, SubjectGroup, SubjectEnrollment, WaitingList
from .serializers import (
    CareerEnrollmentSerializer, SubjectGroupSerializer, SubjectEnrollmentSerializer,
    EnrollmentRequestSerializer, WaitingListSerializer, EnrollmentSummarySerializer,
    BulkEnrollmentSerializer
)
from users.models import Student
from academic.models import Career, StudyPlan, AcademicPeriod, Subject
from authentication.permissions import IsStudentUser, IsTeacherUser, IsAdminUser


class CareerEnrollmentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing career enrollments
    """
    queryset = CareerEnrollment.objects.all().select_related(
        'student__user', 'career', 'study_plan'
    )
    serializer_class = CareerEnrollmentSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAuthenticated, IsAdminUser]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        # Filter based on user role for security
        if user.role == 'student' and hasattr(user, 'student_profile'):
            # Students can only see their own career enrollments
            queryset = queryset.filter(student=user.student_profile)
        elif user.role == 'teacher':
            # Teachers cannot access career enrollments directly
            queryset = queryset.none()

        # Admin users can filter by parameters
        career_id = self.request.query_params.get('career', None)
        status_filter = self.request.query_params.get('status', None)
        student_id = self.request.query_params.get('student', None)

        if career_id:
            queryset = queryset.filter(career_id=career_id)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if student_id and user.role == 'admin':
            queryset = queryset.filter(student_id=student_id)

        return queryset.order_by('-enrollment_date')

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get career enrollment statistics"""
        total = CareerEnrollment.objects.count()
        active = CareerEnrollment.objects.filter(status='active').count()
        completed = CareerEnrollment.objects.filter(status='completed').count()
        dropped = CareerEnrollment.objects.filter(status='dropped').count()
        suspended = CareerEnrollment.objects.filter(status='suspended').count()

        # Stats by career
        by_career = Career.objects.annotate(
            enrollment_count=Count('enrollments', filter=Q(enrollments__status='active'))
        ).values('name', 'code', 'enrollment_count')

        return Response({
            'total': total,
            'active': active,
            'completed': completed,
            'dropped': dropped,
            'suspended': suspended,
            'by_career': list(by_career)
        })


class SubjectGroupViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing subject groups
    """
    queryset = SubjectGroup.objects.all().select_related(
        'subject', 'academic_period'
    )
    serializer_class = SubjectGroupSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAuthenticated, IsAdminUser]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = super().get_queryset()
        subject_id = self.request.query_params.get('subject', None)
        period_id = self.request.query_params.get('period', None)
        has_capacity = self.request.query_params.get('has_capacity', None)
        is_active = self.request.query_params.get('is_active', None)
        career_id = self.request.query_params.get('career', None)
        teacher_id = self.request.query_params.get('teacher', None)

        if subject_id:
            queryset = queryset.filter(subject_id=subject_id)
        if period_id:
            queryset = queryset.filter(academic_period_id=period_id)
        if has_capacity == 'true':
            from django.db import models
            queryset = queryset.filter(current_enrollment__lt=models.F('max_capacity'))
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        if career_id:
            queryset = queryset.filter(subject__study_plans__study_plan__career_id=career_id).distinct()
        if teacher_id:
            # Filter groups assigned to this teacher
            from schedules.models import TeacherAssignment
            queryset = queryset.filter(
                teacher_assignments__teacher_id=teacher_id,
                teacher_assignments__status='active'
            ).distinct()

        return queryset.order_by('subject__code', 'code')

    @action(detail=True, methods=['get'])
    def enrollments(self, request, pk=None):
        """Get enrollments for this subject group"""
        subject_group = self.get_object()
        enrollments = SubjectEnrollment.objects.filter(
            subject_group=subject_group
        ).select_related('student__user', 'career_enrollment__career')

        enrollment_data = []
        for enrollment in enrollments:
            enrollment_data.append({
                'id': enrollment.id,
                'student_id': enrollment.student.student_id,
                'student_name': enrollment.student.user.get_full_name(),
                'student_email': enrollment.student.user.email,
                'career': enrollment.career_enrollment.career.name,
                'enrollment_date': enrollment.enrollment_date,
                'status': enrollment.status
            })

        return Response({
            'subject_group': {
                'id': subject_group.id,
                'subject_name': subject_group.subject.name,
                'subject_code': subject_group.subject.code,
                'group_code': subject_group.code,
                'max_capacity': subject_group.max_capacity,
                'current_enrollment': subject_group.current_enrollment
            },
            'enrollments': enrollment_data
        })

    @action(detail=True, methods=['get'])
    def waiting_list(self, request, pk=None):
        """Get waiting list for this subject group"""
        subject_group = self.get_object()
        waiting_list = WaitingList.objects.filter(
            subject_group=subject_group,
            status='waiting'
        ).select_related('student__user').order_by('position')

        waiting_data = []
        for waiting in waiting_list:
            waiting_data.append({
                'id': waiting.id,
                'student_id': waiting.student.student_id,
                'student_name': waiting.student.user.get_full_name(),
                'position': waiting.position,
                'created_at': waiting.created_at
            })

        return Response({
            'subject_group': {
                'id': subject_group.id,
                'subject_name': subject_group.subject.name,
                'group_code': subject_group.code,
            },
            'waiting_list': waiting_data
        })


class SubjectEnrollmentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing subject enrollments
    """
    queryset = SubjectEnrollment.objects.all().select_related(
        'student__user', 'subject_group__subject', 'subject_group__academic_period',
        'career_enrollment__career'
    )
    serializer_class = SubjectEnrollmentSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in ['create']:
            permission_classes = [IsAuthenticated, IsStudentUser | IsAdminUser]
        elif self.action in ['update', 'partial_update', 'destroy']:
            permission_classes = [IsAuthenticated, IsAdminUser]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        # Filter based on user role
        if user.role == 'student' and hasattr(user, 'student_profile'):
            queryset = queryset.filter(student=user.student_profile)
        elif user.role == 'teacher' and hasattr(user, 'teacher_profile'):
            # Teachers can see enrollments for subjects they teach
            from schedules.models import TeacherAssignment
            assigned_groups = TeacherAssignment.objects.filter(
                teacher=user.teacher_profile,
                status='active'
            ).values_list('subject_group_id', flat=True)
            queryset = queryset.filter(subject_group_id__in=assigned_groups)

        # Additional filters
        student_id = self.request.query_params.get('student', None)
        subject_group_id = self.request.query_params.get('subject_group', None)
        period_id = self.request.query_params.get('period', None)
        status_filter = self.request.query_params.get('status', None)

        if student_id and user.role == 'admin':
            queryset = queryset.filter(student_id=student_id)
        if subject_group_id:
            queryset = queryset.filter(subject_group_id=subject_group_id)
        if period_id:
            queryset = queryset.filter(subject_group__academic_period_id=period_id)
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        return queryset.order_by('-enrollment_date')

    @action(detail=False, methods=['post'])
    def enroll(self, request):
        """Enroll student in subject"""
        serializer = EnrollmentRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        subject_group_id = serializer.validated_data['subject_group_id']
        career_enrollment_id = serializer.validated_data['career_enrollment_id']
        force_enroll = serializer.validated_data['force_enroll']

        try:
            with transaction.atomic():
                subject_group = SubjectGroup.objects.select_for_update().get(
                    id=subject_group_id
                )
                career_enrollment = CareerEnrollment.objects.get(
                    id=career_enrollment_id
                )
                student = career_enrollment.student

                # Check if user can enroll this student
                if (request.user.role == 'student' and
                    hasattr(request.user, 'student_profile') and
                    request.user.student_profile != student):
                    return Response(
                        {'error': 'No puedes inscribir a otro estudiante'},
                        status=status.HTTP_403_FORBIDDEN
                    )

                # Check if student already has an enrollment in this subject group
                existing_enrollment = SubjectEnrollment.objects.filter(
                    student=student,
                    subject_group=subject_group
                ).first()

                if existing_enrollment:
                    if existing_enrollment.status == 'enrolled':
                        return Response(
                            {'error': 'Ya estás inscrito en esta asignatura'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    else:
                        # Reactivate the enrollment
                        previous_status = existing_enrollment.status
                        existing_enrollment.status = 'enrolled'
                        existing_enrollment.career_enrollment = career_enrollment
                        existing_enrollment.enrollment_date = timezone.now()
                        existing_enrollment.save()

                        # Update group enrollment count only if previously not enrolled
                        if previous_status != 'enrolled':
                            subject_group.current_enrollment += 1
                            subject_group.save()

                        # Check if student was on waiting list and remove
                        WaitingList.objects.filter(
                            student=student,
                            subject_group=subject_group,
                            status='waiting'
                        ).update(status='enrolled')

                        serializer = SubjectEnrollmentSerializer(existing_enrollment)
                        return Response({
                            'message': 'Inscripción reactivada exitosamente',
                            'enrollment': serializer.data,
                            'type': 'enrolled'
                        }, status=status.HTTP_200_OK)

                # Check capacity
                if not subject_group.has_capacity() and not force_enroll:
                    # Add to waiting list
                    from django.db import models
                    last_position = WaitingList.objects.filter(
                        subject_group=subject_group
                    ).aggregate(models.Max('position'))['position__max'] or 0

                    waiting_entry = WaitingList.objects.create(
                        student=student,
                        subject_group=subject_group,
                        position=last_position + 1
                    )

                    return Response({
                        'message': 'Grupo lleno. Estudiante añadido a lista de espera.',
                        'waiting_list_position': waiting_entry.position,
                        'type': 'waiting_list'
                    })

                # Create enrollment
                enrollment = SubjectEnrollment.objects.create(
                    student=student,
                    subject_group=subject_group,
                    career_enrollment=career_enrollment
                )
                # Note: The model's save() method already increments current_enrollment

                # Check if student was on waiting list and remove
                WaitingList.objects.filter(
                    student=student,
                    subject_group=subject_group,
                    status='waiting'
                ).update(status='enrolled')

                serializer = SubjectEnrollmentSerializer(enrollment)
                return Response({
                    'message': 'Inscripción exitosa',
                    'enrollment': serializer.data,
                    'type': 'enrolled'
                }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['post'])
    def drop(self, request, pk=None):
        """Drop student from subject"""
        enrollment = self.get_object()

        if (request.user.role == 'student' and
            hasattr(request.user, 'student_profile') and
            request.user.student_profile != enrollment.student):
            return Response(
                {'error': 'No puedes retirar a otro estudiante'},
                status=status.HTTP_403_FORBIDDEN
            )

        with transaction.atomic():
            # Update enrollment status
            enrollment.status = 'dropped'
            enrollment.save()

            # Decrease group enrollment count
            subject_group = enrollment.subject_group
            if subject_group.current_enrollment > 0:
                subject_group.current_enrollment -= 1
                subject_group.save()

                # Check waiting list and enroll next student
                next_waiting = WaitingList.objects.filter(
                    subject_group=subject_group,
                    status='waiting'
                ).order_by('position').first()

                if next_waiting:
                    # Find active career enrollment for this student
                    career_enrollment = CareerEnrollment.objects.filter(
                        student=next_waiting.student,
                        status='active'
                    ).first()

                    if career_enrollment:
                        SubjectEnrollment.objects.create(
                            student=next_waiting.student,
                            subject_group=subject_group,
                            career_enrollment=career_enrollment
                        )

                        next_waiting.status = 'enrolled'
                        next_waiting.save()

                        subject_group.current_enrollment += 1
                        subject_group.save()

        return Response({'message': 'Estudiante retirado exitosamente'})

    @action(detail=False, methods=['get'])
    def my_enrollments(self, request):
        """Get current user's enrollments"""
        if not hasattr(request.user, 'student_profile'):
            return Response(
                {'error': 'Solo disponible para estudiantes'},
                status=status.HTTP_403_FORBIDDEN
            )

        student = request.user.student_profile
        enrollments = SubjectEnrollment.objects.filter(
            student=student,
            status='enrolled'
        ).select_related('subject_group__subject', 'subject_group__academic_period')

        # Use serializer to get properly formatted enrollment data
        serializer = SubjectEnrollmentSerializer(enrollments, many=True)
        enrollment_data = serializer.data

        # Calculate total credits
        total_credits = sum(
            enrollment.subject_group.subject.credits
            for enrollment in enrollments
        )

        # Get waiting list entries
        waiting_list = WaitingList.objects.filter(
            student=student,
            status='waiting'
        ).select_related('subject_group__subject')

        waiting_data = []
        for waiting in waiting_list:
            waiting_data.append({
                'id': waiting.id,
                'subject_code': waiting.subject_group.subject.code,
                'subject_name': waiting.subject_group.subject.name,
                'group_code': waiting.subject_group.code,
                'position': waiting.position,
                'created_at': waiting.created_at
            })

        return Response({
            'student': {
                'id': student.id,
                'name': student.user.get_full_name(),
                'student_id': student.student_id
            },
            'enrolled_subjects': enrollment_data,
            'waiting_subjects': waiting_data,
            'total_credits': total_credits
        })


class EnrollmentProcessView(views.APIView):
    """
    View for handling the complete enrollment process
    """
    permission_classes = [IsAuthenticated, IsStudentUser | IsAdminUser]

    def get(self, request):
        """Get enrollment information for current academic period"""
        user = request.user

        if user.role == 'student':
            if not hasattr(user, 'student_profile'):
                return Response(
                    {'error': 'Perfil de estudiante no encontrado'},
                    status=status.HTTP_404_NOT_FOUND
                )
            student = user.student_profile
        else:
            student_id = request.query_params.get('student_id')
            if not student_id:
                return Response(
                    {'error': 'student_id requerido para administradores'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            try:
                student = Student.objects.get(id=student_id)
            except Student.DoesNotExist:
                return Response(
                    {'error': 'Estudiante no encontrado'},
                    status=status.HTTP_404_NOT_FOUND
                )

        # Get current academic period
        today = date.today()
        current_period = AcademicPeriod.objects.filter(
            start_date__lte=today,
            end_date__gte=today
        ).first()

        if not current_period:
            return Response(
                {'error': 'No hay período académico activo'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check enrollment dates
        enrollment_status = 'closed'
        if current_period.enrollment_start <= today <= current_period.enrollment_end:
            enrollment_status = 'open'
        elif today < current_period.enrollment_start:
            enrollment_status = 'not_started'

        # Get student's career enrollments
        career_enrollments = CareerEnrollment.objects.filter(
            student=student,
            status='active'
        )

        if not career_enrollments.exists():
            return Response(
                {'error': 'Estudiante no matriculado en ninguna carrera'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get available subjects for enrollment
        available_subjects = []
        current_enrollments = []

        for career_enrollment in career_enrollments:
            # Get subjects from study plan
            study_plan_subjects = career_enrollment.study_plan.subjects.all()

            # Get current enrollments for this period
            enrolled_subjects = SubjectEnrollment.objects.filter(
                student=student,
                subject_group__academic_period=current_period,
                career_enrollment=career_enrollment,
                status='enrolled'
            ).select_related('subject_group__subject')

            for enrollment in enrolled_subjects:
                current_enrollments.append({
                    'subject_code': enrollment.subject_group.subject.code,
                    'subject_name': enrollment.subject_group.subject.name,
                    'group_code': enrollment.subject_group.code,
                    'credits': enrollment.subject_group.subject.credits
                })

            # Get available subject groups
            enrolled_subject_ids = enrolled_subjects.values_list(
                'subject_group__subject_id', flat=True
            )

            for study_plan_subject in study_plan_subjects:
                if study_plan_subject.subject.id not in enrolled_subject_ids:
                    subject_groups = SubjectGroup.objects.filter(
                        subject=study_plan_subject.subject,
                        academic_period=current_period,
                        is_active=True
                    )

                    for group in subject_groups:
                        # Check prerequisites
                        missing_prerequisites = []
                        for prerequisite in study_plan_subject.prerequisites.all():
                            if not SubjectEnrollment.objects.filter(
                                student=student,
                                subject_group__subject=prerequisite,
                                status='completed'
                            ).exists():
                                missing_prerequisites.append({
                                    'code': prerequisite.code,
                                    'name': prerequisite.name
                                })

                        available_subjects.append({
                            'subject_group_id': group.id,
                            'subject_code': group.subject.code,
                            'subject_name': group.subject.name,
                            'group_code': group.code,
                            'credits': group.subject.credits,
                            'max_capacity': group.max_capacity,
                            'current_enrollment': group.current_enrollment,
                            'available_spots': group.max_capacity - group.current_enrollment,
                            'has_capacity': group.has_capacity(),
                            'missing_prerequisites': missing_prerequisites,
                            'can_enroll': len(missing_prerequisites) == 0
                        })

        return Response({
            'student': {
                'id': student.id,
                'name': student.user.get_full_name(),
                'student_id': student.student_id
            },
            'academic_period': {
                'id': current_period.id,
                'name': current_period.name,
                'enrollment_start': current_period.enrollment_start,
                'enrollment_end': current_period.enrollment_end,
                'status': enrollment_status
            },
            'career_enrollments': [{
                'id': ce.id,
                'career_name': ce.career.name,
                'study_plan_name': ce.study_plan.name
            } for ce in career_enrollments],
            'current_enrollments': current_enrollments,
            'available_subjects': available_subjects
        })


class BulkEnrollmentView(views.APIView):
    """
    View for bulk enrollment operations (Admin only)
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request):
        """Bulk enroll students in a subject group"""
        serializer = BulkEnrollmentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        student_ids = serializer.validated_data['student_ids']
        subject_group_id = serializer.validated_data['subject_group_id']
        career_enrollment_check = serializer.validated_data['career_enrollment_check']

        try:
            subject_group = SubjectGroup.objects.get(id=subject_group_id)
        except SubjectGroup.DoesNotExist:
            return Response(
                {'error': 'Grupo de asignatura no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )

        results = {
            'successful': [],
            'failed': [],
            'waiting_list': []
        }

        with transaction.atomic():
            subject_group = SubjectGroup.objects.select_for_update().get(
                id=subject_group_id
            )

            for student_id in student_ids:
                try:
                    student = Student.objects.get(id=student_id, status='active')

                    # Find appropriate career enrollment
                    career_enrollment = None
                    if career_enrollment_check:
                        career_enrollment = CareerEnrollment.objects.filter(
                            student=student,
                            status='active'
                        ).first()

                        if not career_enrollment:
                            results['failed'].append({
                                'student_id': student_id,
                                'reason': 'No career enrollment found'
                            })
                            continue
                    else:
                        career_enrollment = CareerEnrollment.objects.filter(
                            student=student,
                            status='active'
                        ).first()

                    # Check if already enrolled
                    existing_enrollment = SubjectEnrollment.objects.filter(
                        student=student,
                        subject_group=subject_group
                    ).first()

                    if existing_enrollment:
                        if existing_enrollment.status == 'enrolled':
                            results['failed'].append({
                                'student_id': student_id,
                                'reason': 'Already enrolled'
                            })
                            continue
                        else:
                            # Reactivate enrollment
                            existing_enrollment.status = 'enrolled'
                            existing_enrollment.career_enrollment = career_enrollment
                            existing_enrollment.enrollment_date = timezone.now()
                            existing_enrollment.save()

                            subject_group.current_enrollment += 1
                            subject_group.save()

                            results['successful'].append({
                                'student_id': student_id,
                                'enrollment_date': timezone.now()
                            })
                            continue

                    # Check capacity
                    if not subject_group.has_capacity():
                        # Add to waiting list
                        from django.db import models
                        last_position = WaitingList.objects.filter(
                            subject_group=subject_group
                        ).aggregate(models.Max('position'))['position__max'] or 0

                        WaitingList.objects.create(
                            student=student,
                            subject_group=subject_group,
                            position=last_position + 1
                        )

                        results['waiting_list'].append({
                            'student_id': student_id,
                            'position': last_position + 1
                        })
                        continue

                    # Create enrollment
                    SubjectEnrollment.objects.create(
                        student=student,
                        subject_group=subject_group,
                        career_enrollment=career_enrollment
                    )
                    # Note: The model's save() method already increments current_enrollment

                    results['successful'].append({
                        'student_id': student_id,
                        'enrollment_date': timezone.now()
                    })

                except Student.DoesNotExist:
                    results['failed'].append({
                        'student_id': student_id,
                        'reason': 'Student not found'
                    })
                except Exception as e:
                    results['failed'].append({
                        'student_id': student_id,
                        'reason': str(e)
                    })

        return Response(results)
