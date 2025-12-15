from django.contrib import admin
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
    Evaluation  # Legacy
)


@admin.register(GradingCategory)
class GradingCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'subject_group', 'weight', 'order', 'created_at']
    list_filter = ['subject_group__academic_period', 'subject_group__subject']
    search_fields = ['name', 'subject_group__subject__name']
    ordering = ['subject_group', 'order', 'name']
    list_editable = ['weight', 'order']


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ['title', 'subject_group', 'assignment_type', 'category', 'max_score', 'due_date', 'published_at']
    list_filter = ['assignment_type', 'subject_group__academic_period', 'category', 'published_at']
    search_fields = ['title', 'subject_group__subject__name', 'description']
    ordering = ['subject_group', '-due_date']
    filter_horizontal = ['assigned_students']
    date_hierarchy = 'due_date'

    fieldsets = (
        ('Información Básica', {
            'fields': ('subject_group', 'category', 'title', 'description', 'instructions', 'assignment_type')
        }),
        ('Calificación', {
            'fields': ('max_score', 'allow_late_submission', 'late_penalty_percent')
        }),
        ('Fechas', {
            'fields': ('start_date', 'due_date', 'published_at')
        }),
        ('Asignación', {
            'fields': ('scope', 'assigned_students')
        }),
        ('Archivo Adjunto', {
            'fields': ('attachment',)
        }),
        ('Metadatos', {
            'fields': ('created_by',),
            'classes': ('collapse',)
        }),
    )


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ['student_name', 'assignment', 'status', 'submitted_at', 'is_late', 'late_days']
    list_filter = ['status', 'is_late', 'assignment__assignment_type', 'submitted_at']
    search_fields = ['student__user__username', 'student__user__first_name', 'student__user__last_name', 'assignment__title']
    ordering = ['-submitted_at']
    date_hierarchy = 'submitted_at'
    readonly_fields = ['is_late', 'late_days', 'submitted_at']

    def student_name(self, obj):
        return obj.student.user.get_full_name()
    student_name.short_description = 'Estudiante'


@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    list_display = ['student_name', 'assignment', 'score', 'graded_by', 'graded_at']
    list_filter = ['graded_at', 'assignment__subject_group__academic_period', 'assignment__assignment_type']
    search_fields = ['student__user__username', 'student__user__first_name', 'student__user__last_name', 'assignment__title']
    ordering = ['-graded_at']
    date_hierarchy = 'graded_at'
    readonly_fields = ['graded_at']

    fieldsets = (
        ('Calificación', {
            'fields': ('assignment', 'student', 'submission', 'score', 'feedback')
        }),
        ('Archivo de Retroalimentación', {
            'fields': ('feedback_file',),
            'classes': ('collapse',)
        }),
        ('Metadatos', {
            'fields': ('graded_by', 'graded_at'),
            'classes': ('collapse',)
        }),
    )

    def student_name(self, obj):
        return obj.student.user.get_full_name()
    student_name.short_description = 'Estudiante'


@admin.register(FinalGradeConfig)
class FinalGradeConfigAdmin(admin.ModelAdmin):
    list_display = ['subject_group', 'passing_score', 'show_provisional_grades', 'is_published', 'published_at']
    list_filter = ['is_published', 'show_provisional_grades', 'rounding_method']
    search_fields = ['subject_group__subject__name']
    ordering = ['subject_group']

    fieldsets = (
        ('Asignatura', {
            'fields': ('subject_group',)
        }),
        ('Configuración de Visualización', {
            'fields': ('show_provisional_grades', 'is_published', 'published_at')
        }),
        ('Configuración de Cálculo', {
            'fields': ('passing_score', 'rounding_method', 'decimal_places')
        }),
    )


