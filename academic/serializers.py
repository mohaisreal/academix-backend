from rest_framework import serializers
from django.db import transaction
from .models import Career, Subject, AcademicPeriod, StudyPlan, StudyPlanSubject, Classroom
from grades.models import FinalGrade
from enrollment.models import SubjectEnrollment


class CareerSerializer(serializers.ModelSerializer):
    """
    Serializer for Career
    """
    class Meta:
        model = Career
        fields = [
            'id', 'code', 'name', 'description', 'duration_years',
            'total_credits', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class SubjectSerializer(serializers.ModelSerializer):
    """
    Serializer for Subject
    """
    type_display = serializers.CharField(source='get_type_display', read_only=True)

    class Meta:
        model = Subject
        fields = [
            'id', 'code', 'name', 'description', 'credits', 'type', 'type_display',
            'course_year', 'semester', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class AcademicPeriodSerializer(serializers.ModelSerializer):
    """
    Serializer for AcademicPeriod
    """
    class Meta:
        model = AcademicPeriod
        fields = [
            'id', 'name', 'code', 'start_date', 'end_date',
            'enrollment_start', 'enrollment_end', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class StudyPlanSubjectSerializer(serializers.ModelSerializer):
    """
    Serializer for StudyPlanSubject
    """
    subject = SubjectSerializer(read_only=True)
    prerequisites = SubjectSerializer(many=True, read_only=True)

    class Meta:
        model = StudyPlanSubject
        fields = ['id', 'subject', 'prerequisites']


class StudyPlanSerializer(serializers.ModelSerializer):
    """
    Serializer for StudyPlan
    """
    career = CareerSerializer(read_only=True)
    career_id = serializers.IntegerField(write_only=True)
    subjects = StudyPlanSubjectSerializer(many=True, read_only=True)
    total_subjects = serializers.SerializerMethodField()
    total_credits = serializers.SerializerMethodField()

    class Meta:
        model = StudyPlan
        fields = [
            'id', 'career', 'career_id', 'name', 'code', 'start_year', 'end_year',
            'is_active', 'subjects', 'total_subjects', 'total_credits', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_total_subjects(self, obj):
        return obj.subjects.count()

    def get_total_credits(self, obj):
        return sum(sps.subject.credits for sps in obj.subjects.all())

    def validate_career_id(self, value):
        from .models import Career
        try:
            career = Career.objects.get(id=value)
            if not career.is_active:
                raise serializers.ValidationError("No se puede asignar a una carrera inactiva.")
            return value
        except Career.DoesNotExist:
            raise serializers.ValidationError("La carrera especificada no existe.")


class ClassroomSerializer(serializers.ModelSerializer):
    """
    Serializer for Classroom
    """
    class Meta:
        model = Classroom
        fields = ['id', 'code', 'name', 'building', 'floor', 'capacity', 'has_projector', 'has_computers', 'is_active', 'created_at', 'updated_at']


# Academic Report Serializers

class AcademicRecordItemSerializer(serializers.ModelSerializer):
    """Serializer for individual academic record items"""
    subject_code = serializers.CharField(source='subject_group.subject.code', read_only=True)
    subject_name = serializers.CharField(source='subject_group.subject.name', read_only=True)
    credits = serializers.IntegerField(source='subject_group.subject.credits', read_only=True)
    academic_period = serializers.CharField(source='subject_group.academic_period.name', read_only=True)
    final_score = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()

    class Meta:
        model = SubjectEnrollment
        fields = ['id', 'subject_code', 'subject_name', 'credits', 'academic_period', 'final_score', 'status', 'status_display', 'enrollment_date']

    def get_final_score(self, obj):
        try:
            return obj.final_grade.final_score
        except FinalGrade.DoesNotExist:
            return None

    def get_status(self, obj):
        try:
            return obj.final_grade.status
        except FinalGrade.DoesNotExist:
            return 'pending'

    def get_status_display(self, obj):
        try:
            return obj.final_grade.get_status_display()
        except FinalGrade.DoesNotExist:
            return 'Pendiente'


class StudentAcademicRecordSerializer(serializers.Serializer):
    """Serializer for complete student academic record"""
    student_id = serializers.IntegerField()
    student_name = serializers.CharField()
    student_code = serializers.CharField()
    career_name = serializers.CharField()
    enrollments = AcademicRecordItemSerializer(many=True)
    total_credits_attempted = serializers.IntegerField()
    total_credits_earned = serializers.IntegerField()
    gpa = serializers.DecimalField(max_digits=4, decimal_places=2)
    passed_subjects = serializers.IntegerField()
    failed_subjects = serializers.IntegerField()
    pending_subjects = serializers.IntegerField()


class AcademicStatisticsSerializer(serializers.Serializer):
    """Serializer for academic statistics"""
    total_students = serializers.IntegerField()
    total_subjects = serializers.IntegerField()
    total_enrollments = serializers.IntegerField()
    average_gpa = serializers.DecimalField(max_digits=4, decimal_places=2)
    pass_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    fail_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    by_career = serializers.DictField()
    by_period = serializers.DictField()


class SubjectStatisticsSerializer(serializers.Serializer):
    """Serializer for subject-specific statistics"""
    subject_id = serializers.IntegerField()
    subject_code = serializers.CharField()
    subject_name = serializers.CharField()
    total_enrollments = serializers.IntegerField()
    passed_count = serializers.IntegerField()
    failed_count = serializers.IntegerField()
    pending_count = serializers.IntegerField()
    average_grade = serializers.DecimalField(max_digits=4, decimal_places=2)
    pass_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
