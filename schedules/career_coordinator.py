"""
Career Schedule Coordinator
Author: Academix Team
Description: Coordinates schedule generation across multiple careers to avoid teacher conflicts
"""

import logging
import uuid
from collections import defaultdict
from typing import List, Dict, Set, Any
from django.utils import timezone

from .models import (
    ScheduleConfiguration, ScheduleGeneration, ScheduleSession,
    TeacherAssignment
)
from .services import ScheduleGeneratorService
from academic.models import AcademicPeriod, Career, StudyPlan, StudyPlanSubject

logger = logging.getLogger(__name__)


class CareerScheduleCoordinator:
    """
    Coordinador para generar horarios separados por carrera
    Asegura que no haya solapamientos de profesores entre carreras
    """

    def __init__(self, academic_period_id: int, config: ScheduleConfiguration, user):
        self.period_id = academic_period_id
        self.period = AcademicPeriod.objects.get(id=academic_period_id)
        self.config = config
        self.user = user

        # Generar batch_id único para esta ejecución
        self.batch_id = uuid.uuid4()

        # Tracker global de profesores para evitar solapamientos entre carreras
        self.global_teacher_schedule = defaultdict(set)  # Teacher ID -> Set of timeslot IDs

        # Resultados
        self.generations = []
        self.overall_success = True
        self.summary = {
            'batch_id': str(self.batch_id),
            'total_careers': 0,
            'successful_careers': 0,
            'failed_careers': 0,
            'total_sessions': 0
        }

    def generate_all_careers(self) -> List[ScheduleGeneration]:
        """
        Genera horarios para todas las carreras del período académico
        """
        logger.info(f"Iniciando generación de horarios por carrera para {self.period}")

        # Obtener todas las carreras activas que tienen asignaturas en este período
        careers = self._get_active_careers()
        self.summary['total_careers'] = len(careers)

        if not careers:
            logger.warning("No se encontraron carreras activas con asignaturas asignadas")
            return []

        logger.info(f"Generando horarios para {len(careers)} carreras")

        # Generar horario para cada carrera secuencialmente
        for career in careers:
            logger.info(f"\n{'='*80}")
            logger.info(f"Generando horario para carrera: {career.name} ({career.code})")
            logger.info(f"{'='*80}")

            try:
                generation = self._generate_career_schedule(career)
                self.generations.append(generation)

                if generation.status == 'completed':
                    self.summary['successful_careers'] += 1
                    self.summary['total_sessions'] += generation.sessions_scheduled
                else:
                    self.summary['failed_careers'] += 1
                    self.overall_success = False

            except Exception as e:
                logger.error(f"Error generando horario para {career.name}: {str(e)}", exc_info=True)
                self.summary['failed_careers'] += 1
                self.overall_success = False

        # Log resumen
        logger.info(f"\n{'='*80}")
        logger.info("RESUMEN DE GENERACIÓN DE HORARIOS POR CARRERA")
        logger.info(f"{'='*80}")
        logger.info(f"Total de carreras: {self.summary['total_careers']}")
        logger.info(f"Exitosas: {self.summary['successful_careers']}")
        logger.info(f"Fallidas: {self.summary['failed_careers']}")
        logger.info(f"Total de sesiones generadas: {self.summary['total_sessions']}")
        logger.info(f"{'='*80}\n")

        return self.generations

    def _get_active_careers(self) -> List[Career]:
        """
        Obtiene las carreras activas que tienen asignaturas en este período
        """
        # Obtener asignaciones activas del período
        assignments = TeacherAssignment.objects.filter(
            subject_group__academic_period=self.period,
            status='active'
        ).select_related('subject_group__subject')

        if not assignments.exists():
            return []

        # Obtener las asignaturas que tienen asignaciones
        subject_ids = set(assignments.values_list('subject_group__subject_id', flat=True))

        # Obtener las carreras a través de StudyPlanSubject
        study_plan_subjects = StudyPlanSubject.objects.filter(
            subject_id__in=subject_ids
        ).select_related('study_plan__career').distinct()

        career_ids = set(
            sps.study_plan.career.id
            for sps in study_plan_subjects
            if sps.study_plan.is_active and sps.study_plan.career.is_active
        )

        careers = Career.objects.filter(id__in=career_ids, is_active=True).order_by('code')

        return list(careers)

    def _generate_career_schedule(self, career: Career) -> ScheduleGeneration:
        """
        Genera el horario para una carrera específica
        """
        # Obtener planes de estudio activos de la carrera
        study_plans = StudyPlan.objects.filter(career=career, is_active=True)

        if not study_plans.exists():
            logger.warning(f"No se encontraron planes de estudio activos para {career.name}")
            return self._create_empty_generation(career, "No hay planes de estudio activos")

        # Obtener asignaturas de la carrera
        study_plan_subjects = StudyPlanSubject.objects.filter(
            study_plan__in=study_plans
        ).values_list('subject_id', flat=True).distinct()

        # Obtener asignaciones de profesores para estas asignaturas en este período
        career_assignments = TeacherAssignment.objects.filter(
            subject_group__academic_period=self.period,
            subject_group__subject_id__in=study_plan_subjects,
            status='active'
        ).select_related('subject_group__subject', 'teacher', 'subject_group')

        if not career_assignments.exists():
            logger.warning(f"No se encontraron asignaciones para {career.name}")
            return self._create_empty_generation(career, "No hay asignaciones de profesores")

        logger.info(f"Encontradas {career_assignments.count()} asignaciones para {career.name}")

        # Crear servicio generador para esta carrera
        generator = ScheduleGeneratorService(
            academic_period_id=self.period_id,
            config=self.config,
            user=self.user,
            career=career,
            global_teacher_schedule=self.global_teacher_schedule,
            career_assignments=list(career_assignments),
            batch_id=self.batch_id
        )

        # Generar horario
        generation = generator.generate_schedule()

        # Actualizar tracker global con las sesiones generadas
        if generation.status == 'completed':
            self._update_global_teacher_schedule(generation)

        return generation

    def _update_global_teacher_schedule(self, generation: ScheduleGeneration):
        """
        Actualiza el tracker global de profesores con las sesiones generadas
        """
        sessions = ScheduleSession.objects.filter(
            schedule_generation=generation
        ).select_related('teacher', 'time_slot')

        for session in sessions:
            self.global_teacher_schedule[session.teacher.id].add(session.time_slot.id)

        logger.info(f"Tracker global actualizado con {sessions.count()} sesiones")

    def _create_empty_generation(self, career: Career, reason: str) -> ScheduleGeneration:
        """
        Crea una generación vacía cuando no hay asignaciones para una carrera
        """
        generation = ScheduleGeneration.objects.create(
            batch_id=self.batch_id,
            academic_period=self.period,
            career=career,
            configuration=self.config,
            status='failed',
            total_sessions_to_schedule=0,
            sessions_scheduled=0,
            success_rate=0.0,
            algorithm_used=self.config.algorithm,
            created_by=self.user,
            notes=reason
        )
        generation.completed_at = timezone.now()
        generation.save()

        return generation
