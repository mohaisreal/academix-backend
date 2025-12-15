from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from users.models import Teacher
from academic.models import Classroom, AcademicPeriod
from enrollment.models import SubjectGroup
from datetime import timedelta

User = get_user_model()


class TimeSlot(models.Model):
    """
    Model for time slots
    """
    WEEKDAY_CHOICES = [
        (0, 'Lunes'),
        (1, 'Martes'),
        (2, 'Miércoles'),
        (3, 'Jueves'),
        (4, 'Viernes'),
        (5, 'Sábado'),
        (6, 'Domingo'),
    ]

    academic_period = models.ForeignKey(
        AcademicPeriod,
        on_delete=models.CASCADE,
        related_name='time_slots',
        null=True,
        blank=True
    )
    day_of_week = models.IntegerField(choices=WEEKDAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()
    duration_minutes = models.IntegerField(editable=False, default=60)
    slot_code = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'time_slots'
        verbose_name = 'Time Slot'
        verbose_name_plural = 'Time Slots'
        ordering = ['day_of_week', 'start_time']
        unique_together = [['academic_period', 'day_of_week', 'start_time']]

    def save(self, *args, **kwargs):
        # Calculate duration in minutes
        if self.start_time and self.end_time:
            start_dt = timedelta(hours=self.start_time.hour, minutes=self.start_time.minute)
            end_dt = timedelta(hours=self.end_time.hour, minutes=self.end_time.minute)
            self.duration_minutes = int((end_dt - start_dt).total_seconds() / 60)

        # Generate slot_code if not provided
        if not self.slot_code:
            day_letter = ['L', 'M', 'X', 'J', 'V', 'S', 'D'][self.day_of_week]
            self.slot_code = f"{day_letter}{self.start_time.strftime('%H%M')}"

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_day_of_week_display()} {self.start_time.strftime('%H:%M')} - {self.end_time.strftime('%H:%M')}"


class Schedule(models.Model):
    """
    Model for class schedules
    """
    subject_group = models.ForeignKey(SubjectGroup, on_delete=models.CASCADE, related_name='schedules')
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='schedules')
    classroom = models.ForeignKey(Classroom, on_delete=models.CASCADE, related_name='schedules')
    time_slot = models.ForeignKey(TimeSlot, on_delete=models.CASCADE, related_name='schedules')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'schedules'
        verbose_name = 'Schedule'
        verbose_name_plural = 'Schedules'
        ordering = ['time_slot__day_of_week', 'time_slot__start_time']

    def __str__(self):
        return f"{self.subject_group.subject.name} - {self.teacher.user.get_full_name()} - {self.time_slot}"

    def clean(self):
        """Validate schedule for conflicts"""
        conflicts = self.check_conflicts()
        if conflicts:
            error_messages = []
            if conflicts['teacher_conflicts']:
                error_messages.append(
                    f"El profesor ya tiene clase en este horario: {conflicts['teacher_conflicts'][0]['subject']}"
                )
            if conflicts['classroom_conflicts']:
                error_messages.append(
                    f"El aula ya está ocupada en este horario: {conflicts['classroom_conflicts'][0]['subject']}"
                )
            raise ValidationError(' | '.join(error_messages))

    def check_conflicts(self):
        """Check for scheduling conflicts"""
        conflicts = {
            'teacher_conflicts': [],
            'classroom_conflicts': []
        }

        # Check teacher conflicts
        teacher_schedules = Schedule.objects.filter(
            teacher=self.teacher,
            time_slot=self.time_slot,
            is_active=True,
            subject_group__academic_period=self.subject_group.academic_period
        ).exclude(pk=self.pk)

        for schedule in teacher_schedules:
            conflicts['teacher_conflicts'].append({
                'subject': schedule.subject_group.subject.name,
                'group': schedule.subject_group.code
            })

        # Check classroom conflicts
        classroom_schedules = Schedule.objects.filter(
            classroom=self.classroom,
            time_slot=self.time_slot,
            is_active=True,
            subject_group__academic_period=self.subject_group.academic_period
        ).exclude(pk=self.pk)

        for schedule in classroom_schedules:
            conflicts['classroom_conflicts'].append({
                'subject': schedule.subject_group.subject.name,
                'group': schedule.subject_group.code
            })

        return conflicts


