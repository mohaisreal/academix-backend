"""
Schedule Management API Views
Author: Academix Team
"""

import logging
from collections import defaultdict
from django.db.models import Prefetch, Count, Q
from django.utils import timezone
from django.http import HttpResponse
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser

from .models import (
    TimeSlot, Schedule, TeacherAssignment,
    TeacherRole, TeacherRoleAssignment, TeacherAvailability, TeacherPreferences,
    ScheduleConfiguration, ScheduleGeneration, ScheduleSession, BlockedTimeSlot
)
from .serializers import (
    TimeSlotSerializer, ScheduleDetailSerializer, TeacherAssignmentDetailSerializer,
    TeacherRoleSerializer, TeacherRoleAssignmentSerializer,
    TeacherAvailabilitySerializer, TeacherAvailabilityListSerializer,
    TeacherPreferencesSerializer,
    ScheduleConfigurationSerializer,
    ScheduleGenerationListSerializer, ScheduleGenerationDetailSerializer,
    ScheduleGenerationCreateSerializer,
    ScheduleSessionListSerializer, ScheduleSessionDetailSerializer,
    BlockedTimeSlotSerializer, BlockedTimeSlotListSerializer
)
from .services import ScheduleGeneratorService
from .career_coordinator import CareerScheduleCoordinator
from .pdf_generator import SchedulePDFGenerator

logger = logging.getLogger(__name__)


class TimeSlotViewSet(viewsets.ModelViewSet):
    """API ViewSet for TimeSlot management"""
    queryset = TimeSlot.objects.all()
    serializer_class = TimeSlotSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        academic_period_id = self.request.query_params.get('academic_period')
        if academic_period_id:
            queryset = queryset.filter(academic_period_id=academic_period_id)
        return queryset.order_by('day_of_week', 'start_time')


class ScheduleViewSet(viewsets.ModelViewSet):
    """API ViewSet for Schedule management"""
    queryset = Schedule.objects.all()
    serializer_class = ScheduleDetailSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            'subject_group__subject',
            'teacher__user',
            'classroom',
            'time_slot'
        )

        # Filter by academic period
        period_id = self.request.query_params.get('academic_period')
        if period_id:
            queryset = queryset.filter(subject_group__academic_period_id=period_id)

        # Filter by teacher
        teacher_id = self.request.query_params.get('teacher')
        if teacher_id:
            queryset = queryset.filter(teacher_id=teacher_id)

        # Filter by classroom
        classroom_id = self.request.query_params.get('classroom')
        if classroom_id:
            queryset = queryset.filter(classroom_id=classroom_id)

        return queryset.order_by('time_slot__day_of_week', 'time_slot__start_time')

    @action(detail=False, methods=['get'], url_path='my-schedule')
    def my_schedule(self, request):
        """
        Get the schedule for the current user (student or teacher)
        GET /api/schedules/my-schedule/
        """
        user = request.user

        # Try to get teacher
        try:
            from users.models import Teacher
            teacher = Teacher.objects.get(user=user)
            # Return teacher's schedule
            schedules = Schedule.objects.filter(
                teacher=teacher
            ).select_related(
                'subject_group__subject',
                'teacher__user',
                'classroom',
                'time_slot'
            ).order_by('time_slot__day_of_week', 'time_slot__start_time')

            serializer = self.get_serializer(schedules, many=True)
            return Response(serializer.data)
        except Teacher.DoesNotExist:
            pass

        # Try to get student
        try:
            from users.models import Student
            from enrollment.models import SubjectEnrollment

            student = Student.objects.get(user=user)

            # Get enrolled subject groups
            enrollments = SubjectEnrollment.objects.filter(
                student=student,
                status='enrolled'
            ).values_list('subject_group_id', flat=True)

            # Return student's schedule
            schedules = Schedule.objects.filter(
                subject_group_id__in=enrollments
            ).select_related(
                'subject_group__subject',
                'teacher__user',
                'classroom',
                'time_slot'
            ).order_by('time_slot__day_of_week', 'time_slot__start_time')

            serializer = self.get_serializer(schedules, many=True)
            return Response(serializer.data)
        except Student.DoesNotExist:
            pass

        # User is neither teacher nor student
        return Response({
            'error': 'No se encontró información de horario para este usuario'
        }, status=status.HTTP_404_NOT_FOUND)


