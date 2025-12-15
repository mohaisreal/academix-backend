from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.db.models import Sum, Avg, Q
from django.utils import timezone
from decimal import Decimal
from enrollment.models import SubjectEnrollment, SubjectGroup
from users.models import Teacher, Student


class GradingCategory(models.Model):
    """
    Categoría de ponderación para evaluaciones (Exámenes 40%, Tareas 30%, etc.)
    """
    subject_group = models.ForeignKey(
        SubjectGroup,
        on_delete=models.CASCADE,
        related_name='grading_categories'
    )
    name = models.CharField(
        max_length=100,
        help_text="Nombre de la categoría (ej: Exámenes, Trabajos, Quizzes)"
    )
    weight = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Peso en porcentaje (0-100)"
    )
    description = models.TextField(blank=True, null=True)
    order = models.IntegerField(default=1, validators=[MinValueValidator(1)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'grading_categories'
        verbose_name = 'Grading Category'
        verbose_name_plural = 'Grading Categories'
        ordering = ['subject_group', 'order', 'name']
        unique_together = [['subject_group', 'name']]

    def __str__(self):
        return f"{self.subject_group.subject.name} - {self.name} ({self.weight}%)"

    def clean(self):
        """Validar que el peso total no exceda 100%"""
        total_weight = GradingCategory.objects.filter(
            subject_group=self.subject_group
        ).exclude(pk=self.pk).aggregate(total=Sum('weight'))['total'] or Decimal('0')

        if total_weight + self.weight > 100:
            raise ValidationError(
                f"El peso total de las categorías no puede exceder 100%. "
                f"Peso actual: {total_weight}%, Intentando agregar: {self.weight}%"
            )


class Assignment(models.Model):
    """
    Tarea, evaluación o examen asignado a estudiantes
    Reemplaza el modelo Evaluation con funcionalidades extendidas
    """
    ASSIGNMENT_TYPE_CHOICES = [
        ('task', 'Tarea'),
        ('quiz', 'Quiz'),
        ('exam', 'Examen'),
        ('project', 'Proyecto'),
        ('practical', 'Práctica'),
        ('participation', 'Participación'),
        ('other', 'Otro'),
    ]

    SCOPE_CHOICES = [
        ('all', 'Todos los estudiantes'),
        ('selected', 'Estudiantes seleccionados'),
    ]

    subject_group = models.ForeignKey(
        SubjectGroup,
        on_delete=models.CASCADE,
        related_name='assignments'
    )
    category = models.ForeignKey(
        GradingCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assignments',
        help_text="Categoría de ponderación (opcional)"
    )

    # Información básica
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    instructions = models.TextField(blank=True, null=True)
    assignment_type = models.CharField(
        max_length=20,
        choices=ASSIGNMENT_TYPE_CHOICES,
        default='task'
    )

    # Calificación
    max_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        default=10.0
    )

    # Fechas
    start_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Fecha de inicio (opcional)"
    )
    due_date = models.DateTimeField(
        help_text="Fecha límite de entrega"
    )
    published_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Fecha de publicación"
    )

    # Asignación
    scope = models.CharField(
        max_length=20,
        choices=SCOPE_CHOICES,
        default='all'
    )
    assigned_students = models.ManyToManyField(
        Student,
        blank=True,
        related_name='assigned_tasks',
        help_text="Estudiantes asignados (si scope='selected')"
    )

    # Entrega
    allow_late_submission = models.BooleanField(default=True)
    late_penalty_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Penalización por entrega tardía (%)"
    )

    # Archivo adjunto
    attachment = models.FileField(
        upload_to='assignments/%Y/%m/%d/',
        blank=True,
        null=True,
        help_text="Archivo adjunto del profesor (opcional)"
    )

    # Metadatos
    created_by = models.ForeignKey(
        Teacher,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_assignments'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'assignments'
        verbose_name = 'Assignment'
        verbose_name_plural = 'Assignments'
        ordering = ['subject_group', '-due_date']
        indexes = [
            models.Index(fields=['subject_group', 'published_at']),
            models.Index(fields=['assignment_type']),
            models.Index(fields=['due_date']),
        ]

    def __str__(self):
        return f"{self.subject_group.subject.name} - {self.title}"

    def clean(self):
        """Validaciones del assignment"""
        if self.start_date and self.due_date and self.start_date > self.due_date:
            raise ValidationError("La fecha de inicio no puede ser posterior a la fecha límite")

        if self.scope == 'selected' and not self.pk:
            # Se validará después de crear el objeto
            pass

    def is_published(self):
        """Verifica si el assignment está publicado"""
        return self.published_at is not None and self.published_at <= timezone.now()

    def is_overdue(self):
        """Verifica si el assignment está vencido"""
        return timezone.now() > self.due_date

    def publish(self):
        """Publicar el assignment"""
        if not self.published_at:
            self.published_at = timezone.now()
            self.save()


class Submission(models.Model):
    """
    Entrega de un estudiante para un assignment
    """
    STATUS_CHOICES = [
        ('draft', 'Borrador'),
        ('submitted', 'Entregado'),
        ('late', 'Entrega tardía'),
        ('graded', 'Calificado'),
        ('returned', 'Devuelto'),
    ]

    assignment = models.ForeignKey(
        Assignment,
        on_delete=models.CASCADE,
        related_name='submissions'
    )
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='submissions'
    )

    # Contenido
    text_content = models.TextField(
        blank=True,
        null=True,
        help_text="Respuesta en texto (opcional)"
    )
    submission_file = models.FileField(
        upload_to='submissions/%Y/%m/%d/',
        blank=True,
        null=True,
        help_text="Archivo de entrega del estudiante"
    )

    # Estado y fechas
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft'
    )
    submitted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Fecha y hora de entrega"
    )
    is_late = models.BooleanField(
        default=False,
        help_text="Indica si la entrega fue tardía"
    )
    late_days = models.IntegerField(
        default=0,
        help_text="Días de retraso"
    )

    # Metadatos
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'submissions'
        verbose_name = 'Submission'
        verbose_name_plural = 'Submissions'
        unique_together = [['assignment', 'student']]
        ordering = ['-submitted_at']
        indexes = [
            models.Index(fields=['assignment', 'student']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.student.user.get_full_name()} - {self.assignment.title}"

    def submit(self):
        """Marcar submission como entregada"""
        if self.status == 'draft':
            self.submitted_at = timezone.now()

            # Verificar si es tardía
            if self.submitted_at > self.assignment.due_date:
                self.is_late = True
                self.status = 'late'

                # Calcular días de retraso
                delta = self.submitted_at - self.assignment.due_date
                self.late_days = delta.days
            else:
                self.status = 'submitted'

            self.save()

    def can_submit(self):
        """Verifica si el estudiante puede entregar"""
        if self.status in ['submitted', 'late', 'graded', 'returned']:
            return False

        if not self.assignment.allow_late_submission and timezone.now() > self.assignment.due_date:
            return False

        return True


class Grade(models.Model):
    """
    Calificación individual de un assignment
    """
    assignment = models.ForeignKey(
        Assignment,
        on_delete=models.CASCADE,
        related_name='grades'
    )
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='grades'
    )
    submission = models.OneToOneField(
        Submission,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='grade'
    )

    # Calificación
    score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        blank=True,
        null=True
    )
    feedback = models.TextField(blank=True, null=True)
    feedback_file = models.FileField(
        upload_to='feedback/%Y/%m/%d/',
        blank=True,
        null=True,
        help_text="Archivo de retroalimentación (opcional)"
    )

    # Metadatos
    graded_by = models.ForeignKey(
        Teacher,
        on_delete=models.SET_NULL,
        null=True,
        related_name='graded_assignments'
    )
    graded_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'grades'
        verbose_name = 'Grade'
        verbose_name_plural = 'Grades'
        unique_together = [['assignment', 'student']]
        ordering = ['-graded_at']
        indexes = [
            models.Index(fields=['assignment', 'student']),
            models.Index(fields=['student']),
        ]

    def __str__(self):
        return f"{self.student.user.get_full_name()} - {self.assignment.title}: {self.score}"

    def clean(self):
        """Validar que el score no exceda el max_score"""
        if self.score and self.score > self.assignment.max_score:
            raise ValidationError(
                f"La calificación ({self.score}) no puede exceder el puntaje máximo ({self.assignment.max_score})"
            )

    def save(self, *args, **kwargs):
        """Override save para establecer graded_at"""
        if self.score is not None and not self.graded_at:
            self.graded_at = timezone.now()

        # Actualizar estado de submission si existe
        if self.submission:
            self.submission.status = 'graded'
            self.submission.save()

        super().save(*args, **kwargs)

    def get_normalized_score(self):
        """Obtener calificación normalizada a escala de 10"""
        if self.score is None:
            return None
        return (self.score / self.assignment.max_score) * Decimal('10')

    def get_percentage(self):
        """Obtener calificación como porcentaje"""
        if self.score is None:
            return None
        return (self.score / self.assignment.max_score) * Decimal('100')


