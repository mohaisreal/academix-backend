from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import (
    Schedule, TeacherAssignment, TimeSlot,
    TeacherRole, TeacherRoleAssignment, TeacherAvailability, TeacherPreferences,
    ScheduleConfiguration, ScheduleGeneration, ScheduleSession, BlockedTimeSlot
)
from academic.serializers import SubjectSerializer, AcademicPeriodSerializer, ClassroomSerializer
from enrollment.models import SubjectGroup
from users.models import Teacher

User = get_user_model()


class ScheduleDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for Schedule with detailed classroom information
    """
    day_of_week = serializers.SerializerMethodField()
    start_time = serializers.SerializerMethodField()
    end_time = serializers.SerializerMethodField()
    classroom = serializers.SerializerMethodField()
    subject_group = serializers.SerializerMethodField()

    class Meta:
        model = Schedule
        fields = ['id', 'day_of_week', 'start_time', 'end_time', 'classroom', 'subject_group']

    def get_day_of_week(self, obj):
        return obj.time_slot.day_of_week

    def get_start_time(self, obj):
        return obj.time_slot.start_time.strftime('%H:%M:%S')

    def get_end_time(self, obj):
        return obj.time_slot.end_time.strftime('%H:%M:%S')

    def get_classroom(self, obj):
        return {
            'code': obj.classroom.code,
            'building': obj.classroom.building
        }

    def get_subject_group(self, obj):
        return {
            'id': obj.subject_group.id,
            'subject': {
                'code': obj.subject_group.subject.code,
                'name': obj.subject_group.subject.name,
            },
            'group_code': obj.subject_group.code,
            'teacher': {
                'user': {
                    'first_name': obj.teacher.user.first_name,
                    'last_name': obj.teacher.user.last_name,
                }
            }
        }


class SubjectGroupDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for SubjectGroup with nested subject and academic period
    """
    subject = SubjectSerializer(read_only=True)
    academic_period = serializers.SerializerMethodField()
    group_code = serializers.CharField(source='code', read_only=True)

    class Meta:
        model = SubjectGroup
        fields = [
            'id', 'subject', 'group_code', 'max_capacity',
            'current_enrollment', 'academic_period'
        ]

    def get_academic_period(self, obj):
        from datetime import date
        today = date.today()
        is_current = (
            obj.academic_period.start_date <= today <= obj.academic_period.end_date
            if obj.academic_period.start_date and obj.academic_period.end_date
            else False
        )
        return {
            'name': obj.academic_period.name,
            'is_current': is_current
        }


class TeacherAssignmentDetailSerializer(serializers.ModelSerializer):
    """
    Complete serializer for TeacherAssignment with all nested data
    """
    subject_group = SubjectGroupDetailSerializer(read_only=True)
    schedules = serializers.SerializerMethodField()

    class Meta:
        model = TeacherAssignment
        fields = ['id', 'subject_group', 'schedules']

    def get_schedules(self, obj):
        schedules = Schedule.objects.filter(
            subject_group=obj.subject_group,
            is_active=True
        ).select_related('classroom', 'time_slot')

        return [{
            'id': schedule.id,
            'day_of_week': schedule.time_slot.day_of_week,
            'start_time': schedule.time_slot.start_time.strftime('%H:%M:%S'),
            'end_time': schedule.time_slot.end_time.strftime('%H:%M:%S'),
            'classroom': {
                'code': schedule.classroom.code,
                'building': schedule.classroom.building
            }
        } for schedule in schedules]


# ===== NEW SERIALIZERS FOR SCHEDULE GENERATION SYSTEM =====

class TimeSlotSerializer(serializers.ModelSerializer):
    """Serializer for TimeSlot model"""
    day_name = serializers.CharField(source='get_day_of_week_display', read_only=True)

    class Meta:
        model = TimeSlot
        fields = [
            'id', 'academic_period', 'day_of_week', 'day_name',
            'start_time', 'end_time', 'duration_minutes',
            'slot_code', 'is_active'
        ]
        read_only_fields = ['duration_minutes', 'slot_code']


class TeacherRoleSerializer(serializers.ModelSerializer):
    """Serializer for TeacherRole model"""
    class Meta:
        model = TeacherRole
        fields = [
            'id', 'name', 'required_free_hours_per_week',
            'priority', 'description', 'icon'
        ]