class TeacherAssignment(models.Model):
    """
    Model for teacher assignments to subject groups
    """
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='assignments')
    subject_group = models.ForeignKey(SubjectGroup, on_delete=models.CASCADE, related_name='teacher_assignments')
    assignment_date = models.DateField(auto_now_add=True)
    is_main_teacher = models.BooleanField(default=True)
    weekly_hours = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    status = models.CharField(
        max_length=20,
        choices=[
            ('active', 'Activo'),
            ('inactive', 'Inactivo'),
            ('completed', 'Completado'),
        ],
        default='active'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'teacher_assignments'
        verbose_name = 'Teacher Assignment'
        verbose_name_plural = 'Teacher Assignments'
        unique_together = [['teacher', 'subject_group']]
        ordering = ['-assignment_date']

    def __str__(self):
        return f"{self.teacher.user.get_full_name()} - {self.subject_group.subject.name}"

    def clean(self):
        """
        Validate that the teacher is qualified to teach the subject.
        """
        from django.core.exceptions import ValidationError

        if self.teacher and self.subject_group:
            subject = self.subject_group.subject
            if not self.teacher.can_teach_subject(subject):
                raise ValidationError({
                    'teacher': f'El profesor {self.teacher.user.get_full_name()} no está calificado para impartir la asignatura {subject.name}. '
                               f'Por favor, añada la asignatura individual o la carrera correspondiente a las calificaciones del profesor.'
                })

    def save(self, *args, **kwargs):
        """Override save to call clean()"""
        self.clean()
        super().save(*args, **kwargs)


class TeacherRole(models.Model):
    """
    Administrative roles for teachers (requires non-teaching hours)
    """
    ROLE_CHOICES = [
        ('teacher', 'Profesor'),
        ('tutor', 'Tutor de Aula'),
        ('department_head', 'Jefe de Departamento'),
        ('head_of_studies', 'Jefe de Estudios'),
        ('deputy_director', 'Subdirector'),
        ('director', 'Director'),
    ]

    name = models.CharField(max_length=50, choices=ROLE_CHOICES, unique=True)
    required_free_hours_per_week = models.IntegerField(
        validators=[MinValueValidator(0)],
        help_text="Horas no lectivas requeridas por semana"
    )
    priority = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text="Mayor número = mayor prioridad en asignación"
    )
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, default="briefcase")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'teacher_roles'
        verbose_name = 'Teacher Role'
        verbose_name_plural = 'Teacher Roles'
        ordering = ['-priority']

    def __str__(self):
        return self.get_name_display()


class TeacherRoleAssignment(models.Model):
    """
    Assignment of administrative roles to teachers for specific periods
    """
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='role_assignments')
    role = models.ForeignKey(TeacherRole, on_delete=models.CASCADE, related_name='assignments')
    academic_period = models.ForeignKey(AcademicPeriod, on_delete=models.CASCADE, related_name='teacher_role_assignments')
    additional_free_hours = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Horas adicionales no lectivas específicas para este profesor"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'teacher_role_assignments'
        verbose_name = 'Teacher Role Assignment'
        verbose_name_plural = 'Teacher Role Assignments'
        unique_together = [['teacher', 'role', 'academic_period']]

    def __str__(self):
        return f"{self.teacher.user.get_full_name()} - {self.role.get_name_display()} ({self.academic_period.name})"

    def get_total_free_hours(self):
        """Calculate total non-teaching hours required"""
        return self.role.required_free_hours_per_week + self.additional_free_hours