class FinalGradeConfig(models.Model):
    """
    Configuración de calificación final por asignatura
    """
    ROUNDING_CHOICES = [
        ('none', 'Sin redondeo'),
        ('up', 'Redondear hacia arriba'),
        ('down', 'Redondear hacia abajo'),
        ('nearest', 'Redondear al más cercano'),
    ]

    subject_group = models.OneToOneField(
        SubjectGroup,
        on_delete=models.CASCADE,
        related_name='final_grade_config'
    )

    # Configuración de visualización
    show_provisional_grades = models.BooleanField(
        default=False,
        help_text="Mostrar calificaciones provisionales a estudiantes"
    )
    is_published = models.BooleanField(
        default=False,
        help_text="Calificaciones finales publicadas"
    )
    published_at = models.DateTimeField(null=True, blank=True)

    # Configuración de cálculo
    passing_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=5.0,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="Calificación mínima para aprobar"
    )
    rounding_method = models.CharField(
        max_length=20,
        choices=ROUNDING_CHOICES,
        default='nearest'
    )
    decimal_places = models.IntegerField(
        default=2,
        validators=[MinValueValidator(0), MaxValueValidator(4)],
        help_text="Número de decimales en calificación final"
    )

    # Metadatos
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'final_grade_configs'
        verbose_name = 'Final Grade Configuration'
        verbose_name_plural = 'Final Grade Configurations'

    def __str__(self):
        return f"Config - {self.subject_group.subject.name}"

    def publish(self):
        """Publicar calificaciones finales"""
        self.is_published = True
        self.published_at = timezone.now()
        self.save()