class TeacherRoleAssignmentSerializer(serializers.ModelSerializer):
    """Serializer for TeacherRoleAssignment model"""
    role = TeacherRoleSerializer(read_only=True)
    teacher_name = serializers.CharField(source='teacher.user.get_full_name', read_only=True)
    total_free_hours = serializers.IntegerField(source='get_total_free_hours', read_only=True)

    class Meta:
        model = TeacherRoleAssignment
        fields = [
            'id', 'teacher', 'teacher_name', 'role',
            'academic_period', 'additional_free_hours',
            'total_free_hours', 'is_active'
        ]


class TeacherAvailabilitySerializer(serializers.ModelSerializer):
    """Serializer for TeacherAvailability model"""
    teacher_name = serializers.CharField(source='teacher.user.get_full_name', read_only=True)
    teacher_id_number = serializers.CharField(source='teacher.employee_id', read_only=True)
    availability_type_display = serializers.CharField(source='get_availability_type_display', read_only=True)
    available_slots = TimeSlotSerializer(source='available_time_slots', many=True, read_only=True)
    available_hours = serializers.IntegerField(source='get_available_hours', read_only=True)
    academic_period_name = serializers.CharField(source='academic_period.name', read_only=True)

    class Meta:
        model = TeacherAvailability
        fields = [
            'id', 'teacher', 'teacher_name', 'teacher_id_number',
            'academic_period', 'academic_period_name',
            'availability_type', 'availability_type_display',
            'max_teaching_hours', 'available_hours',
            'available_time_slots', 'available_slots',
            'blocked_days', 'restriction_reason', 'notes',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class TeacherAvailabilityListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing teacher availability"""
    teacher_name = serializers.CharField(source='teacher.user.get_full_name', read_only=True)
    teacher_id_number = serializers.CharField(source='teacher.employee_id', read_only=True)
    availability_type_display = serializers.CharField(source='get_availability_type_display', read_only=True)
    available_hours = serializers.IntegerField(source='get_available_hours', read_only=True)

    class Meta:
        model = TeacherAvailability
        fields = [
            'id', 'teacher', 'teacher_name', 'teacher_id_number',
            'availability_type', 'availability_type_display',
            'max_teaching_hours', 'available_hours',
            'restriction_reason', 'is_active'
        ]


class TeacherPreferencesSerializer(serializers.ModelSerializer):
    """Serializer for TeacherPreferences model"""
    teacher_name = serializers.CharField(source='teacher.user.get_full_name', read_only=True)
    unavailable_slots = TimeSlotSerializer(source='unavailable_time_slots', many=True, read_only=True)

    class Meta:
        model = TeacherPreferences
        fields = [
            'id', 'teacher', 'teacher_name', 'academic_period',
            'max_hours_per_week', 'max_consecutive_hours', 'max_daily_hours',
            'preferred_days', 'unavailable_time_slots', 'unavailable_slots',
            'preferred_start_time', 'preferred_end_time', 'color_code'
        ]


class ScheduleConfigurationSerializer(serializers.ModelSerializer):
    """Serializer for ScheduleConfiguration model"""
    algorithm_display = serializers.CharField(source='get_algorithm_display', read_only=True)
    priority_display = serializers.CharField(source='get_optimization_priority_display', read_only=True)

    class Meta:
        model = ScheduleConfiguration
        fields = [
            'id', 'academic_period', 'algorithm', 'algorithm_display',
            'max_execution_time_seconds', 'optimization_priority', 'priority_display',
            'allow_teacher_gaps', 'max_daily_hours_per_teacher',
            'max_daily_hours_per_group', 'max_classes_per_day',
            'max_sessions_per_subject_per_day', 'min_break_between_classes',
            'weight_minimize_teacher_gaps', 'weight_teacher_preferences',
            'weight_balanced_distribution', 'weight_classroom_proximity',
            'weight_minimize_daily_changes'
        ]


class ScheduleSessionListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing schedule sessions"""
    subject_name = serializers.CharField(source='subject_group.subject.name', read_only=True)
    subject_code = serializers.CharField(source='subject_group.subject.code', read_only=True)
    subject_year = serializers.IntegerField(source='subject_group.subject.course_year', read_only=True)
    group_code = serializers.CharField(source='subject_group.code', read_only=True)
    teacher_name = serializers.CharField(source='teacher.user.get_full_name', read_only=True)
    classroom_code = serializers.CharField(source='classroom.code', read_only=True)
    day_of_week = serializers.IntegerField(source='time_slot.day_of_week', read_only=True)
    day_name = serializers.CharField(source='time_slot.get_day_of_week_display', read_only=True)
    start_time = serializers.TimeField(source='time_slot.start_time', read_only=True)
    end_time = serializers.TimeField(source='time_slot.end_time', read_only=True)
    career_codes = serializers.SerializerMethodField()

    class Meta:
        model = ScheduleSession
        fields = [
            'id', 'subject_name', 'subject_code', 'subject_year', 'group_code',
            'teacher_name', 'classroom_code', 'day_of_week', 'day_name',
            'start_time', 'end_time', 'duration_slots',
            'session_type', 'is_locked', 'career_codes'
        ]

    def get_career_codes(self, obj):
        """Get all career codes that include this subject"""
        from academic.models import StudyPlanSubject
        study_plans = StudyPlanSubject.objects.filter(
            subject=obj.subject_group.subject
        ).select_related('study_plan__career')
        return [sp.study_plan.career.code for sp in study_plans]


class ScheduleSessionDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for schedule sessions"""
    subject_group = SubjectGroupDetailSerializer(read_only=True)
    teacher = serializers.SerializerMethodField()
    time_slot = TimeSlotSerializer(read_only=True)
    classroom = ClassroomSerializer(read_only=True)
    session_type_display = serializers.CharField(source='get_session_type_display', read_only=True)

    class Meta:
        model = ScheduleSession
        fields = [
            'id', 'schedule_generation', 'teacher_assignment',
            'subject_group', 'teacher', 'time_slot', 'classroom',
            'duration_slots', 'session_type', 'session_type_display',
            'is_locked', 'notes', 'created_at', 'updated_at'
        ]

    def get_teacher(self, obj):
        return {
            'id': obj.teacher.id,
            'name': obj.teacher.user.get_full_name(),
            'employee_id': obj.teacher.employee_id,
            'department': obj.teacher.department
        }


class ScheduleGenerationListSerializer(serializers.ModelSerializer):
    """Serializer for listing schedule generations"""
    academic_period_name = serializers.CharField(source='academic_period.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    algorithm_display = serializers.CharField(source='get_algorithm_used_display', read_only=True)

    career_name = serializers.CharField(source='career.name', read_only=True)
    career_code = serializers.CharField(source='career.code', read_only=True)

    class Meta:
        model = ScheduleGeneration
        fields = [
            'id', 'batch_id', 'academic_period', 'academic_period_name',
            'career', 'career_name', 'career_code',
            'status', 'status_display', 'started_at', 'completed_at',
            'execution_time_seconds', 'total_sessions_to_schedule',
            'sessions_scheduled', 'success_rate', 'optimization_score',
            'algorithm_used', 'algorithm_display', 'is_published',
            'created_by_name'
        ]


class ScheduleGenerationDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for schedule generation with full information"""
    academic_period = AcademicPeriodSerializer(read_only=True)
    configuration = ScheduleConfigurationSerializer(read_only=True)
    sessions = ScheduleSessionListSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    conflicts_formatted = serializers.SerializerMethodField()

    def get_conflicts_formatted(self, obj):
        """Retorna los conflictos en formato legible"""
        if not obj.conflicts_detected:
            return None

        from .services import ScheduleGeneratorService
        return ScheduleGeneratorService.format_conflicts_list(obj.conflicts_detected)

    career_info = serializers.SerializerMethodField()

    def get_career_info(self, obj):
        """Retorna información de la carrera"""
        if obj.career:
            return {
                'id': obj.career.id,
                'code': obj.career.code,
                'name': obj.career.name
            }
        return None

    class Meta:
        model = ScheduleGeneration
        fields = [
            'id', 'academic_period', 'career', 'career_info',
            'configuration', 'status', 'status_display',
            'started_at', 'completed_at', 'execution_time_seconds',
            'total_sessions_to_schedule', 'sessions_scheduled', 'success_rate',
            'conflicts_detected', 'conflicts_formatted', 'warnings', 'optimization_score',
            'algorithm_used', 'algorithm_parameters',
            'created_by', 'created_by_name', 'is_published',
            'sessions', 'notes'
        ]


class ScheduleGenerationCreateSerializer(serializers.Serializer):
    """Serializer for initiating schedule generation"""
    academic_period_id = serializers.IntegerField(required=True)
    configuration = ScheduleConfigurationSerializer(required=False)

    def validate_academic_period_id(self, value):
        from academic.models import AcademicPeriod
        if not AcademicPeriod.objects.filter(id=value).exists():
            raise serializers.ValidationError("Academic period not found")
        return value


class BlockedTimeSlotSerializer(serializers.ModelSerializer):
    """Serializer for BlockedTimeSlot model"""
    time_slot_display = serializers.SerializerMethodField()
    block_type_display = serializers.CharField(source='get_block_type_display', read_only=True)
    career_name = serializers.CharField(source='career.name', read_only=True, allow_null=True)
    classroom_code = serializers.CharField(source='classroom.code', read_only=True, allow_null=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True, allow_null=True)
    academic_period_name = serializers.CharField(source='academic_period.name', read_only=True)

    class Meta:
        model = BlockedTimeSlot
        fields = [
            'id', 'academic_period', 'academic_period_name',
            'time_slot', 'time_slot_display',
            'block_type', 'block_type_display',
            'career', 'career_name',
            'classroom', 'classroom_code',
            'reason', 'notes', 'is_active',
            'created_at', 'updated_at', 'created_by', 'created_by_name'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by']

    def get_time_slot_display(self, obj):
        """Return formatted time slot information"""
        return {
            'id': obj.time_slot.id,
            'day_of_week': obj.time_slot.day_of_week,
            'day_name': obj.time_slot.get_day_of_week_display(),
            'start_time': obj.time_slot.start_time.strftime('%H:%M'),
            'end_time': obj.time_slot.end_time.strftime('%H:%M'),
            'slot_code': obj.time_slot.slot_code
        }

    def validate(self, data):
        """Validate blocked time slot data"""
        block_type = data.get('block_type')
        career = data.get('career')
        classroom = data.get('classroom')

        # Validate career-specific blocks
        if block_type == 'career' and not career:
            raise serializers.ValidationError({
                'career': 'Debe especificar una carrera cuando el tipo de bloqueo es "career"'
            })

        # Validate classroom-specific blocks
        if block_type == 'classroom' and not classroom:
            raise serializers.ValidationError({
                'classroom': 'Debe especificar un aula cuando el tipo de bloqueo es "classroom"'
            })

        # Ensure career is not set for non-career blocks
        if block_type != 'career' and career:
            raise serializers.ValidationError({
                'career': 'No debe especificar una carrera para bloqueos que no son por carrera'
            })

        # Ensure classroom is not set for non-classroom blocks
        if block_type != 'classroom' and classroom:
            raise serializers.ValidationError({
                'classroom': 'No debe especificar un aula para bloqueos que no son por aula'
            })

        return data


class BlockedTimeSlotListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing blocked time slots"""
    time_slot_display = serializers.SerializerMethodField()
    block_type_display = serializers.CharField(source='get_block_type_display', read_only=True)
    career_name = serializers.CharField(source='career.name', read_only=True, allow_null=True)
    classroom_code = serializers.CharField(source='classroom.code', read_only=True, allow_null=True)

    class Meta:
        model = BlockedTimeSlot
        fields = [
            'id', 'time_slot', 'time_slot_display',
            'block_type', 'block_type_display',
            'career', 'career_name',
            'classroom', 'classroom_code',
            'reason', 'is_active'
        ]

    def get_time_slot_display(self, obj):
        """Return formatted time slot information"""
        return {
            'id': obj.time_slot.id,
            'day_of_week': obj.time_slot.day_of_week,
            'day_name': obj.time_slot.get_day_of_week_display(),
            'start_time': obj.time_slot.start_time.strftime('%H:%M'),
            'end_time': obj.time_slot.end_time.strftime('%H:%M'),
            'slot_code': obj.time_slot.slot_code
        }