class TeacherAvailability(models.Model):
    """
    Teacher availability and scheduling restrictions (hard constraints)
    Controls whether a teacher can be scheduled and their time restrictions
    """
    AVAILABILITY_TYPE_CHOICES = [
        ('full', 'Disponibilidad Completa'),
        ('restricted', 'Disponibilidad Restringida'),
        ('unavailable', 'No Disponible'),
    ]

    teacher = models.ForeignKey(
        Teacher,
        on_delete=models.CASCADE,
        related_name='availability_restrictions'
    )
    academic_period = models.ForeignKey(
        AcademicPeriod,
        on_delete=models.CASCADE,
        related_name='teacher_availability'
    )

    # Main availability control
    availability_type = models.CharField(
        max_length=20,
        choices=AVAILABILITY_TYPE_CHOICES,
        default='full',
        help_text="Tipo de disponibilidad del profesor"
    )

    # Teaching hour restrictions
    max_teaching_hours = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(40)],
        help_text="Máximo de horas semanales que puede dar clase (null = sin límite)"
    )

    # Time slot restrictions
    # If availability_type is 'restricted', these define when the teacher CAN teach
    available_time_slots = models.ManyToManyField(
        TimeSlot,
        blank=True,
        related_name='available_for_teachers',
        help_text="Franjas horarias donde el profesor SÍ puede dar clase (solo si es 'restricted')"
    )

    # Blocked days (hard constraint)
    blocked_days = models.JSONField(
        default=list,
        blank=True,
        help_text="Lista de días bloqueados [0-6] donde 0=Lunes, no puede dar clase estos días"
    )

    # Reason for restriction
    restriction_reason = models.CharField(
        max_length=200,
        blank=True,
        help_text="Razón de la restricción (ej: 'De permiso', 'Medio tiempo', 'Proyecto especial')"
    )

    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_teacher_availability'
    )

    class Meta:
        db_table = 'teacher_availability'
        verbose_name = 'Teacher Availability'
        verbose_name_plural = 'Teacher Availabilities'
        unique_together = [['teacher', 'academic_period']]
        ordering = ['teacher__user__last_name']

    def __str__(self):
        return f"{self.teacher.user.get_full_name()} - {self.academic_period.name} ({self.get_availability_type_display()})"

    def can_teach_at_time_slot(self, time_slot: TimeSlot) -> bool:
        """
        Check if teacher can teach at a specific time slot
        Returns True if teacher is available, False otherwise
        """
        if not self.is_active:
            return True  # No active restriction

        if self.availability_type == 'unavailable':
            return False

        # Check blocked days
        if time_slot.day_of_week in self.blocked_days:
            return False

        # Check restricted availability
        if self.availability_type == 'restricted':
            # If restricted, they can only teach in available_time_slots
            return self.available_time_slots.filter(id=time_slot.id).exists()

        # Full availability
        return True

    def get_available_hours(self) -> int:
        """Get the maximum teaching hours allowed"""
        if self.availability_type == 'unavailable':
            return 0
        return self.max_teaching_hours if self.max_teaching_hours is not None else 40


class TeacherPreferences(models.Model):
    """
    Teacher scheduling preferences (soft constraints)
    """
    teacher = models.OneToOneField(Teacher, on_delete=models.CASCADE, related_name='scheduling_preferences')
    academic_period = models.ForeignKey(AcademicPeriod, on_delete=models.CASCADE, related_name='teacher_preferences')

    # Capacity constraints
    max_hours_per_week = models.IntegerField(default=20, validators=[MinValueValidator(1), MaxValueValidator(40)])
    max_consecutive_hours = models.IntegerField(default=4, validators=[MinValueValidator(1), MaxValueValidator(8)])
    max_daily_hours = models.IntegerField(default=6, validators=[MinValueValidator(1), MaxValueValidator(12)])

    # Preferences (JSON fields for flexibility)
    preferred_days = models.JSONField(
        default=list,
        blank=True,
        help_text="Lista de días preferidos [0-6] donde 0=Lunes"
    )
    unavailable_time_slots = models.ManyToManyField(
        TimeSlot,
        blank=True,
        related_name='unavailable_for_teachers',
        help_text="Franjas horarias no disponibles"
    )
    preferred_start_time = models.TimeField(null=True, blank=True)
    preferred_end_time = models.TimeField(null=True, blank=True)

    # Visualization
    color_code = models.CharField(max_length=7, default="#10B981")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'teacher_preferences'
        verbose_name = 'Teacher Preferences'
        verbose_name_plural = 'Teacher Preferences'

    def __str__(self):
        return f"Preferences: {self.teacher.user.get_full_name()} - {self.academic_period.name}"