class FinalGrade(models.Model):
    """
    Calificación final de un estudiante en una asignatura
    """
    GRADE_STATUS_CHOICES = [
        ('passed', 'Aprobado'),
        ('failed', 'Reprobado'),
        ('pending', 'Pendiente'),
    ]

    subject_enrollment = models.OneToOneField(
        SubjectEnrollment,
        on_delete=models.CASCADE,
        related_name='final_grade'
    )

    # Calificación
    final_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        blank=True,
        null=True
    )
    status = models.CharField(
        max_length=20,
        choices=GRADE_STATUS_CHOICES,
        default='pending'
    )

    # Publicación
    is_published = models.BooleanField(default=False)
    observations = models.TextField(blank=True, null=True)

    # Cálculos
    calculation_details = models.JSONField(
        default=dict,
        blank=True,
        help_text="Detalles del cálculo de la calificación final"
    )
    calculated_at = models.DateTimeField(blank=True, null=True)

    # Metadatos
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'final_grades'
        verbose_name = 'Final Grade'
        verbose_name_plural = 'Final Grades'
        ordering = ['-calculated_at']

    def __str__(self):
        student_name = self.subject_enrollment.student.user.get_full_name()
        subject_name = self.subject_enrollment.subject_group.subject.name
        return f"{student_name} - {subject_name}: {self.final_score}"

    def calculate_with_categories(self):
        """
        Calcular calificación final usando categorías de ponderación
        """
        subject_group = self.subject_enrollment.subject_group
        student = self.subject_enrollment.student

        # Obtener categorías
        categories = GradingCategory.objects.filter(subject_group=subject_group)

        if not categories.exists():
            # Fallback: calcular sin categorías
            return self._calculate_without_categories()

        total_weighted_score = Decimal('0')
        total_weight = Decimal('0')
        details = {
            'categories': [],
            'method': 'with_categories'
        }

        for category in categories:
            # Obtener assignments de esta categoría
            assignments = Assignment.objects.filter(
                subject_group=subject_group,
                category=category,
                published_at__isnull=False
            )

            if not assignments.exists():
                continue

            # Calcular promedio de la categoría
            category_total = Decimal('0')
            category_count = 0
            assignment_details = []

            for assignment in assignments:
                try:
                    grade = Grade.objects.get(
                        assignment=assignment,
                        student=student,
                        score__isnull=False
                    )

                    normalized_score = grade.get_normalized_score()
                    category_total += normalized_score
                    category_count += 1

                    assignment_details.append({
                        'assignment': assignment.title,
                        'score': float(grade.score),
                        'max_score': float(assignment.max_score),
                        'normalized': float(normalized_score)
                    })
                except Grade.DoesNotExist:
                    pass

            if category_count > 0:
                category_average = category_total / category_count
                weighted_contribution = category_average * (category.weight / Decimal('100'))
                total_weighted_score += weighted_contribution
                total_weight += category.weight

                details['categories'].append({
                    'name': category.name,
                    'weight': float(category.weight),
                    'average': float(category_average),
                    'contribution': float(weighted_contribution),
                    'assignments': assignment_details
                })

        if total_weight == 0:
            self.final_score = None
            self.status = 'pending'
        else:
            # Ajustar si no todas las categorías tienen calificaciones
            if total_weight < 100:
                # Prorratear al total
                self.final_score = (total_weighted_score / total_weight) * Decimal('100')
            else:
                self.final_score = total_weighted_score

            # Aplicar redondeo según configuración
            config = FinalGradeConfig.objects.filter(subject_group=subject_group).first()
            if config:
                self.final_score = self._apply_rounding(self.final_score, config)
                passing_score = config.passing_score
            else:
                passing_score = Decimal('5.0')

            # Determinar estado
            self.status = 'passed' if self.final_score >= passing_score else 'failed'
            details['total_weight_used'] = float(total_weight)
            details['passing_score'] = float(passing_score)

        self.calculation_details = details
        self.calculated_at = timezone.now()
        self.save()

        return self.final_score

    def _calculate_without_categories(self):
        """
        Método legacy: calcular sin categorías (promedio ponderado de assignments)
        """
        subject_group = self.subject_enrollment.subject_group
        student = self.subject_enrollment.student

        assignments = Assignment.objects.filter(
            subject_group=subject_group,
            published_at__isnull=False
        )

        if not assignments.exists():
            self.final_score = None
            self.status = 'pending'
            self.calculation_details = {'method': 'no_assignments'}
            self.calculated_at = timezone.now()
            self.save()
            return None

        total_weighted_score = Decimal('0')
        total_weight = Decimal('0')

        for assignment in assignments:
            try:
                grade = Grade.objects.get(
                    assignment=assignment,
                    student=student,
                    score__isnull=False
                )

                normalized_score = grade.get_normalized_score()
                # Usar max_score como peso si no hay categorías
                total_weighted_score += normalized_score
                total_weight += Decimal('1')
            except Grade.DoesNotExist:
                pass

        if total_weight == 0:
            self.final_score = None
            self.status = 'pending'
        else:
            self.final_score = total_weighted_score / total_weight

            config = FinalGradeConfig.objects.filter(subject_group=subject_group).first()
            passing_score = config.passing_score if config else Decimal('5.0')

            self.status = 'passed' if self.final_score >= passing_score else 'failed'

        self.calculation_details = {'method': 'without_categories', 'assignments_count': int(total_weight)}
        self.calculated_at = timezone.now()
        self.save()

        return self.final_score

    def _apply_rounding(self, score, config):
        """Aplicar método de redondeo según configuración"""
        if config.rounding_method == 'none':
            return score
        elif config.rounding_method == 'up':
            import math
            return Decimal(math.ceil(float(score) * (10 ** config.decimal_places)) / (10 ** config.decimal_places))
        elif config.rounding_method == 'down':
            import math
            return Decimal(math.floor(float(score) * (10 ** config.decimal_places)) / (10 ** config.decimal_places))
        else:  # nearest
            return round(score, config.decimal_places)

    def publish(self):
        """Publicar calificación final"""
        if self.final_score is None:
            self.calculate_with_categories()

        self.is_published = True
        self.save()

        # Crear notificación
        from notifications.models import Notification
        Notification.objects.create(
            recipient=self.subject_enrollment.student.user,
            title='Nueva Calificación Final Publicada',
            message=f'Tu calificación final para {self.subject_enrollment.subject_group.subject.name} ha sido publicada: {self.final_score}',
            type='grade_published',
            priority='medium'
        )


