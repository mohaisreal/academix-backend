from rest_framework import serializers
from django.db import transaction
from django.core.exceptions import ValidationError as DjangoValidationError
from .models import CareerEnrollment, SubjectGroup, SubjectEnrollment, WaitingList
from users.models import Student
from academic.models import Career, StudyPlan, AcademicPeriod, Subject


class CareerEnrollmentSerializer(serializers.ModelSerializer):
    """
    Serializer for Career Enrollment
    """
    student_name = serializers.CharField(source='student.user.get_full_name', read_only=True)
    student_id = serializers.CharField(source='student.student_id', read_only=True)
    career_name = serializers.CharField(source='career.name', read_only=True)
    career_code = serializers.CharField(source='career.code', read_only=True)
    study_plan_name = serializers.CharField(source='study_plan.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = CareerEnrollment
        fields = [
            'id', 'student', 'student_name', 'student_id', 'career', 'career_name',
            'career_code', 'study_plan', 'study_plan_name', 'enrollment_date',
            'status', 'status_display', 'created_at'
        ]
        read_only_fields = ['enrollment_date', 'created_at']

    def to_representation(self, instance):
        """Return nested objects for career and study_plan in responses"""
        representation = super().to_representation(instance)

        # Convert career from ID to nested object
        if instance.career:
            representation['career'] = {
                'id': instance.career.id,
                'name': instance.career.name,
                'code': instance.career.code
            }

        # Convert study_plan from ID to nested object
        if instance.study_plan:
            representation['study_plan'] = {
                'id': instance.study_plan.id,
                'name': instance.study_plan.name
            }

        return representation

    def validate(self, data):
        student = data.get('student')
        career = data.get('career')
        study_plan = data.get('study_plan')

        # Only validate if all required fields are present (during creation)
        if student and career and study_plan:
            # Check if study plan belongs to career
            if study_plan.career != career:
                raise serializers.ValidationError(
                    "El plan de estudios no pertenece a la carrera seleccionada."
                )

            # Check if student is already enrolled in this career (only for new enrollments)
            if not self.instance:  # Only check on creation, not update
                if CareerEnrollment.objects.filter(
                    student=student,
                    career=career,
                    status='active'
                ).exists():
                    raise serializers.ValidationError(
                        "El estudiante ya está matriculado en esta carrera."
                    )

        return data


class SubjectGroupSerializer(serializers.ModelSerializer):
    """
    Serializer for Subject Group
    """
    subject = serializers.SerializerMethodField()
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    subject_code = serializers.CharField(source='subject.code', read_only=True)
    subject_credits = serializers.IntegerField(source='subject.credits', read_only=True)
    academic_period_name = serializers.CharField(source='academic_period.name', read_only=True)
    available_spots = serializers.SerializerMethodField()
    has_capacity = serializers.SerializerMethodField()
    teacher_name = serializers.SerializerMethodField()
    teacher = serializers.SerializerMethodField()
    group_code = serializers.CharField(source='code', read_only=True)

    class Meta:
        model = SubjectGroup
        fields = [
            'id', 'subject', 'subject_name', 'subject_code', 'subject_credits',
            'academic_period', 'academic_period_name', 'code', 'group_code', 'max_capacity',
            'current_enrollment', 'available_spots', 'has_capacity', 'teacher_name',
            'teacher', 'is_active', 'created_at'
        ]
        read_only_fields = ['current_enrollment', 'created_at']

    def to_representation(self, instance):
        """Return nested objects for academic_period in responses"""
        representation = super().to_representation(instance)

        # Convert academic_period from ID to nested object
        if instance.academic_period:
            representation['academic_period'] = {
                'id': instance.academic_period.id,
                'name': instance.academic_period.name,
                'is_current': instance.academic_period.is_current if hasattr(instance.academic_period, 'is_current') else instance.academic_period.is_active
            }

        return representation

    def get_subject(self, obj):
        """Return subject as an object with code and name"""
        return {
            'id': obj.subject.id,
            'code': obj.subject.code,
            'name': obj.subject.name,
            'credits': obj.subject.credits,
            'course_year': obj.subject.course_year if hasattr(obj.subject, 'course_year') else None,
            'semester': obj.subject.semester if hasattr(obj.subject, 'semester') else None
        }

    def get_available_spots(self, obj):
        return obj.max_capacity - obj.current_enrollment

    def get_has_capacity(self, obj):
        return obj.has_capacity()

    def get_teacher_name(self, obj):
        """Get the main teacher's full name"""
        from schedules.models import TeacherAssignment
        assignment = TeacherAssignment.objects.filter(
            subject_group=obj,
            is_main_teacher=True,
            status='active'
        ).select_related('teacher__user').first()

        if assignment:
            return assignment.teacher.user.get_full_name()
        return None

    def get_teacher(self, obj):
        """Get the main teacher's information"""
        from schedules.models import TeacherAssignment
        assignment = TeacherAssignment.objects.filter(
            subject_group=obj,
            is_main_teacher=True,
            status='active'
        ).select_related('teacher__user').first()

        if assignment:
            return {
                'user': {
                    'first_name': assignment.teacher.user.first_name,
                    'last_name': assignment.teacher.user.last_name
                }
            }
        return None


class SubjectEnrollmentSerializer(serializers.ModelSerializer):
    """
    Serializer for Subject Enrollment
    """
    student_name = serializers.CharField(source='student.user.get_full_name', read_only=True)
    student_id = serializers.CharField(source='student.student_id', read_only=True)
    subject_name = serializers.CharField(source='subject_group.subject.name', read_only=True)
    subject_code = serializers.CharField(source='subject_group.subject.code', read_only=True)
    group_code = serializers.CharField(source='subject_group.code', read_only=True)
    academic_period = serializers.CharField(source='subject_group.academic_period.name', read_only=True)
    credits = serializers.IntegerField(source='subject_group.subject.credits', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    career_enrollment_name = serializers.CharField(source='career_enrollment.career.name', read_only=True)

    class Meta:
        model = SubjectEnrollment
        fields = [
            'id', 'student', 'student_name', 'student_id', 'subject_group',
            'subject_name', 'subject_code', 'group_code', 'academic_period',
            'credits', 'career_enrollment', 'career_enrollment_name',
            'enrollment_date', 'status', 'status_display', 'created_at'
        ]
        read_only_fields = ['enrollment_date', 'created_at']

    def to_representation(self, instance):
        """Return nested objects for subject_group in responses"""
        representation = super().to_representation(instance)

        # Convert subject_group from ID to nested object
        if instance.subject_group:
            from schedules.models import TeacherAssignment

            # Get main teacher assignment
            teacher_assignment = TeacherAssignment.objects.filter(
                subject_group=instance.subject_group,
                is_main_teacher=True,
                status='active'
            ).select_related('teacher__user').first()

            teacher_data = None
            if teacher_assignment:
                teacher_data = {
                    'id': teacher_assignment.teacher.id,
                    'user': {
                        'first_name': teacher_assignment.teacher.user.first_name,
                        'last_name': teacher_assignment.teacher.user.last_name
                    }
                }

            representation['subject_group'] = {
                'id': instance.subject_group.id,
                'code': instance.subject_group.code,
                'group_code': instance.subject_group.code,
                'subject': {
                    'id': instance.subject_group.subject.id,
                    'code': instance.subject_group.subject.code,
                    'name': instance.subject_group.subject.name,
                    'credits': instance.subject_group.subject.credits,
                    'course_year': instance.subject_group.subject.course_year if hasattr(instance.subject_group.subject, 'course_year') else None,
                    'semester': instance.subject_group.subject.semester if hasattr(instance.subject_group.subject, 'semester') else None
                },
                'teacher': teacher_data,
                'academic_period': {
                    'id': instance.subject_group.academic_period.id,
                    'name': instance.subject_group.academic_period.name,
                    'is_current': instance.subject_group.academic_period.is_current if hasattr(instance.subject_group.academic_period, 'is_current') else instance.subject_group.academic_period.is_active
                }
            }

        return representation

    def validate(self, data):
        student = data['student']
        subject_group = data['subject_group']
        career_enrollment = data['career_enrollment']

        # Check if career enrollment belongs to student
        if career_enrollment.student != student:
            raise serializers.ValidationError(
                "La matriculación de carrera no pertenece al estudiante."
            )

        # Check if student is already enrolled in this subject
        if SubjectEnrollment.objects.filter(
            student=student,
            subject_group__subject=subject_group.subject,
            subject_group__academic_period=subject_group.academic_period,
            status='enrolled'
        ).exists():
            raise serializers.ValidationError(
                "El estudiante ya está inscrito en esta asignatura para este período."
            )

        return data

    def create(self, validated_data):
        # Use the model's clean method for additional validation
        enrollment = SubjectEnrollment(**validated_data)
        try:
            enrollment.clean()
        except DjangoValidationError as e:
            raise serializers.ValidationError(str(e))

        return super().create(validated_data)


class EnrollmentRequestSerializer(serializers.Serializer):
    """
    Serializer for enrollment requests
    """
    subject_group_id = serializers.IntegerField()
    career_enrollment_id = serializers.IntegerField()
    force_enroll = serializers.BooleanField(default=False)

    def validate_subject_group_id(self, value):
        try:
            subject_group = SubjectGroup.objects.get(id=value, is_active=True)
            if not subject_group.academic_period.is_active:
                raise serializers.ValidationError(
                    "El período académico no está activo para inscripciones."
                )
            return value
        except SubjectGroup.DoesNotExist:
            raise serializers.ValidationError("Grupo de asignatura no encontrado.")

    def validate_career_enrollment_id(self, value):
        try:
            career_enrollment = CareerEnrollment.objects.get(id=value, status='active')
            return value
        except CareerEnrollment.DoesNotExist:
            raise serializers.ValidationError("Matriculación de carrera no encontrada o inactiva.")


class WaitingListSerializer(serializers.ModelSerializer):
    """
    Serializer for Waiting List
    """
    student_name = serializers.CharField(source='student.user.get_full_name', read_only=True)
    student_id = serializers.CharField(source='student.student_id', read_only=True)
    subject_name = serializers.CharField(source='subject_group.subject.name', read_only=True)
    subject_code = serializers.CharField(source='subject_group.subject.code', read_only=True)
    group_code = serializers.CharField(source='subject_group.code', read_only=True)
    academic_period = serializers.CharField(source='subject_group.academic_period.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = WaitingList
        fields = [
            'id', 'student', 'student_name', 'student_id', 'subject_group',
            'subject_name', 'subject_code', 'group_code', 'academic_period',
            'position', 'status', 'status_display', 'created_at'
        ]
        read_only_fields = ['position', 'created_at']


class EnrollmentSummarySerializer(serializers.Serializer):
    """
    Serializer for enrollment summary
    """
    student_id = serializers.IntegerField()
    student_name = serializers.CharField()
    total_credits = serializers.IntegerField()
    enrolled_subjects = serializers.ListField()
    waiting_subjects = serializers.ListField()
    conflicts = serializers.ListField()
    prerequisites_missing = serializers.ListField()


class BulkEnrollmentSerializer(serializers.Serializer):
    """
    Serializer for bulk enrollment operations
    """
    student_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False
    )
    subject_group_id = serializers.IntegerField()
    career_enrollment_check = serializers.BooleanField(default=True)

    def validate_subject_group_id(self, value):
        try:
            SubjectGroup.objects.get(id=value, is_active=True)
            return value
        except SubjectGroup.DoesNotExist:
            raise serializers.ValidationError("Grupo de asignatura no encontrado.")

    def validate_student_ids(self, value):
        existing_students = Student.objects.filter(
            id__in=value,
            status='active'
        ).values_list('id', flat=True)

        missing_students = set(value) - set(existing_students)
        if missing_students:
            raise serializers.ValidationError(
                f"Estudiantes no encontrados o inactivos: {list(missing_students)}"
            )

        return value