@admin.register(FinalGrade)
class FinalGradeAdmin(admin.ModelAdmin):
    list_display = ['student_name', 'subject_name', 'final_score', 'status', 'is_published', 'calculated_at']
    list_filter = ['status', 'is_published', 'calculated_at']
    search_fields = [
        'subject_enrollment__student__user__username',
        'subject_enrollment__student__user__first_name',
        'subject_enrollment__student__user__last_name',
        'subject_enrollment__subject_group__subject__name'
    ]
    ordering = ['-calculated_at']
    date_hierarchy = 'calculated_at'
    readonly_fields = ['final_score', 'status', 'calculation_details', 'calculated_at']

    fieldsets = (
        ('Inscripción', {
            'fields': ('subject_enrollment',)
        }),
        ('Calificación', {
            'fields': ('final_score', 'status', 'is_published', 'observations')
        }),
        ('Cálculos', {
            'fields': ('calculation_details', 'calculated_at'),
            'classes': ('collapse',)
        }),
    )

    def student_name(self, obj):
        return obj.subject_enrollment.student.user.get_full_name()
    student_name.short_description = 'Estudiante'

    def subject_name(self, obj):
        return obj.subject_enrollment.subject_group.subject.name
    subject_name.short_description = 'Asignatura'


@admin.register(GradeReport)
class GradeReportAdmin(admin.ModelAdmin):
    list_display = ['subject_group', 'generated_by', 'report_date', 'is_final']
    list_filter = ['is_final', 'report_date', 'subject_group__academic_period']
    search_fields = ['subject_group__subject__name', 'generated_by__user__username']
    ordering = ['-report_date']
    date_hierarchy = 'report_date'


@admin.register(CourseMaterial)
class CourseMaterialAdmin(admin.ModelAdmin):
    list_display = ['title', 'subject_group', 'folder', 'order', 'file_type', 'file_size_display', 'is_published', 'uploaded_by', 'created_at']
    list_filter = ['is_published', 'file_type', 'folder', 'subject_group__academic_period', 'created_at']
    search_fields = ['title', 'description', 'subject_group__subject__name']
    ordering = ['subject_group', 'folder', 'order', 'title']
    list_editable = ['is_published', 'order']
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Información Básica', {
            'fields': ('subject_group', 'title', 'description', 'folder', 'order')
        }),
        ('Archivo', {
            'fields': ('file',)
        }),
        ('Configuración', {
            'fields': ('is_published',)
        }),
        ('Metadatos', {
            'fields': ('uploaded_by', 'file_type', 'file_size'),
            'classes': ('collapse',)
        }),
    )

    readonly_fields = ['file_type', 'file_size']


# Legacy model - Mantener temporalmente
@admin.register(Evaluation)
class EvaluationAdminLegacy(admin.ModelAdmin):
    list_display = ['name', 'subject_group', 'type', 'weight', 'max_score', 'evaluation_date', 'is_published']
    list_filter = ['type', 'is_published', 'evaluation_date', 'subject_group__academic_period']
    search_fields = ['name', 'subject_group__subject__name']
    ordering = ['subject_group', '-evaluation_date']

    class Media:
        css = {
            'all': ('admin/css/legacy-warning.css',)
        }


# ==================== QUIZ ADMIN (PHASE 4) ====================