class GradeReport(models.Model):
    """
    Reporte de calificaciones generado por un profesor
    """
    subject_group = models.ForeignKey(
        SubjectGroup,
        on_delete=models.CASCADE,
        related_name='grade_reports'
    )
    generated_by = models.ForeignKey(
        Teacher,
        on_delete=models.SET_NULL,
        null=True,
        related_name='generated_reports'
    )
    report_date = models.DateField(auto_now_add=True)
    is_final = models.BooleanField(default=False)
    observations = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'grade_reports'
        verbose_name = 'Grade Report'
        verbose_name_plural = 'Grade Reports'
        ordering = ['-report_date']

    def __str__(self):
        return f"Report - {self.subject_group.subject.name} - {self.report_date}"


# Modelo legacy - Mantener temporalmente para compatibilidad
class Evaluation(models.Model):
    """
    DEPRECATED: Usar Assignment en su lugar
    Mantenido temporalmente para compatibilidad con datos existentes
    """
    EVALUATION_TYPE_CHOICES = [
        ('exam', 'Examen'),
        ('assignment', 'Trabajo'),
        ('practical', 'Práctica'),
        ('project', 'Proyecto'),
        ('quiz', 'Quiz'),
        ('participation', 'Participación'),
        ('other', 'Otro'),
    ]

    subject_group = models.ForeignKey(SubjectGroup, on_delete=models.CASCADE, related_name='evaluations_legacy')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    type = models.CharField(max_length=20, choices=EVALUATION_TYPE_CHOICES)
    weight = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Evaluation weight in percentage (0-100)"
    )
    max_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        default=10.0
    )
    evaluation_date = models.DateField(blank=True, null=True)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'evaluations_legacy'
        verbose_name = 'Evaluation (Legacy)'
        verbose_name_plural = 'Evaluations (Legacy)'
        ordering = ['subject_group', '-evaluation_date']

    def __str__(self):
        return f"[LEGACY] {self.subject_group.subject.name} - {self.name}"


