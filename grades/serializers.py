from rest_framework import serializers
from decimal import Decimal
from django.db.models import Avg, Sum, Count, Q
from django.utils import timezone

from .models import (
    GradingCategory,
    Assignment,
    Submission,
    Grade,
    FinalGradeConfig,
    FinalGrade,
    GradeReport,
    CourseMaterial,
    Quiz,
    Question,
    QuestionOption,
    QuizAttempt,
    QuizAnswer,
)
from users.models import Student, Teacher
from enrollment.models import SubjectGroup, SubjectEnrollment


# ==================== BASIC SERIALIZERS ====================

class StudentBasicSerializer(serializers.ModelSerializer):
    """Serializer básico para estudiantes"""
    user_full_name = serializers.CharField(source='user.get_full_name', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = Student
        fields = ['id', 'student_code', 'user_full_name', 'user_email']


class TeacherBasicSerializer(serializers.ModelSerializer):
    """Serializer básico para profesores"""
    user_full_name = serializers.CharField(source='user.get_full_name', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = Teacher
        fields = ['id', 'employee_number', 'user_full_name', 'user_email']


class SubjectGroupBasicSerializer(serializers.ModelSerializer):
    """Serializer básico para grupos de materia"""
    subject_code = serializers.CharField(source='subject.code', read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    teacher_name = serializers.CharField(source='teacher.user.get_full_name', read_only=True)

    class Meta:
        model = SubjectGroup
        fields = ['id', 'subject_code', 'subject_name', 'group_code', 'teacher_name']


# ==================== MAIN SERIALIZERS ====================

class GradingCategorySerializer(serializers.ModelSerializer):
    """
    Serializer para categorías de ponderación
    """
    assignments_count = serializers.SerializerMethodField()
    subject_name = serializers.CharField(source='subject_group.subject.name', read_only=True)

    class Meta:
        model = GradingCategory
        fields = [
            'id', 'subject_group', 'subject_name', 'name', 'weight',
            'description', 'order', 'assignments_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_assignments_count(self, obj):
        """Número de assignments en esta categoría"""
        return obj.assignments.filter(published_at__isnull=False).count()

    def validate(self, data):
        """Validar que el peso total no exceda 100%"""
        subject_group = data.get('subject_group')
        weight = data.get('weight')

        # Obtener peso total actual (excluyendo esta categoría si es update)
        existing_categories = GradingCategory.objects.filter(subject_group=subject_group)
        if self.instance:
            existing_categories = existing_categories.exclude(pk=self.instance.pk)

        total_weight = existing_categories.aggregate(total=Sum('weight'))['total'] or Decimal('0')

        if total_weight + weight > 100:
            raise serializers.ValidationError({
                'weight': f'El peso total no puede exceder 100%. Peso actual: {total_weight}%'
            })

        return data


class AssignmentListSerializer(serializers.ModelSerializer):
    """
    Serializer simplificado para listados de assignments
    """
    subject_name = serializers.CharField(source='subject_group.subject.name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True, allow_null=True)
    created_by_name = serializers.CharField(source='created_by.user.get_full_name', read_only=True)

    # Campos calculados
    submissions_count = serializers.SerializerMethodField()
    graded_count = serializers.SerializerMethodField()
    is_overdue = serializers.SerializerMethodField()
    is_published = serializers.SerializerMethodField()

    class Meta:
        model = Assignment
        fields = [
            'id', 'subject_group', 'subject_name', 'category', 'category_name',
            'title', 'assignment_type', 'max_score', 'start_date', 'due_date',
            'published_at', 'scope', 'created_by_name',
            'submissions_count', 'graded_count', 'is_overdue', 'is_published',
            'created_at'
        ]

    def get_submissions_count(self, obj):
        """Número de entregas"""
        return obj.submissions.exclude(status='draft').count()

    def get_graded_count(self, obj):
        """Número de entregas calificadas"""
        return obj.grades.filter(score__isnull=False).count()

    def get_is_overdue(self, obj):
        """Si el assignment está vencido"""
        return obj.is_overdue()

    def get_is_published(self, obj):
        """Si el assignment está publicado"""
        return obj.is_published()


class AssignmentDetailSerializer(serializers.ModelSerializer):
    """
    Serializer completo para detalle de assignment
    """
    subject_name = serializers.CharField(source='subject_group.subject.name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True, allow_null=True)
    created_by_name = serializers.CharField(source='created_by.user.get_full_name', read_only=True)
    attachment_url = serializers.SerializerMethodField()

    # Estadísticas
    total_assigned = serializers.SerializerMethodField()
    pending_count = serializers.SerializerMethodField()
    submitted_count = serializers.SerializerMethodField()
    graded_count = serializers.SerializerMethodField()
    average_score = serializers.SerializerMethodField()

    # Estado
    is_overdue = serializers.SerializerMethodField()
    is_published = serializers.SerializerMethodField()

    class Meta:
        model = Assignment
        fields = [
            'id', 'subject_group', 'subject_name', 'category', 'category_name',
            'title', 'description', 'instructions', 'assignment_type',
            'max_score', 'start_date', 'due_date', 'published_at',
            'scope', 'assigned_students', 'allow_late_submission', 'late_penalty_percent',
            'attachment', 'attachment_url', 'created_by', 'created_by_name',
            'total_assigned', 'pending_count', 'submitted_count', 'graded_count',
            'average_score', 'is_overdue', 'is_published',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at']

    def get_attachment_url(self, obj):
        """URL del archivo adjunto"""
        if obj.attachment:
            return obj.attachment.url
        return None

    def get_total_assigned(self, obj):
        """Total de estudiantes asignados"""
        if obj.scope == 'all':
            return obj.subject_group.enrollments.filter(status='enrolled').count()
        return obj.assigned_students.count()

    def get_pending_count(self, obj):
        """Entregas pendientes"""
        total = self.get_total_assigned(obj)
        submitted = obj.submissions.exclude(status='draft').count()
        return total - submitted

    def get_submitted_count(self, obj):
        """Entregas realizadas"""
        return obj.submissions.exclude(status='draft').count()

    def get_graded_count(self, obj):
        """Entregas calificadas"""
        return obj.grades.filter(score__isnull=False).count()

    def get_average_score(self, obj):
        """Promedio de calificaciones"""
        avg = obj.grades.filter(score__isnull=False).aggregate(avg=Avg('score'))['avg']
        return float(avg) if avg else None

    def get_is_overdue(self, obj):
        return obj.is_overdue()

    def get_is_published(self, obj):
        return obj.is_published()

    def create(self, validated_data):
        """Agregar created_by automáticamente"""
        request = self.context.get('request')
        if request and hasattr(request.user, 'teacher_profile'):
            validated_data['created_by'] = request.user.teacher_profile
        return super().create(validated_data)

    def validate(self, data):
        """Validaciones del assignment"""
        start_date = data.get('start_date')
        due_date = data.get('due_date')

        if start_date and due_date and start_date > due_date:
            raise serializers.ValidationError({
                'start_date': 'La fecha de inicio no puede ser posterior a la fecha límite'
            })

        return data


class SubmissionSerializer(serializers.ModelSerializer):
    """
    Serializer para entregas de estudiantes
    """
    student_name = serializers.CharField(source='student.user.get_full_name', read_only=True)
    assignment_title = serializers.CharField(source='assignment.title', read_only=True)
    submission_file_url = serializers.SerializerMethodField()

    # Calificación asociada
    grade_score = serializers.SerializerMethodField()
    grade_feedback = serializers.SerializerMethodField()
    grade_feedback_file_url = serializers.SerializerMethodField()

    class Meta:
        model = Submission
        fields = [
            'id', 'assignment', 'assignment_title', 'student', 'student_name',
            'text_content', 'submission_file', 'submission_file_url',
            'status', 'submitted_at', 'is_late', 'late_days',
            'grade_score', 'grade_feedback', 'grade_feedback_file_url',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['student', 'status', 'submitted_at', 'is_late', 'late_days', 'created_at', 'updated_at']

    def get_submission_file_url(self, obj):
        """URL del archivo de entrega"""
        if obj.submission_file:
            return obj.submission_file.url
        return None

    def get_grade_score(self, obj):
        """Calificación si existe"""
        try:
            return float(obj.grade.score) if obj.grade.score else None
        except:
            return None

    def get_grade_feedback(self, obj):
        """Feedback si existe"""
        try:
            return obj.grade.feedback
        except:
            return None

    def get_grade_feedback_file_url(self, obj):
        """URL del archivo de feedback"""
        try:
            if obj.grade.feedback_file:
                return obj.grade.feedback_file.url
        except:
            pass
        return None

    def create(self, validated_data):
        """Auto-asignar estudiante desde request"""
        request = self.context.get('request')
        if request and hasattr(request.user, 'student_profile'):
            validated_data['student'] = request.user.student_profile
        return super().create(validated_data)

    def validate(self, data):
        """Validar que el estudiante puede entregar"""
        request = self.context.get('request')
        assignment = data.get('assignment')

        if request and hasattr(request.user, 'student_profile'):
            student = request.user.student_profile

            # Verificar que el estudiante esté asignado
            if assignment.scope == 'selected':
                if student not in assignment.assigned_students.all():
                    raise serializers.ValidationError('No estás asignado a esta tarea')

            # Verificar si ya existe una entrega
            if not self.instance:  # Solo en create
                existing = Submission.objects.filter(assignment=assignment, student=student).exists()
                if existing:
                    raise serializers.ValidationError('Ya existe una entrega para esta tarea')

        return data


class GradeSerializer(serializers.ModelSerializer):
    """
    Serializer para calificaciones individuales
    """
    student_name = serializers.CharField(source='student.user.get_full_name', read_only=True)
    assignment_title = serializers.CharField(source='assignment.title', read_only=True)
    assignment_max_score = serializers.DecimalField(
        source='assignment.max_score',
        max_digits=5,
        decimal_places=2,
        read_only=True
    )
    graded_by_name = serializers.CharField(source='graded_by.user.get_full_name', read_only=True)
    feedback_file_url = serializers.SerializerMethodField()

    # Campos calculados
    normalized_score = serializers.SerializerMethodField()
    percentage = serializers.SerializerMethodField()

    class Meta:
        model = Grade
        fields = [
            'id', 'assignment', 'assignment_title', 'assignment_max_score',
            'student', 'student_name', 'submission', 'score', 'feedback',
            'feedback_file', 'feedback_file_url', 'normalized_score', 'percentage',
            'graded_by', 'graded_by_name', 'graded_at',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['graded_by', 'graded_at', 'created_at', 'updated_at']

    def get_feedback_file_url(self, obj):
        """URL del archivo de retroalimentación"""
        if obj.feedback_file:
            return obj.feedback_file.url
        return None

    def get_normalized_score(self, obj):
        """Calificación normalizada a escala de 10"""
        score = obj.get_normalized_score()
        return float(score) if score else None

    def get_percentage(self, obj):
        """Calificación como porcentaje"""
        percentage = obj.get_percentage()
        return float(percentage) if percentage else None

    def create(self, validated_data):
        """Establecer graded_by automáticamente"""
        request = self.context.get('request')
        if request and hasattr(request.user, 'teacher_profile'):
            validated_data['graded_by'] = request.user.teacher_profile
        return super().create(validated_data)

    def validate(self, data):
        """Validar calificación"""
        score = data.get('score')
        assignment = data.get('assignment')

        if score is not None and assignment:
            if score > assignment.max_score:
                raise serializers.ValidationError({
                    'score': f'La calificación ({score}) no puede exceder el puntaje máximo ({assignment.max_score})'
                })
            if score < 0:
                raise serializers.ValidationError({
                    'score': 'La calificación no puede ser negativa'
                })

        return data


class GradebookStudentSerializer(serializers.Serializer):
    """
    Serializer para una fila del gradebook (estudiante + sus calificaciones)
    """
    student_id = serializers.IntegerField()
    student_code = serializers.CharField()
    student_name = serializers.CharField()
    student_email = serializers.EmailField()

    # Diccionario con las calificaciones por assignment
    grades = serializers.DictField()

    # Promedios por categoría
    category_averages = serializers.DictField()

    # Calificación final
    final_grade = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)
    status = serializers.CharField(allow_null=True)


class GradebookSerializer(serializers.Serializer):
    """
    Serializer para el libro de calificaciones completo (tipo spreadsheet)
    """
    # Información del grupo
    subject_group_id = serializers.IntegerField()
    subject_name = serializers.CharField()
    subject_code = serializers.CharField()
    group_code = serializers.CharField()
    academic_period = serializers.CharField()

    # Categorías de ponderación
    categories = GradingCategorySerializer(many=True)

    # Assignments agrupados por categoría
    assignments = serializers.ListField()

    # Estudiantes con sus calificaciones
    students = GradebookStudentSerializer(many=True)

    # Estadísticas generales
    statistics = serializers.DictField()


class FinalGradeConfigSerializer(serializers.ModelSerializer):
    """
    Serializer para configuración de calificación final
    """
    subject_name = serializers.CharField(source='subject_group.subject.name', read_only=True)

    class Meta:
        model = FinalGradeConfig
        fields = [
            'id', 'subject_group', 'subject_name',
            'show_provisional_grades', 'is_published', 'published_at',
            'passing_score', 'rounding_method', 'decimal_places',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['published_at', 'created_at', 'updated_at']


class FinalGradeSerializer(serializers.ModelSerializer):
    """
    Serializer para calificación final
    """
    student_id = serializers.IntegerField(source='subject_enrollment.student.id', read_only=True)
    student_name = serializers.CharField(source='subject_enrollment.student.user.get_full_name', read_only=True)
    student_code = serializers.CharField(source='subject_enrollment.student.student_id', read_only=True)
    subject_name = serializers.CharField(source='subject_enrollment.subject_group.subject.name', read_only=True)
    subject_code = serializers.CharField(source='subject_enrollment.subject_group.subject.code', read_only=True)
    credits = serializers.IntegerField(source='subject_enrollment.subject_group.subject.credits', read_only=True)

    class Meta:
        model = FinalGrade
        fields = [
            'id', 'subject_enrollment',
            'student_id', 'student_name', 'student_code',
            'subject_name', 'subject_code', 'credits',
            'final_score', 'status', 'is_published', 'observations',
            'calculation_details', 'calculated_at',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['final_score', 'status', 'calculation_details', 'calculated_at', 'created_at', 'updated_at']


class StudentDashboardSerializer(serializers.Serializer):
    """
    Serializer para el dashboard del estudiante
    """
    # Tareas pendientes
    pending_assignments = AssignmentListSerializer(many=True)

    # Próximas tareas (próximos 7 días)
    upcoming_assignments = AssignmentListSerializer(many=True)

    # Calificaciones recientes (últimos 30 días)
    recent_grades = GradeSerializer(many=True)

    # Resumen por asignatura
    subjects_summary = serializers.ListField()

    # Estadísticas generales
    statistics = serializers.DictField()


class GradeReportSerializer(serializers.ModelSerializer):
    """
    Serializer para reportes de calificaciones
    """
    subject_name = serializers.CharField(source='subject_group.subject.name', read_only=True)
    generated_by_name = serializers.CharField(source='generated_by.user.get_full_name', read_only=True)

    class Meta:
        model = GradeReport
        fields = [
            'id', 'subject_group', 'subject_name',
            'generated_by', 'generated_by_name',
            'report_date', 'is_final', 'observations',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['report_date', 'created_at', 'updated_at']


class BulkGradeSerializer(serializers.Serializer):
    """
    Serializer para calificación masiva
    """
    grades = serializers.ListField(
        child=serializers.DictField(),
        help_text="Lista de diccionarios con: assignment_id, student_id, score, feedback"
    )

    def validate_grades(self, value):
        """Validar estructura de grades"""
        for grade_data in value:
            if 'assignment_id' not in grade_data:
                raise serializers.ValidationError("Cada calificación debe tener 'assignment_id'")
            if 'student_id' not in grade_data:
                raise serializers.ValidationError("Cada calificación debe tener 'student_id'")
            if 'score' not in grade_data:
                raise serializers.ValidationError("Cada calificación debe tener 'score'")

        return value

    def create(self, validated_data):
        """Crear múltiples calificaciones"""
        grades_data = validated_data.get('grades', [])
        request = self.context.get('request')

        created_grades = []
        errors = []

        for grade_data in grades_data:
            try:
                assignment = Assignment.objects.get(id=grade_data['assignment_id'])
                student = Student.objects.get(id=grade_data['student_id'])

                # Obtener o crear submission si no existe
                submission, _ = Submission.objects.get_or_create(
                    assignment=assignment,
                    student=student
                )

                # Crear o actualizar grade
                grade, created = Grade.objects.update_or_create(
                    assignment=assignment,
                    student=student,
                    defaults={
                        'submission': submission,
                        'score': grade_data['score'],
                        'feedback': grade_data.get('feedback', ''),
                        'graded_by': request.user.teacher_profile if hasattr(request.user, 'teacher_profile') else None
                    }
                )

                created_grades.append(grade)

            except Exception as e:
                errors.append({
                    'assignment_id': grade_data.get('assignment_id'),
                    'student_id': grade_data.get('student_id'),
                    'error': str(e)
                })

        return {
            'created_count': len(created_grades),
            'error_count': len(errors),
            'errors': errors
        }


# ==================== COURSE MATERIALS SERIALIZERS ====================

class CourseMaterialSerializer(serializers.ModelSerializer):
    """Serializer for course materials"""
    uploaded_by_name = serializers.CharField(source='uploaded_by.user.get_full_name', read_only=True)
    file_url = serializers.SerializerMethodField()
    file_name = serializers.SerializerMethodField()

    class Meta:
        model = CourseMaterial
        fields = [
            'id', 'subject_group', 'title', 'description', 'file', 'file_url', 'file_name',
            'file_type', 'file_size', 'file_size_display', 'folder', 'order',
            'is_published', 'uploaded_by', 'uploaded_by_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['file_type', 'file_size', 'file_size_display', 'uploaded_by', 'created_at', 'updated_at']

    def get_file_url(self, obj):
        """Return signed URL for the file"""
        if obj.file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None

    def get_file_name(self, obj):
        """Return original file name"""
        if obj.file:
            import os
            return os.path.basename(obj.file.name)
        return None

    def create(self, validated_data):
        request = self.context.get('request')
        if request and hasattr(request.user, 'teacher_profile'):
            validated_data['uploaded_by'] = request.user.teacher_profile
        return super().create(validated_data)


class CourseMaterialFolderSerializer(serializers.Serializer):
    """Serializer for grouping materials by folder"""
    folder_name = serializers.CharField()
    materials = CourseMaterialSerializer(many=True)
    total_size = serializers.IntegerField()
    file_count = serializers.IntegerField()


# ==================== ACADEMIC RECORD SERIALIZERS (PHASE 3) ====================

class SubjectGradeRecordSerializer(serializers.Serializer):
    """Serializer for individual subject grade in academic record"""
    subject_id = serializers.IntegerField()
    subject_code = serializers.CharField()
    subject_name = serializers.CharField()
    credits = serializers.IntegerField()
    final_grade = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)
    status = serializers.CharField()
    academic_period = serializers.CharField()
    teacher_name = serializers.CharField()
    assignments_count = serializers.IntegerField()
    passed = serializers.BooleanField()


class AcademicPeriodRecordSerializer(serializers.Serializer):
    """Serializer for academic period summary in record"""
    period_id = serializers.IntegerField()
    period_name = serializers.CharField()
    period_code = serializers.CharField()
    subjects = SubjectGradeRecordSerializer(many=True)
    period_average = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)
    credits_enrolled = serializers.IntegerField()
    credits_passed = serializers.IntegerField()
    subjects_passed = serializers.IntegerField()
    subjects_failed = serializers.IntegerField()


class AcademicRecordSerializer(serializers.Serializer):
    """Complete academic record for a student"""
    student_id = serializers.IntegerField()
    student_code = serializers.CharField()
    student_name = serializers.CharField()
    career_name = serializers.CharField()
    enrollment_date = serializers.DateField()

    # Aggregated statistics
    overall_average = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)
    total_credits_enrolled = serializers.IntegerField()
    total_credits_passed = serializers.IntegerField()
    total_subjects_enrolled = serializers.IntegerField()
    total_subjects_passed = serializers.IntegerField()
    total_subjects_failed = serializers.IntegerField()
    completion_percentage = serializers.DecimalField(max_digits=5, decimal_places=2)

    # Detailed records by period
    periods = AcademicPeriodRecordSerializer(many=True)

    # Current status
    current_period = serializers.CharField(allow_null=True)
    is_active = serializers.BooleanField()


class GradeTranscriptSerializer(serializers.Serializer):
    """Serializer for official grade transcript"""
    student = serializers.SerializerMethodField()
    career = serializers.SerializerMethodField()
    generated_date = serializers.DateTimeField()
    transcript_id = serializers.CharField()

    # Academic record
    periods = AcademicPeriodRecordSerializer(many=True)

    # Summary statistics
    overall_average = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)
    total_credits = serializers.IntegerField()
    total_subjects = serializers.IntegerField()

    def get_student(self, obj):
        return {
            'id': obj.get('student_id'),
            'code': obj.get('student_code'),
            'name': obj.get('student_name'),
            'email': obj.get('student_email')
        }

    def get_career(self, obj):
        return {
            'name': obj.get('career_name'),
            'enrollment_date': obj.get('enrollment_date')
        }


class ProgressReportSerializer(serializers.Serializer):
    """Serializer for student progress report"""
    student_id = serializers.IntegerField()
    student_name = serializers.CharField()
    career_name = serializers.CharField()
    current_period = serializers.CharField()

    # Performance metrics
    current_period_average = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)
    overall_average = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)
    credits_progress = serializers.DictField()

    # Trends
    grade_trend = serializers.ListField()

    # Current subjects
    current_subjects = SubjectGradeRecordSerializer(many=True)

    # Alerts
    at_risk_subjects = serializers.ListField()
    pending_assignments = serializers.IntegerField()


# ==================== QUIZ SERIALIZERS (PHASE 4) ====================

class QuestionOptionSerializer(serializers.ModelSerializer):
    """Serializer para opciones de pregunta"""

    class Meta:
        model = QuestionOption
        fields = [
            'id',
            'option_text',
            'is_correct',
            'order',
        ]
        read_only_fields = ['id']


class QuestionSerializer(serializers.ModelSerializer):
    """Serializer para preguntas con sus opciones"""
    options = QuestionOptionSerializer(many=True, read_only=True)
    is_objective = serializers.BooleanField(read_only=True)
    requires_manual_grading = serializers.BooleanField(read_only=True)

    class Meta:
        model = Question
        fields = [
            'id',
            'quiz',
            'question_type',
            'question_text',
            'explanation',
            'points',
            'order',
            'correct_answer',
            'case_sensitive',
            'options',
            'is_objective',
            'requires_manual_grading',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class QuestionWithOptionsCreateSerializer(serializers.ModelSerializer):
    """Serializer para crear preguntas con sus opciones en una sola llamada"""
    options = QuestionOptionSerializer(many=True, required=False)

    class Meta:
        model = Question
        fields = [
            'id',
            'quiz',
            'question_type',
            'question_text',
            'explanation',
            'points',
            'order',
            'correct_answer',
            'case_sensitive',
            'options',
        ]
        read_only_fields = ['id']

    def create(self, validated_data):
        options_data = validated_data.pop('options', [])
        question = Question.objects.create(**validated_data)

        # Crear opciones si existen
        for option_data in options_data:
            QuestionOption.objects.create(question=question, **option_data)

        return question

    def update(self, instance, validated_data):
        options_data = validated_data.pop('options', None)

        # Actualizar campos de la pregunta
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Actualizar opciones si se proporcionan
        if options_data is not None:
            # Eliminar opciones existentes
            instance.options.all().delete()

            # Crear nuevas opciones
            for option_data in options_data:
                QuestionOption.objects.create(question=instance, **option_data)

        return instance


class QuizListSerializer(serializers.ModelSerializer):
    """Serializer simplificado para listar quizzes"""
    subject_group_detail = SubjectGroupBasicSerializer(source='subject_group', read_only=True)
    question_count = serializers.IntegerField(read_only=True)
    is_available = serializers.BooleanField(read_only=True)
    is_past_due = serializers.BooleanField(read_only=True)

    # Para estudiantes: información de su progreso
    student_attempts_count = serializers.IntegerField(read_only=True, required=False)
    student_best_score = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        read_only=True,
        required=False
    )

    class Meta:
        model = Quiz
        fields = [
            'id',
            'subject_group',
            'subject_group_detail',
            'title',
            'description',
            'quiz_type',
            'question_count',
            'total_points',
            'passing_score',
            'due_date',
            'time_limit',
            'max_attempts',
            'is_published',
            'is_available',
            'is_past_due',
            'student_attempts_count',
            'student_best_score',
            'created_at',
        ]


class QuizDetailSerializer(serializers.ModelSerializer):
    """Serializer detallado para un quiz con todas sus preguntas"""
    subject_group_detail = SubjectGroupBasicSerializer(source='subject_group', read_only=True)
    questions = QuestionSerializer(many=True, read_only=True)
    question_count = serializers.IntegerField(read_only=True)
    is_available = serializers.BooleanField(read_only=True)
    is_past_due = serializers.BooleanField(read_only=True)
    created_by_detail = TeacherBasicSerializer(source='created_by', read_only=True)

    class Meta:
        model = Quiz
        fields = [
            'id',
            'subject_group',
            'subject_group_detail',
            'title',
            'description',
            'quiz_type',
            'time_limit',
            'due_date',
            'available_from',
            'available_until',
            'max_attempts',
            'total_points',
            'passing_score',
            'randomize_questions',
            'randomize_options',
            'show_correct_answers',
            'show_feedback',
            'is_published',
            'question_count',
            'is_available',
            'is_past_due',
            'questions',
            'created_by',
            'created_by_detail',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class QuizCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer para crear/actualizar quizzes"""

    class Meta:
        model = Quiz
        fields = [
            'id',
            'subject_group',
            'title',
            'description',
            'quiz_type',
            'time_limit',
            'due_date',
            'available_from',
            'available_until',
            'max_attempts',
            'total_points',
            'passing_score',
            'randomize_questions',
            'randomize_options',
            'show_correct_answers',
            'show_feedback',
            'is_published',
            'created_by',
        ]
        read_only_fields = ['id']


class QuizAnswerSerializer(serializers.ModelSerializer):
    """Serializer para respuestas de quiz"""
    question_detail = QuestionSerializer(source='question', read_only=True)

    class Meta:
        model = QuizAnswer
        fields = [
            'id',
            'attempt',
            'question',
            'question_detail',
            'selected_option',
            'text_answer',
            'is_correct',
            'points_earned',
            'teacher_feedback',
            'answered_at',
        ]
        read_only_fields = ['id', 'is_correct', 'points_earned', 'answered_at']


class QuizAttemptListSerializer(serializers.ModelSerializer):
    """Serializer simplificado para listar intentos"""
    quiz_detail = QuizListSerializer(source='quiz', read_only=True)
    student_detail = StudentBasicSerializer(source='student', read_only=True)
    is_passed = serializers.BooleanField(read_only=True)
    time_taken = serializers.SerializerMethodField()
    is_late = serializers.BooleanField(read_only=True)

    class Meta:
        model = QuizAttempt
        fields = [
            'id',
            'quiz',
            'quiz_detail',
            'student',
            'student_detail',
            'attempt_number',
            'status',
            'score',
            'max_score',
            'percentage',
            'is_passed',
            'time_taken',
            'is_late',
            'started_at',
            'submitted_at',
            'graded_at',
        ]

    def get_time_taken(self, obj):
        time_delta = obj.time_taken
        if time_delta:
            total_seconds = int(time_delta.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60

            if hours > 0:
                return f"{hours}h {minutes}m {seconds}s"
            elif minutes > 0:
                return f"{minutes}m {seconds}s"
            else:
                return f"{seconds}s"
        return None


class QuizAttemptDetailSerializer(serializers.ModelSerializer):
    """Serializer detallado para un intento con todas sus respuestas"""
    quiz_detail = QuizDetailSerializer(source='quiz', read_only=True)
    student_detail = StudentBasicSerializer(source='student', read_only=True)
    answers = QuizAnswerSerializer(many=True, read_only=True)
    is_passed = serializers.BooleanField(read_only=True)
    time_taken = serializers.SerializerMethodField()
    is_late = serializers.BooleanField(read_only=True)
    graded_by_detail = TeacherBasicSerializer(source='graded_by', read_only=True)

    class Meta:
        model = QuizAttempt
        fields = [
            'id',
            'quiz',
            'quiz_detail',
            'student',
            'student_detail',
            'attempt_number',
            'status',
            'score',
            'max_score',
            'percentage',
            'is_passed',
            'time_taken',
            'is_late',
            'teacher_feedback',
            'graded_by',
            'graded_by_detail',
            'started_at',
            'submitted_at',
            'graded_at',
            'answers',
        ]

    def get_time_taken(self, obj):
        time_delta = obj.time_taken
        if time_delta:
            total_seconds = int(time_delta.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60

            if hours > 0:
                return f"{hours}h {minutes}m {seconds}s"
            elif minutes > 0:
                return f"{minutes}m {seconds}s"
            else:
                return f"{seconds}s"
        return None


class QuizSubmissionSerializer(serializers.Serializer):
    """Serializer para enviar respuestas de un quiz"""
    answers = serializers.ListField(
        child=serializers.DictField()
    )

    def validate_answers(self, value):
        """
        Validar que cada respuesta tenga la estructura correcta
        Formato esperado:
        [
            {
                "question_id": 1,
                "selected_option_id": 2  # Para opción múltiple/verdadero-falso
            },
            {
                "question_id": 2,
                "text_answer": "Mi respuesta"  # Para respuesta corta/ensayo
            }
        ]
        """
        for answer in value:
            if 'question_id' not in answer:
                raise serializers.ValidationError("Cada respuesta debe incluir 'question_id'")

            if 'selected_option_id' not in answer and 'text_answer' not in answer:
                raise serializers.ValidationError(
                    "Cada respuesta debe incluir 'selected_option_id' o 'text_answer'"
                )

        return value


class QuizStatisticsSerializer(serializers.Serializer):
    """Serializer para estadísticas de un quiz"""
    quiz_id = serializers.IntegerField()
    quiz_title = serializers.CharField()
    total_attempts = serializers.IntegerField()
    unique_students = serializers.IntegerField()
    completed_attempts = serializers.IntegerField()
    average_score = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)
    pass_rate = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)
    average_time_minutes = serializers.FloatField(allow_null=True)
    score_distribution = serializers.ListField(
        child=serializers.DictField()
    )
