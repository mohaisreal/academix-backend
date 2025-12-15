from django.contrib import admin
from django.utils.html import format_html
from .models import (
    TimeSlot, Schedule, TeacherAssignment,
    TeacherRole, TeacherRoleAssignment, TeacherPreferences,
    ScheduleConfiguration, ScheduleGeneration, ScheduleSession,
    BlockedTimeSlot
)


@admin.register(TimeSlot)
class TimeSlotAdmin(admin.ModelAdmin):
    list_display = ['academic_period', 'day_of_week', 'start_time', 'end_time', 'duration_minutes', 'slot_code', 'is_active']
    list_filter = ['academic_period', 'day_of_week', 'is_active']
    search_fields = ['slot_code']
    ordering = ['academic_period', 'day_of_week', 'start_time']
    readonly_fields = ['duration_minutes', 'slot_code']


@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = ['subject_group', 'teacher', 'classroom', 'time_slot', 'is_active']
    list_filter = ['is_active', 'time_slot__day_of_week', 'subject_group__academic_period']
    search_fields = ['subject_group__subject__name', 'teacher__user__username', 'classroom__code']
    ordering = ['time_slot__day_of_week', 'time_slot__start_time']
    raw_id_fields = ['subject_group', 'teacher', 'classroom', 'time_slot']


@admin.register(TeacherAssignment)
class TeacherAssignmentAdmin(admin.ModelAdmin):
    list_display = ['teacher', 'subject_group', 'weekly_hours', 'is_main_teacher', 'status', 'assignment_date']
    list_filter = ['status', 'is_main_teacher', 'assignment_date']
    search_fields = ['teacher__user__username', 'subject_group__subject__name']
    ordering = ['-assignment_date']
    raw_id_fields = ['teacher', 'subject_group']


@admin.register(TeacherRole)
class TeacherRoleAdmin(admin.ModelAdmin):
    list_display = ['name', 'required_free_hours_per_week', 'priority', 'icon']
    list_filter = ['priority']
    ordering = ['-priority']


@admin.register(TeacherRoleAssignment)
class TeacherRoleAssignmentAdmin(admin.ModelAdmin):
    list_display = ['teacher', 'role', 'academic_period', 'total_free_hours', 'is_active']
    list_filter = ['role', 'academic_period', 'is_active']
    search_fields = ['teacher__user__username']
    raw_id_fields = ['teacher']

    def total_free_hours(self, obj):
        return obj.get_total_free_hours()
    total_free_hours.short_description = 'Total Free Hours'


@admin.register(TeacherPreferences)
class TeacherPreferencesAdmin(admin.ModelAdmin):
    list_display = ['teacher', 'academic_period', 'max_hours_per_week', 'max_daily_hours', 'max_consecutive_hours', 'color_display']
    list_filter = ['academic_period']
    search_fields = ['teacher__user__username']
    raw_id_fields = ['teacher']
    filter_horizontal = ['unavailable_time_slots']

    def color_display(self, obj):
        return format_html(
            '<div style="width: 30px; height: 20px; background-color: {}; border: 1px solid #ccc;"></div>',
            obj.color_code
        )
    color_display.short_description = 'Color'


@admin.register(ScheduleConfiguration)
class ScheduleConfigurationAdmin(admin.ModelAdmin):
    list_display = ['academic_period', 'algorithm', 'max_execution_time_seconds', 'optimization_priority']
    list_filter = ['algorithm', 'optimization_priority']
    fieldsets = (
        ('Período Académico', {
            'fields': ('academic_period',)
        }),
        ('Algoritmo', {
            'fields': ('algorithm', 'max_execution_time_seconds', 'optimization_priority')
        }),
        ('Restricciones Duras', {
            'fields': (
                'allow_teacher_gaps',
                'max_daily_hours_per_teacher',
                'max_daily_hours_per_group',
                'max_classes_per_day',
                'min_break_between_classes',
            )
        }),
        ('Pesos de Optimización', {
            'fields': (
                'weight_minimize_teacher_gaps',
                'weight_teacher_preferences',
                'weight_balanced_distribution',
                'weight_classroom_proximity',
                'weight_minimize_daily_changes',
            )
        }),
    )