class CourseMaterial(models.Model):
    """
    Material educativo del curso (PDFs, presentaciones, documentos, etc.)
    """
    subject_group = models.ForeignKey(
        SubjectGroup,
        on_delete=models.CASCADE,
        related_name='course_materials'
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    file = models.FileField(upload_to='course_materials/%Y/%m/%d/')
    file_type = models.CharField(max_length=100, blank=True)
    file_size = models.BigIntegerField(default=0, help_text="File size in bytes")
    folder = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Folder name for organization"
    )
    order = models.IntegerField(default=1, validators=[MinValueValidator(1)])
    is_published = models.BooleanField(
        default=True,
        help_text="Whether the material is visible to students"
    )
    uploaded_by = models.ForeignKey(
        Teacher,
        on_delete=models.SET_NULL,
        null=True,
        related_name='uploaded_materials'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'course_materials'
        verbose_name = 'Course Material'
        verbose_name_plural = 'Course Materials'
        ordering = ['subject_group', 'folder', 'order', 'title']

    def __str__(self):
        return f"{self.subject_group.subject.name} - {self.title}"

    def save(self, *args, **kwargs):
        # Auto-detect file type and size if file is present
        if self.file:
            self.file_size = self.file.size
            if not self.file_type:
                # Extract file extension
                import os
                self.file_type = os.path.splitext(self.file.name)[1][1:].lower()
        super().save(*args, **kwargs)

    @property
    def file_size_display(self):
        """Return human-readable file size"""
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"


# ==================== QUIZ MODELS (PHASE 4) ====================

class Quiz(models.Model):
    """
    Modelo para cuestionarios/exámenes en línea
    """
    QUIZ_TYPES = [
        ('practice', 'Práctica'),
        ('quiz', 'Quiz'),
        ('exam', 'Examen'),
    ]

    subject_group = models.ForeignKey(
        'enrollment.SubjectGroup',
        on_delete=models.CASCADE,
        related_name='quizzes'
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    quiz_type = models.CharField(max_length=20, choices=QUIZ_TYPES, default='quiz')

    # Configuración de tiempo
    time_limit = models.IntegerField(
        null=True,
        blank=True,
        help_text='Límite de tiempo en minutos (dejar en blanco para sin límite)'
    )
    due_date = models.DateTimeField(null=True, blank=True)
    available_from = models.DateTimeField(null=True, blank=True)
    available_until = models.DateTimeField(null=True, blank=True)

    # Configuración de intentos
    max_attempts = models.IntegerField(
        default=1,
        help_text='Número máximo de intentos permitidos'
    )

    # Configuración de calificación
    total_points = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=100.00
    )
    passing_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=70.00,
        help_text='Puntaje mínimo para aprobar (%)'
    )

    # Configuración de visualización
    randomize_questions = models.BooleanField(
        default=False,
        help_text='Randomizar el orden de las preguntas'
    )
    randomize_options = models.BooleanField(
        default=False,
        help_text='Randomizar el orden de las opciones'
    )
    show_correct_answers = models.BooleanField(
        default=True,
        help_text='Mostrar respuestas correctas después de completar'
    )
    show_feedback = models.BooleanField(
        default=True,
        help_text='Mostrar retroalimentación después de completar'
    )

    # Publicación
    is_published = models.BooleanField(default=False)

    # Metadatos
    created_by = models.ForeignKey(
        'users.Teacher',
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_quizzes'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Quiz'
        verbose_name_plural = 'Quizzes'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.subject_group}"

    @property
    def question_count(self):
        """Número total de preguntas"""
        return self.questions.count()

    @property
    def is_available(self):
        """Verifica si el quiz está disponible actualmente"""
        now = timezone.now()

        if not self.is_published:
            return False

        if self.available_from and now < self.available_from:
            return False

        if self.available_until and now > self.available_until:
            return False

        return True

    @property
    def is_past_due(self):
        """Verifica si el quiz está vencido"""
        if not self.due_date:
            return False
        return timezone.now() > self.due_date