class TeacherAssignmentViewSet(viewsets.ModelViewSet):
    """API ViewSet for TeacherAssignment management"""
    queryset = TeacherAssignment.objects.all()
    serializer_class = TeacherAssignmentDetailSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            'teacher__user',
            'subject_group__subject',
            'subject_group__academic_period'
        )

        teacher_id = self.request.query_params.get('teacher')
        if teacher_id:
            queryset = queryset.filter(teacher_id=teacher_id)

        period_id = self.request.query_params.get('academic_period')
        if period_id:
            queryset = queryset.filter(subject_group__academic_period_id=period_id)

        return queryset.filter(status='active')


class TeacherRoleViewSet(viewsets.ModelViewSet):
    """API ViewSet for TeacherRole management"""
    queryset = TeacherRole.objects.all()
    serializer_class = TeacherRoleSerializer
    permission_classes = [IsAdminUser]


class TeacherRoleAssignmentViewSet(viewsets.ModelViewSet):
    """API ViewSet for TeacherRoleAssignment management"""
    queryset = TeacherRoleAssignment.objects.all()
    serializer_class = TeacherRoleAssignmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            'teacher__user',
            'role',
            'academic_period'
        )

        teacher_id = self.request.query_params.get('teacher')
        if teacher_id:
            queryset = queryset.filter(teacher_id=teacher_id)

        period_id = self.request.query_params.get('academic_period')
        if period_id:
            queryset = queryset.filter(academic_period_id=period_id)

        return queryset.filter(is_active=True)