@admin.register(ScheduleGeneration)
class ScheduleGenerationAdmin(admin.ModelAdmin):
    list_display = ['id', 'academic_period', 'status', 'success_rate_display', 'execution_time_display', 'started_at', 'is_published']
    list_filter = ['status', 'is_published', 'academic_period', 'started_at']
    search_fields = ['academic_period__name']
    readonly_fields = [
        'status', 'started_at', 'completed_at', 'execution_time_seconds',
        'total_sessions_to_schedule', 'sessions_scheduled', 'success_rate',
        'conflicts_detected', 'warnings', 'optimization_score',
        'algorithm_used', 'algorithm_parameters', 'created_by'
    ]

    fieldsets = (
        ('Información General', {
            'fields': ('academic_period', 'configuration', 'status', 'created_by')
        }),
        ('Tiempos', {
            'fields': ('started_at', 'completed_at', 'execution_time_seconds')
        }),
        ('Resultados', {
            'fields': (
                'total_sessions_to_schedule',
                'sessions_scheduled',
                'success_rate',
                'optimization_score',
            )
        }),
        ('Algoritmo', {
            'fields': ('algorithm_used', 'algorithm_parameters')
        }),
        ('Problemas', {
            'fields': ('conflicts_detected', 'warnings')
        }),
        ('Publicación', {
            'fields': ('is_published', 'notes')
        }),
    )

    def success_rate_display(self, obj):
        color = 'green' if obj.success_rate >= 80 else ('orange' if obj.success_rate >= 50 else 'red')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
            color, obj.success_rate
        )
    success_rate_display.short_description = 'Success Rate'

    def execution_time_display(self, obj):
        if obj.execution_time_seconds:
            return f"{obj.execution_time_seconds:.2f}s"
        return "-"
    execution_time_display.short_description = 'Execution Time'


@admin.register(ScheduleSession)
class ScheduleSessionAdmin(admin.ModelAdmin):
    list_display = [
        'schedule_generation', 'subject_group', 'teacher',
        'time_slot', 'classroom', 'duration_slots', 'session_type', 'is_locked'
    ]
    list_filter = [
        'schedule_generation__academic_period',
        'session_type',
        'is_locked',
        'time_slot__day_of_week'
    ]
    search_fields = [
        'subject_group__subject__name',
        'teacher__user__username',
        'classroom__code'
    ]
    ordering = ['time_slot__day_of_week', 'time_slot__start_time']
    raw_id_fields = [
        'schedule_generation',
        'teacher_assignment',
        'subject_group',
        'teacher',
        'time_slot',
        'classroom'
    ]


@admin.register(BlockedTimeSlot)
class BlockedTimeSlotAdmin(admin.ModelAdmin):
    list_display = ['time_slot', 'block_type', 'academic_period', 'career', 'classroom', 'reason', 'is_active']
    list_filter = ['block_type', 'is_active', 'academic_period', 'time_slot__day_of_week']
    search_fields = ['reason', 'notes', 'career__name', 'classroom__code']
    ordering = ['time_slot__day_of_week', 'time_slot__start_time']
    raw_id_fields = ['time_slot', 'career', 'classroom']
    readonly_fields = ['created_at', 'updated_at', 'created_by']

    fieldsets = (
        ('Franja Horaria', {
            'fields': ('academic_period', 'time_slot')
        }),
        ('Tipo de Bloqueo', {
            'fields': ('block_type', 'career', 'classroom')
        }),
        ('Detalles', {
            'fields': ('reason', 'notes', 'is_active')
        }),
        ('Auditoría', {
            'fields': ('created_at', 'updated_at', 'created_by'),
            'classes': ('collapse',)
        }),
    )