class Question(models.Model):
    """
    Modelo para preguntas individuales en un quiz
    """
    QUESTION_TYPES = [
        ('multiple_choice', 'Opción Múltiple'),
        ('true_false', 'Verdadero/Falso'),
        ('short_answer', 'Respuesta Corta'),
        ('essay', 'Ensayo'),
    ]

    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name='questions'
    )
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPES)
    question_text = models.TextField()
    explanation = models.TextField(
        blank=True,
        help_text='Explicación que se muestra después de responder'
    )
    points = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=1.00
    )
    order = models.IntegerField(default=1)

    # Para respuestas cortas y ensayos
    correct_answer = models.TextField(
        blank=True,
        help_text='Respuesta correcta para preguntas de respuesta corta'
    )

    # Para auto-calificación de respuestas cortas
    case_sensitive = models.BooleanField(
        default=False,
        help_text='Distinguir mayúsculas/minúsculas en respuestas cortas'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Pregunta'
        verbose_name_plural = 'Preguntas'
        ordering = ['quiz', 'order']

    def __str__(self):
        return f"{self.quiz.title} - Q{self.order}"

    @property
    def is_objective(self):
        """Verifica si la pregunta se puede calificar automáticamente"""
        return self.question_type in ['multiple_choice', 'true_false', 'short_answer']

    @property
    def requires_manual_grading(self):
        """Verifica si la pregunta requiere calificación manual"""
        return self.question_type == 'essay'


class QuestionOption(models.Model):
    """
    Modelo para opciones de respuesta en preguntas de opción múltiple
    """
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='options'
    )
    option_text = models.TextField()
    is_correct = models.BooleanField(default=False)
    order = models.IntegerField(default=1)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Opción de Pregunta'
        verbose_name_plural = 'Opciones de Pregunta'
        ordering = ['question', 'order']

    def __str__(self):
        return f"{self.question} - Option {self.order}"