class TeacherAvailabilityViewSet(viewsets.ModelViewSet):
    """
    API ViewSet for TeacherAvailability management
    Handles teacher scheduling restrictions and availability
    """
    queryset = TeacherAvailability.objects.all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'list':
            return TeacherAvailabilityListSerializer
        return TeacherAvailabilitySerializer

    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            'teacher__user',
            'academic_period'
        ).prefetch_related('available_time_slots')

        teacher_id = self.request.query_params.get('teacher')
        if teacher_id:
            queryset = queryset.filter(teacher_id=teacher_id)

        period_id = self.request.query_params.get('academic_period')
        if period_id:
            queryset = queryset.filter(academic_period_id=period_id)

        availability_type = self.request.query_params.get('availability_type')
        if availability_type:
            queryset = queryset.filter(availability_type=availability_type)

        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')

        return queryset.order_by('teacher__user__last_name')

    def perform_create(self, serializer):
        """Set the created_by field when creating"""
        # Validate that teacher doesn't have more than 3 restrictions
        teacher_id = serializer.validated_data.get('teacher').id
        academic_period_id = serializer.validated_data.get('academic_period').id

        existing_count = TeacherAvailability.objects.filter(
            teacher_id=teacher_id,
            academic_period_id=academic_period_id
        ).count()

        if existing_count >= 3:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({
                'detail': 'Un profesor no puede tener más de 3 restricciones de disponibilidad por período académico.'
            })

        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=['get'])
    def unavailable_teachers(self, request):
        """
        Get list of teachers marked as unavailable for a specific academic period
        GET /api/schedules/teacher-availability/unavailable_teachers/?academic_period=1
        """
        period_id = request.query_params.get('academic_period')
        if not period_id:
            return Response(
                {'error': 'academic_period parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        unavailable = self.get_queryset().filter(
            academic_period_id=period_id,
            availability_type='unavailable',
            is_active=True
        ).select_related('teacher__user')

        data = [{
            'teacher_id': item.teacher.id,
            'teacher_name': item.teacher.user.get_full_name(),
            'employee_id': item.teacher.employee_id,
            'reason': item.restriction_reason,
            'notes': item.notes
        } for item in unavailable]

        return Response({
            'count': len(data),
            'teachers': data
        })

    @action(detail=False, methods=['get'])
    def restricted_teachers(self, request):
        """
        Get list of teachers with restricted availability for a specific academic period
        GET /api/schedules/teacher-availability/restricted_teachers/?academic_period=1
        """
        period_id = request.query_params.get('academic_period')
        if not period_id:
            return Response(
                {'error': 'academic_period parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        restricted = self.get_queryset().filter(
            academic_period_id=period_id,
            availability_type='restricted',
            is_active=True
        )

        serializer = self.get_serializer(restricted, many=True)
        return Response({
            'count': restricted.count(),
            'teachers': serializer.data
        })

    @action(detail=True, methods=['post'])
    def set_unavailable(self, request, pk=None):
        """
        Mark a teacher as unavailable
        POST /api/schedules/teacher-availability/{id}/set_unavailable/
        Body: {"reason": "Medical leave"}
        """
        availability = self.get_object()
        reason = request.data.get('reason', '')

        availability.availability_type = 'unavailable'
        availability.restriction_reason = reason
        availability.is_active = True
        availability.save()

        serializer = self.get_serializer(availability)
        return Response({
            'message': f'{availability.teacher.user.get_full_name()} marked as unavailable',
            'availability': serializer.data
        })

    @action(detail=True, methods=['post'])
    def restore_availability(self, request, pk=None):
        """
        Restore teacher to full availability
        POST /api/schedules/teacher-availability/{id}/restore_availability/
        """
        availability = self.get_object()

        availability.availability_type = 'full'
        availability.restriction_reason = ''
        availability.is_active = True
        availability.save()

        serializer = self.get_serializer(availability)
        return Response({
            'message': f'{availability.teacher.user.get_full_name()} restored to full availability',
            'availability': serializer.data
        })


class TeacherPreferencesViewSet(viewsets.ModelViewSet):
    """API ViewSet for TeacherPreferences management"""
    queryset = TeacherPreferences.objects.all()
    serializer_class = TeacherPreferencesSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            'teacher__user',
            'academic_period'
        ).prefetch_related('unavailable_time_slots')

        teacher_id = self.request.query_params.get('teacher')
        if teacher_id:
            queryset = queryset.filter(teacher_id=teacher_id)

        period_id = self.request.query_params.get('academic_period')
        if period_id:
            queryset = queryset.filter(academic_period_id=period_id)

        return queryset


class ScheduleConfigurationViewSet(viewsets.ModelViewSet):
    """API ViewSet for ScheduleConfiguration management"""
    queryset = ScheduleConfiguration.objects.all()
    serializer_class = ScheduleConfigurationSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        queryset = super().get_queryset().select_related('academic_period')
        period_id = self.request.query_params.get('academic_period')
        if period_id:
            queryset = queryset.filter(academic_period_id=period_id)
        return queryset


class ScheduleGenerationViewSet(viewsets.ModelViewSet):
    """
    Main API ViewSet for Schedule Generation
    Handles schedule generation, viewing, and management
    """
    queryset = ScheduleGeneration.objects.all()
    permission_classes = [IsAdminUser]

    def get_serializer_class(self):
        if self.action == 'list':
            return ScheduleGenerationListSerializer
        elif self.action == 'create' or self.action == 'generate':
            return ScheduleGenerationCreateSerializer
        return ScheduleGenerationDetailSerializer

    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            'academic_period',
            'configuration',
            'created_by'
        )

        period_id = self.request.query_params.get('academic_period')
        if period_id:
            queryset = queryset.filter(academic_period_id=period_id)

        career_id = self.request.query_params.get('career')
        if career_id:
            queryset = queryset.filter(career_id=career_id)

        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        return queryset.order_by('-started_at')

    @action(detail=False, methods=['post'])
    def generate(self, request):
        """
        Initiate new schedule generation
        POST /api/schedules/generations/generate/
        Body: {
            "academic_period_id": 1,
            "configuration": { ... }
        }
        """
        serializer = ScheduleGenerationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        period_id = serializer.validated_data['academic_period_id']
        config_data = serializer.validated_data.get('configuration', {})

        # Get or create configuration
        config, _ = ScheduleConfiguration.objects.get_or_create(
            academic_period_id=period_id,
            defaults={**config_data} if config_data else {}
        )

        # Execute schedule generation by career (synchronous for now)
        logger.info(f"Starting schedule generation by career for period {period_id}")
        try:
            # Use CareerScheduleCoordinator to generate schedules for all careers
            coordinator = CareerScheduleCoordinator(period_id, config, request.user)
            generations = coordinator.generate_all_careers()

            if not generations:
                return Response({
                    'error': 'No se encontraron carreras para generar horarios',
                    'details': 'No hay carreras activas con asignaturas en este período'
                }, status=status.HTTP_404_NOT_FOUND)

            # Serialize all generations
            response_serializer = ScheduleGenerationListSerializer(generations, many=True)

            return Response({
                'message': f'Generación de horarios completada para {len(generations)} carrera(s)',
                'summary': coordinator.summary,
                'generations': response_serializer.data,
                'overall_success': coordinator.overall_success
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Schedule generation failed: {str(e)}", exc_info=True)
            return Response({
                'error': 'Falló la generación de horarios',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'])
    def preview(self, request, pk=None):
        """
        Get preview of generated schedule with multiple view formats
        GET /api/schedules/generations/{id}/preview/?view_type=grid&filter_type=teacher&entity_id=1
        """
        generation = self.get_object()
        view_type = request.query_params.get('view_type', 'grid')  # grid, list, calendar
        filter_type = request.query_params.get('filter_type')  # teacher, group, classroom
        entity_id = request.query_params.get('entity_id')

        # Get sessions
        sessions = ScheduleSession.objects.filter(
            schedule_generation=generation
        ).select_related(
            'time_slot', 'teacher__user', 'subject_group__subject',
            'classroom', 'teacher_assignment'
        )

        # Apply filters
        if filter_type and entity_id:
            if filter_type == 'teacher':
                sessions = sessions.filter(teacher_id=entity_id)
            elif filter_type == 'group':
                sessions = sessions.filter(subject_group_id=entity_id)
            elif filter_type == 'classroom':
                sessions = sessions.filter(classroom_id=entity_id)

        # Format based on view type
        if view_type == 'grid':
            schedule_data = self._format_grid_view(sessions)
        elif view_type == 'list':
            schedule_data = self._format_list_view(sessions)
        else:
            schedule_data = self._format_grid_view(sessions)

        return Response({
            'generation_id': generation.id,
            'status': generation.status,
            'optimization_score': generation.optimization_score,
            'execution_time': generation.execution_time_seconds,
            'sessions_count': sessions.count(),
            'conflicts': generation.conflicts_detected,
            'warnings': generation.warnings,
            'schedule': schedule_data,
            'statistics': self._calculate_statistics(sessions)
        })

    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        """
        Publish generated schedule (make it the active one)
        POST /api/schedules/generations/{id}/publish/
        """
        generation = self.get_object()

        if generation.status != 'completed':
            return Response(
                {'error': 'Only completed schedules can be published'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Unpublish previous schedules for this period
        ScheduleGeneration.objects.filter(
            academic_period=generation.academic_period,
            is_published=True
        ).update(is_published=False)

        # Publish this one
        generation.is_published = True
        generation.save()

        logger.info(f"Schedule generation {generation.id} published")

        return Response({
            'message': 'Schedule published successfully',
            'generation_id': generation.id,
            'published_at': timezone.now()
        })

    @action(detail=True, methods=['delete'])
    def unpublish(self, request, pk=None):
        """Unpublish a schedule"""
        generation = self.get_object()
        generation.is_published = False
        generation.save()

        return Response({
            'message': 'Schedule unpublished successfully'
        })

    @action(detail=True, methods=['get'])
    def conflicts(self, request, pk=None):
        """Get detailed conflicts and warnings"""
        generation = self.get_object()
        return Response({
            'conflicts': generation.conflicts_detected,
            'warnings': generation.warnings,
            'conflict_count': len(generation.conflicts_detected),
            'warning_count': len(generation.warnings)
        })

    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        """Get detailed statistics about the generated schedule"""
        generation = self.get_object()
        sessions = ScheduleSession.objects.filter(schedule_generation=generation)

        stats = self._calculate_statistics(sessions)

        return Response(stats)

    @action(detail=True, methods=['get'])
    def export_pdf(self, request, pk=None):
        """
        Export schedule generation as PDF
        GET /api/schedules/generations/{id}/export_pdf/
        """
        generation = self.get_object()

        if generation.status != 'completed':
            return Response(
                {'error': 'Only completed schedules can be exported as PDF'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Generate PDF
            pdf_generator = SchedulePDFGenerator(generation.id)
            pdf_buffer = pdf_generator.generate()

            # Prepare response
            filename = f"horario_{generation.academic_period.code}_{generation.id}.pdf"
            response = HttpResponse(pdf_buffer, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'

            logger.info(f"PDF generated for schedule generation {generation.id}")

            return response

        except Exception as e:
            logger.error(f"PDF generation failed: {str(e)}", exc_info=True)
            return Response({
                'error': 'Failed to generate PDF',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['delete'], url_path='batch/(?P<batch_id>[^/.]+)')
    def delete_batch(self, request, batch_id=None):
        """
        Delete all generations in a batch
        DELETE /api/schedules/generations/batch/{batch_id}/
        """
        try:
            # Find all generations with this batch_id
            generations = ScheduleGeneration.objects.filter(batch_id=batch_id)

            if not generations.exists():
                return Response({
                    'error': 'No generations found for this batch'
                }, status=status.HTTP_404_NOT_FOUND)

            # Count generations to delete
            count = generations.count()

            # Delete all sessions first
            for gen in generations:
                ScheduleSession.objects.filter(schedule_generation=gen).delete()

            # Delete generations
            generations.delete()

            logger.info(f"Deleted {count} generations from batch {batch_id}")

            return Response({
                'message': f'Successfully deleted {count} generation(s)',
                'deleted_count': count,
                'batch_id': batch_id
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Failed to delete batch {batch_id}: {str(e)}", exc_info=True)
            return Response({
                'error': 'Failed to delete batch',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _format_grid_view(self, sessions):
        """Format sessions as a grid (weekly timetable)"""
        DAYS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']

        # Get unique time slots
        time_slots_qs = TimeSlot.objects.filter(
            id__in=sessions.values_list('time_slot_id', flat=True)
        ).order_by('start_time').distinct('start_time')

        # Structure: {day: {time: [sessions]}}
        grid = defaultdict(lambda: defaultdict(list))

        for session in sessions:
            day = session.time_slot.day_of_week
            time_key = session.time_slot.start_time.strftime('%H:%M')

            # Get career codes for this subject
            from academic.models import StudyPlanSubject
            study_plans = StudyPlanSubject.objects.filter(
                subject=session.subject_group.subject
            ).select_related('study_plan__career')
            career_codes = [sp.study_plan.career.code for sp in study_plans]

            grid[day][time_key].append({
                'id': session.id,
                'subject': {
                    'id': session.subject_group.subject.id,
                    'name': session.subject_group.subject.name,
                    'code': session.subject_group.subject.code,
                    'year': session.subject_group.subject.course_year
                },
                'teacher': {
                    'id': session.teacher.id,
                    'name': session.teacher.user.get_full_name(),
                    'department': session.teacher.department
                },
                'group': {
                    'id': session.subject_group.id,
                    'code': session.subject_group.code
                },
                'classroom': {
                    'id': session.classroom.id,
                    'code': session.classroom.code,
                    'name': session.classroom.name,
                    'building': session.classroom.building
                },
                'time': {
                    'start': session.time_slot.start_time.strftime('%H:%M'),
                    'end': session.time_slot.end_time.strftime('%H:%M'),
                    'duration_minutes': session.time_slot.duration_minutes
                },
                'duration_slots': session.duration_slots,
                'session_type': session.session_type,
                'is_locked': session.is_locked,
                'career_codes': career_codes
            })

        # Get unique time strings for the grid
        unique_times = sorted(set(
            session.time_slot.start_time.strftime('%H:%M')
            for session in sessions
        ))

        return {
            'type': 'grid',
            'days': DAYS[:max(grid.keys()) + 1] if grid else DAYS[:5],
            'time_slots': [
                {'time': time_str, 'code': time_str.replace(':', '')}
                for time_str in unique_times
            ],
            'data': dict(grid)
        }

    def _format_list_view(self, sessions):
        """Format sessions as a simple list"""
        sessions_list = []

        for session in sessions.order_by('time_slot__day_of_week', 'time_slot__start_time'):
            sessions_list.append({
                'id': session.id,
                'day': session.time_slot.get_day_of_week_display(),
                'day_number': session.time_slot.day_of_week,
                'time_start': session.time_slot.start_time.strftime('%H:%M'),
                'time_end': session.time_slot.end_time.strftime('%H:%M'),
                'subject': session.subject_group.subject.name,
                'subject_code': session.subject_group.subject.code,
                'teacher': session.teacher.user.get_full_name(),
                'group': session.subject_group.code,
                'classroom': session.classroom.code,
                'classroom_name': session.classroom.name,
                'building': session.classroom.building,
                'duration': session.duration_slots,
                'type': session.get_session_type_display()
            })

        return {
            'type': 'list',
            'sessions': sessions_list,
            'total': len(sessions_list)
        }

    def _calculate_statistics(self, sessions):
        """Calculate various statistics about the schedule"""
        if not sessions.exists():
            return {}

        # Basic counts
        total_sessions = sessions.count()

        # Sessions by day
        by_day = {}
        for day in range(7):
            count = sessions.filter(time_slot__day_of_week=day).count()
            if count > 0:
                by_day[day] = {
                    'name': TimeSlot.WEEKDAY_CHOICES[day][1],
                    'count': count
                }

        # Sessions by type
        by_type = {}
        for session_type, display in ScheduleSession.SESSION_TYPE_CHOICES:
            count = sessions.filter(session_type=session_type).count()
            if count > 0:
                by_type[session_type] = {
                    'name': display,
                    'count': count
                }

        # Unique counts
        teachers_count = sessions.values('teacher').distinct().count()
        groups_count = sessions.values('subject_group').distinct().count()
        classrooms_count = sessions.values('classroom').distinct().count()

        return {
            'total_sessions': total_sessions,
            'by_day': by_day,
            'by_type': by_type,
            'unique_teachers': teachers_count,
            'unique_groups': groups_count,
            'unique_classrooms': classrooms_count
        }


class ScheduleSessionViewSet(viewsets.ModelViewSet):
    """API ViewSet for ScheduleSession management"""
    queryset = ScheduleSession.objects.all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'list':
            return ScheduleSessionListSerializer
        return ScheduleSessionDetailSerializer

    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            'schedule_generation',
            'teacher_assignment',
            'subject_group__subject',
            'teacher__user',
            'time_slot',
            'classroom'
        )

        # Filter by generation
        generation_id = self.request.query_params.get('generation')
        if generation_id:
            queryset = queryset.filter(schedule_generation_id=generation_id)

        # Filter by teacher
        teacher_id = self.request.query_params.get('teacher')
        if teacher_id:
            queryset = queryset.filter(teacher_id=teacher_id)

        # Filter by classroom
        classroom_id = self.request.query_params.get('classroom')
        if classroom_id:
            queryset = queryset.filter(classroom_id=classroom_id)

        # Filter by day
        day = self.request.query_params.get('day')
        if day is not None:
            queryset = queryset.filter(time_slot__day_of_week=day)

        return queryset.order_by('time_slot__day_of_week', 'time_slot__start_time')


class BlockedTimeSlotViewSet(viewsets.ModelViewSet):
    """API ViewSet for BlockedTimeSlot management"""
    queryset = BlockedTimeSlot.objects.all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'list':
            return BlockedTimeSlotListSerializer
        return BlockedTimeSlotSerializer

    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            'academic_period',
            'time_slot',
            'career',
            'classroom',
            'created_by'
        )

        # Filter by academic period
        academic_period_id = self.request.query_params.get('academic_period')
        if academic_period_id:
            queryset = queryset.filter(academic_period_id=academic_period_id)

        # Filter by block type
        block_type = self.request.query_params.get('block_type')
        if block_type:
            queryset = queryset.filter(block_type=block_type)

        # Filter by career
        career_id = self.request.query_params.get('career')
        if career_id:
            queryset = queryset.filter(career_id=career_id)

        # Filter by classroom
        classroom_id = self.request.query_params.get('classroom')
        if classroom_id:
            queryset = queryset.filter(classroom_id=classroom_id)

        # Filter by active status
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')

        return queryset.order_by('time_slot__day_of_week', 'time_slot__start_time')

    def perform_create(self, serializer):
        """Set the created_by field to the current user"""
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=['get'], url_path='statistics')
    def statistics(self, request):
        """
        Get statistics about blocked time slots
        GET /api/schedules/blocked-time-slots/statistics/
        """
        academic_period_id = request.query_params.get('academic_period')
        queryset = self.get_queryset()

        if academic_period_id:
            queryset = queryset.filter(academic_period_id=academic_period_id)

        # Count by block type
        by_type = defaultdict(int)
        for blocked in queryset:
            by_type[blocked.get_block_type_display()] += 1

        # Count by day
        by_day = defaultdict(int)
        for blocked in queryset:
            day_name = blocked.time_slot.get_day_of_week_display()
            by_day[day_name] += 1

        # Count active vs inactive
        active_count = queryset.filter(is_active=True).count()
        inactive_count = queryset.filter(is_active=False).count()

        return Response({
            'total': queryset.count(),
            'active': active_count,
            'inactive': inactive_count,
            'by_type': dict(by_type),
            'by_day': dict(by_day)
        })