class QuestionOptionInline(admin.TabularInline):
    model = QuestionOption
    extra = 2
    fields = ['option_text', 'is_correct', 'order']


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 1
    fields = ['question_type', 'question_text', 'points', 'order']
    show_change_link = True


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = [
        'title',
        'subject_group',
        'quiz_type',
        'question_count',
        'total_points',
        'due_date',
        'is_published',
        'created_at',
    ]
    list_filter = [
        'quiz_type',
        'is_published',
        'subject_group__academic_period',
        'created_at',
    ]
    search_fields = ['title', 'description', 'subject_group__subject__name']
    ordering = ['-created_at']
    date_hierarchy = 'created_at'
    list_editable = ['is_published']
    inlines = [QuestionInline]

    fieldsets = (
        ('Información Básica', {
            'fields': ('subject_group', 'title', 'description', 'quiz_type')
        }),
        ('Configuración de Tiempo', {
            'fields': ('time_limit', 'available_from', 'available_until', 'due_date')
        }),
        ('Configuración de Calificación', {
            'fields': ('total_points', 'passing_score', 'max_attempts')
        }),
        ('Configuración de Visualización', {
            'fields': (
                'randomize_questions',
                'randomize_options',
                'show_correct_answers',
                'show_feedback',
            )
        }),
        ('Publicación', {
            'fields': ('is_published',)
        }),
        ('Metadatos', {
            'fields': ('created_by',),
            'classes': ('collapse',)
        }),
    )

    readonly_fields = []

    def question_count(self, obj):
        return obj.question_count
    question_count.short_description = 'Preguntas'


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = [
        'quiz',
        'question_type',
        'order',
        'points',
        'is_objective',
        'created_at',
    ]
    list_filter = ['question_type', 'quiz__subject_group__academic_period']
    search_fields = ['question_text', 'quiz__title']
    ordering = ['quiz', 'order']
    inlines = [QuestionOptionInline]

    fieldsets = (
        ('Información Básica', {
            'fields': ('quiz', 'question_type', 'question_text', 'points', 'order')
        }),
        ('Configuración de Respuesta', {
            'fields': ('correct_answer', 'case_sensitive', 'explanation')
        }),
    )

    def get_inline_instances(self, request, obj=None):
        """
        Solo mostrar opciones inline para preguntas de opción múltiple
        """
        if obj and obj.question_type in ['multiple_choice', 'true_false']:
            return super().get_inline_instances(request, obj)
        return []


@admin.register(QuestionOption)
class QuestionOptionAdmin(admin.ModelAdmin):
    list_display = ['question', 'option_text', 'is_correct', 'order']
    list_filter = ['is_correct', 'question__quiz__subject_group__academic_period']
    search_fields = ['option_text', 'question__question_text']
    ordering = ['question', 'order']
    list_editable = ['is_correct', 'order']


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = [
        'student',
        'quiz',
        'attempt_number',
        'status',
        'score',
        'max_score',
        'percentage',
        'is_passed',
        'started_at',
        'submitted_at',
    ]
    list_filter = [
        'status',
        'quiz__subject_group__academic_period',
        'started_at',
    ]
    search_fields = [
        'student__user__first_name',
        'student__user__last_name',
        'student__student_code',
        'quiz__title',
    ]
    ordering = ['-started_at']
    date_hierarchy = 'started_at'

    fieldsets = (
        ('Información del Intento', {
            'fields': ('quiz', 'student', 'attempt_number', 'status')
        }),
        ('Calificación', {
            'fields': ('score', 'max_score', 'percentage')
        }),
        ('Retroalimentación', {
            'fields': ('teacher_feedback', 'graded_by')
        }),
        ('Timestamps', {
            'fields': ('started_at', 'submitted_at', 'graded_at'),
            'classes': ('collapse',)
        }),
    )

    readonly_fields = ['started_at']


@admin.register(QuizAnswer)
class QuizAnswerAdmin(admin.ModelAdmin):
    list_display = [
        'attempt',
        'question',
        'is_correct',
        'points_earned',
        'answered_at',
    ]
    list_filter = [
        'is_correct',
        'question__question_type',
        'answered_at',
    ]
    search_fields = [
        'attempt__student__user__first_name',
        'attempt__student__user__last_name',
        'question__question_text',
    ]
    ordering = ['-answered_at']

    fieldsets = (
        ('Información de la Respuesta', {
            'fields': ('attempt', 'question')
        }),
        ('Respuesta', {
            'fields': ('selected_option', 'text_answer')
        }),
        ('Calificación', {
            'fields': ('is_correct', 'points_earned', 'teacher_feedback')
        }),
    )

    readonly_fields = ['answered_at']