class ScheduleConfiguration(models.Model):
    """
    Configuration for automatic schedule generation
    """
    ALGORITHM_CHOICES = [
        ('backtracking', 'Backtracking con Forward Checking'),
        ('genetic', 'Algoritmo Genético'),
        ('simulated_annealing', 'Recocido Simulado'),
    ]

    PRIORITY_CHOICES = [
        ('teachers', 'Priorizar profesores'),
        ('students', 'Priorizar estudiantes'),
        ('classrooms', 'Priorizar aulas'),
        ('balanced', 'Balanceado'),
    ]

    academic_period = models.OneToOneField(
        AcademicPeriod,
        on_delete=models.CASCADE,
        related_name='schedule_configuration'
    )

    # Algorithm parameters
    algorithm = models.CharField(max_length=50, choices=ALGORITHM_CHOICES, default='backtracking')
    max_execution_time_seconds = models.IntegerField(default=300, validators=[MinValueValidator(30)])
    optimization_priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='balanced')

    # Hard constraints
    allow_teacher_gaps = models.BooleanField(
        default=True,
        help_text="Permitir huecos entre clases de profesores"
    )
    max_daily_hours_per_teacher = models.IntegerField(default=6, validators=[MinValueValidator(1)])
    max_daily_hours_per_group = models.IntegerField(default=6, validators=[MinValueValidator(1)])
    max_classes_per_day = models.IntegerField(
        default=8,
        validators=[MinValueValidator(1), MaxValueValidator(15)],
        help_text="Máximo número de clases permitidas por día para un grupo"
    )
    max_sessions_per_subject_per_day = models.IntegerField(
        default=2,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Máximo número de sesiones de la misma materia por día"
    )
    min_break_between_classes = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Minutos mínimos de descanso entre clases"
    )

    # Soft constraints weights (0-10)
    weight_minimize_teacher_gaps = models.IntegerField(
        default=5,
        validators=[MinValueValidator(0), MaxValueValidator(10)]
    )
    weight_teacher_preferences = models.IntegerField(
        default=3,
        validators=[MinValueValidator(0), MaxValueValidator(10)]
    )
    weight_balanced_distribution = models.IntegerField(
        default=7,
        validators=[MinValueValidator(0), MaxValueValidator(10)]
    )
    weight_classroom_proximity = models.IntegerField(
        default=2,
        validators=[MinValueValidator(0), MaxValueValidator(10)]
    )
    weight_minimize_daily_changes = models.IntegerField(
        default=4,
        validators=[MinValueValidator(0), MaxValueValidator(10)]
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'schedule_configurations'
        verbose_name = 'Schedule Configuration'
        verbose_name_plural = 'Schedule Configurations'

    def __str__(self):
        return f"Config: {self.academic_period.name} - {self.get_algorithm_display()}"


class ScheduleGeneration(models.Model):
    """
    Record of schedule generation process and results
    """
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('running', 'Ejecutando'),
        ('completed', 'Completado'),
        ('failed', 'Fallido'),
        ('partial', 'Parcial'),
    ]

    batch_id = models.UUIDField(
        null=True,
        blank=True,
        help_text='ID del lote de generación - agrupa múltiples generaciones creadas en la misma ejecución'
    )
    academic_period = models.ForeignKey(
        AcademicPeriod,
        on_delete=models.CASCADE,
        related_name='schedule_generations'
    )
    career = models.ForeignKey(
        'academic.Career',
        on_delete=models.CASCADE,
        related_name='schedule_generations',
        null=True,
        blank=True,
        help_text='Carrera para la cual se generó este horario'
    )
    configuration = models.ForeignKey(
        ScheduleConfiguration,
        on_delete=models.SET_NULL,
        null=True,
        related_name='generations'
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    execution_time_seconds = models.FloatField(null=True, blank=True)

    total_sessions_to_schedule = models.IntegerField(default=0)
    sessions_scheduled = models.IntegerField(default=0)
    success_rate = models.FloatField(default=0.0)

    conflicts_detected = models.JSONField(default=list, blank=True)
    warnings = models.JSONField(default=list, blank=True)
    optimization_score = models.FloatField(null=True, blank=True)

    algorithm_used = models.CharField(max_length=50, blank=True)
    algorithm_parameters = models.JSONField(default=dict, blank=True)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_schedule_generations')
    is_published = models.BooleanField(default=False)

    notes = models.TextField(blank=True)

    class Meta:
        db_table = 'schedule_generations'
        verbose_name = 'Schedule Generation'
        verbose_name_plural = 'Schedule Generations'
        ordering = ['-started_at']

    def __str__(self):
        return f"Generation #{self.id} - {self.academic_period.name} ({self.get_status_display()})"

    def calculate_success_rate(self):
        """Calculate and update success rate"""
        if self.total_sessions_to_schedule > 0:
            self.success_rate = (self.sessions_scheduled / self.total_sessions_to_schedule) * 100
        else:
            self.success_rate = 0.0
        return self.success_rate


class ScheduleSession(models.Model):
    """
    Individual scheduled class session (generated by CSP algorithm)
    """
    SESSION_TYPE_CHOICES = [
        ('lecture', 'Clase Teórica'),
        ('lab', 'Laboratorio'),
        ('workshop', 'Taller'),
        ('seminar', 'Seminario'),
        ('exam', 'Examen'),
    ]

    schedule_generation = models.ForeignKey(
        ScheduleGeneration,
        on_delete=models.CASCADE,
        related_name='sessions'
    )
    teacher_assignment = models.ForeignKey(
        TeacherAssignment,
        on_delete=models.CASCADE,
        related_name='scheduled_sessions'
    )
    subject_group = models.ForeignKey(
        SubjectGroup,
        on_delete=models.CASCADE,
        related_name='scheduled_sessions'
    )
    teacher = models.ForeignKey(
        Teacher,
        on_delete=models.CASCADE,
        related_name='scheduled_sessions'
    )
    time_slot = models.ForeignKey(
        TimeSlot,
        on_delete=models.CASCADE,
        related_name='scheduled_sessions'
    )
    classroom = models.ForeignKey(
        Classroom,
        on_delete=models.CASCADE,
        related_name='scheduled_sessions'
    )

    duration_slots = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text="Número de franjas horarias consecutivas"
    )
    session_type = models.CharField(max_length=20, choices=SESSION_TYPE_CHOICES, default='lecture')

    is_locked = models.BooleanField(
        default=False,
        help_text="Si está bloqueado, no se puede modificar automáticamente"
    )
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'schedule_sessions'
        verbose_name = 'Schedule Session'
        verbose_name_plural = 'Schedule Sessions'
        ordering = ['time_slot__day_of_week', 'time_slot__start_time']
        # Ensure no conflicts in generated schedule
        unique_together = [
            ['schedule_generation', 'time_slot', 'classroom'],
            ['schedule_generation', 'time_slot', 'teacher'],
            ['schedule_generation', 'time_slot', 'subject_group'],
        ]

    def __str__(self):
        return f"{self.subject_group.code} - {self.teacher.user.get_full_name()} - {self.time_slot}"

    def clean(self):
        """Validate session for conflicts"""
        conflicts = []

        # Check classroom capacity
        if hasattr(self, 'classroom') and hasattr(self, 'subject_group'):
            if self.classroom.capacity < self.subject_group.max_capacity:
                conflicts.append(
                    f"El aula {self.classroom.code} (capacidad: {self.classroom.capacity}) "
                    f"es insuficiente para el grupo {self.subject_group.code} (tamaño: {self.subject_group.max_capacity})"
                )

        if conflicts:
            raise ValidationError(' | '.join(conflicts))