class QuizAttempt(models.Model):
    """
    Modelo para intentos de un estudiante en un quiz
    """
    STATUS_CHOICES = [
        ('in_progress', 'En Progreso'),
        ('submitted', 'Enviado'),
        ('graded', 'Calificado'),
    ]

    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name='attempts'
    )
    student = models.ForeignKey(
        'users.Student',
        on_delete=models.CASCADE,
        related_name='quiz_attempts'
    )
    attempt_number = models.IntegerField(default=1)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='in_progress')

    # Timestamps
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    graded_at = models.DateTimeField(null=True, blank=True)

    # Calificación
    score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Puntaje obtenido'
    )
    max_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Puntaje máximo posible'
    )
    percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Porcentaje obtenido'
    )

    # Retroalimentación del profesor (para preguntas que requieren calificación manual)
    teacher_feedback = models.TextField(blank=True)
    graded_by = models.ForeignKey(
        'users.Teacher',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='graded_quiz_attempts'
    )

    class Meta:
        verbose_name = 'Intento de Quiz'
        verbose_name_plural = 'Intentos de Quiz'
        ordering = ['-started_at']
        unique_together = ['quiz', 'student', 'attempt_number']

    def __str__(self):
        return f"{self.student.user.get_full_name()} - {self.quiz.title} (Attempt {self.attempt_number})"

    @property
    def is_passed(self):
        """Verifica si el intento fue aprobado"""
        if self.percentage is None:
            return False
        return self.percentage >= self.quiz.passing_score

    @property
    def time_taken(self):
        """Calcula el tiempo tomado para completar el quiz"""
        if not self.submitted_at:
            return None
        return self.submitted_at - self.started_at

    @property
    def is_late(self):
        """Verifica si el intento fue enviado después de la fecha límite"""
        if not self.quiz.due_date or not self.submitted_at:
            return False
        return self.submitted_at > self.quiz.due_date

    def calculate_score(self):
        """
        Calcula el puntaje del intento basado en las respuestas
        Solo para preguntas objetivas (auto-calificables)
        """
        from decimal import Decimal

        total_points = Decimal('0.00')
        earned_points = Decimal('0.00')

        for answer in self.answers.all():
            question = answer.question
            total_points += question.points

            if question.is_objective and answer.is_correct:
                earned_points += question.points

        self.max_score = total_points
        self.score = earned_points

        if total_points > 0:
            self.percentage = (earned_points / total_points) * 100
        else:
            self.percentage = Decimal('0.00')

        # Si todas las preguntas son objetivas, marcar como calificado
        all_objective = all(
            answer.question.is_objective
            for answer in self.answers.all()
        )

        if all_objective and self.status == 'submitted':
            self.status = 'graded'
            self.graded_at = timezone.now()

        self.save()
        return self.score


class QuizAnswer(models.Model):
    """
    Modelo para respuestas individuales en un intento de quiz
    """
    attempt = models.ForeignKey(
        QuizAttempt,
        on_delete=models.CASCADE,
        related_name='answers'
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='student_answers'
    )

    # Para preguntas de opción múltiple y verdadero/falso
    selected_option = models.ForeignKey(
        QuestionOption,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='student_selections'
    )

    # Para preguntas de respuesta corta y ensayo
    text_answer = models.TextField(blank=True)

    # Calificación
    is_correct = models.BooleanField(null=True, blank=True)
    points_earned = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True
    )

    # Para preguntas de ensayo
    teacher_feedback = models.TextField(blank=True)

    answered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Respuesta de Quiz'
        verbose_name_plural = 'Respuestas de Quiz'
        unique_together = ['attempt', 'question']

    def __str__(self):
        return f"{self.attempt} - {self.question}"

    def check_answer(self):
        """
        Verifica si la respuesta es correcta (solo para preguntas objetivas)
        """
        question = self.question

        if question.question_type == 'multiple_choice' or question.question_type == 'true_false':
            if self.selected_option:
                self.is_correct = self.selected_option.is_correct
                if self.is_correct:
                    self.points_earned = question.points
                else:
                    self.points_earned = 0
            else:
                self.is_correct = False
                self.points_earned = 0

        elif question.question_type == 'short_answer':
            if question.correct_answer:
                student_answer = self.text_answer.strip()
                correct_answer = question.correct_answer.strip()

                if not question.case_sensitive:
                    student_answer = student_answer.lower()
                    correct_answer = correct_answer.lower()

                self.is_correct = student_answer == correct_answer
                if self.is_correct:
                    self.points_earned = question.points
                else:
                    self.points_earned = 0
            else:
                # Si no hay respuesta correcta definida, requiere calificación manual
                self.is_correct = None
                self.points_earned = None

        elif question.question_type == 'essay':
            # Los ensayos siempre requieren calificación manual
            self.is_correct = None
            self.points_earned = None

        self.save()
        return self.is_correct