class BlockedTimeSlot(models.Model):
    """
    Model for blocking specific time slots from being used in schedule generation
    Allows administrators to mark certain time slots as unavailable for scheduling
    """
    BLOCK_TYPE_CHOICES = [
        ('global', 'Global - Todas las Carreras'),
        ('career', 'Por Carrera Específica'),
        ('classroom', 'Por Aula Específica'),
    ]

    academic_period = models.ForeignKey(
        AcademicPeriod,
        on_delete=models.CASCADE,
        related_name='blocked_time_slots',
        help_text='Período académico en el cual aplica el bloqueo'
    )
    time_slot = models.ForeignKey(
        TimeSlot,
        on_delete=models.CASCADE,
        related_name='blocks',
        help_text='Franja horaria bloqueada'
    )
    block_type = models.CharField(
        max_length=20,
        choices=BLOCK_TYPE_CHOICES,
        default='global',
        help_text='Tipo de bloqueo: global, por carrera o por aula'
    )

    # Optional: specific career or classroom (if block_type is not 'global')
    career = models.ForeignKey(
        'academic.Career',
        on_delete=models.CASCADE,
        related_name='blocked_time_slots',
        null=True,
        blank=True,
        help_text='Carrera afectada (solo si block_type es "career")'
    )
    classroom = models.ForeignKey(
        Classroom,
        on_delete=models.CASCADE,
        related_name='blocked_time_slots',
        null=True,
        blank=True,
        help_text='Aula afectada (solo si block_type es "classroom")'
    )

    reason = models.CharField(
        max_length=200,
        help_text='Razón del bloqueo (ej: "Mantenimiento", "Evento especial", "Reunión general")'
    )
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_blocked_time_slots'
    )

    class Meta:
        db_table = 'blocked_time_slots'
        verbose_name = 'Blocked Time Slot'
        verbose_name_plural = 'Blocked Time Slots'
        ordering = ['time_slot__day_of_week', 'time_slot__start_time']
        # Prevent duplicate blocks for the same combination
        unique_together = [
            ['academic_period', 'time_slot', 'block_type', 'career', 'classroom']
        ]

    def __str__(self):
        base = f"{self.time_slot} - {self.get_block_type_display()}"
        if self.block_type == 'career' and self.career:
            return f"{base} ({self.career.name})"
        elif self.block_type == 'classroom' and self.classroom:
            return f"{base} ({self.classroom.code})"
        return base

    def clean(self):
        """Validate block configuration"""
        errors = {}

        # Validate career is set for career-specific blocks
        if self.block_type == 'career' and not self.career:
            errors['career'] = 'Debe especificar una carrera cuando el tipo de bloqueo es "career"'

        # Validate classroom is set for classroom-specific blocks
        if self.block_type == 'classroom' and not self.classroom:
            errors['classroom'] = 'Debe especificar un aula cuando el tipo de bloqueo es "classroom"'

        # Ensure career is not set for non-career blocks
        if self.block_type != 'career' and self.career:
            errors['career'] = 'No debe especificar una carrera para bloqueos que no son por carrera'

        # Ensure classroom is not set for non-classroom blocks
        if self.block_type != 'classroom' and self.classroom:
            errors['classroom'] = 'No debe especificar un aula para bloqueos que no son por aula'

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        """Override save to call clean()"""
        self.clean()
        super().save(*args, **kwargs)

    def is_blocked_for_career(self, career) -> bool:
        """Check if this block applies to a specific career"""
        if not self.is_active:
            return False

        if self.block_type == 'global':
            return True
        elif self.block_type == 'career':
            return self.career_id == career.id if career else False
        else:  # classroom block doesn't affect career-level scheduling
            return False

    def is_blocked_for_classroom(self, classroom) -> bool:
        """Check if this block applies to a specific classroom"""
        if not self.is_active:
            return False

        if self.block_type == 'global':
            return True
        elif self.block_type == 'classroom':
            return self.classroom_id == classroom.id if classroom else False
        else:  # career block doesn't affect classroom-level scheduling directly
            return False
