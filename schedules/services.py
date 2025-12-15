"""
Schedule Generator Service - CSP (Constraint Satisfaction Problem) Solver
Author: Academix Team
Description: Automatic schedule generation using backtracking algorithm with constraint propagation
"""

import logging
import time
import math
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Set, Tuple, Optional, Any
from django.db import transaction
from django.utils import timezone

from .models import (
    TimeSlot, TeacherAssignment, ScheduleConfiguration,
    ScheduleGeneration, ScheduleSession, TeacherAvailability, TeacherPreferences,
    TeacherRoleAssignment, BlockedTimeSlot
)
from academic.models import AcademicPeriod, Classroom
from users.models import Teacher
from enrollment.models import SubjectGroup

logger = logging.getLogger(__name__)


class ScheduleGeneratorService:
    """
    Main schedule generation service using CSP algorithms
    Implements backtracking with forward checking and constraint propagation
    """

    def __init__(self, academic_period_id: int, config: ScheduleConfiguration, user, career=None, global_teacher_schedule=None, career_assignments=None, batch_id=None):
        self.period = AcademicPeriod.objects.get(id=academic_period_id)
        self.config = config
        self.user = user
        self.generation = None
        self.career = career  # Carrera específica (opcional)
        self.batch_id = batch_id  # ID del lote de generación
        self.global_teacher_schedule = global_teacher_schedule if global_teacher_schedule is not None else defaultdict(set)

        # Load data
        self.time_slots = list(TimeSlot.objects.filter(
            academic_period=self.period,
            is_active=True
        ).order_by('day_of_week', 'start_time'))

        # Create time slot lookup cache (id -> time_slot object)
        self.time_slot_cache = {ts.id: ts for ts in self.time_slots}

        self.classrooms = list(Classroom.objects.filter(is_active=True))

        self.teachers = list(Teacher.objects.filter(status='active'))

        # Load teacher availability restrictions
        self.teacher_availability = {}
        for availability in TeacherAvailability.objects.filter(
            academic_period=self.period,
            is_active=True
        ).select_related('teacher').prefetch_related('available_time_slots'):
            self.teacher_availability[availability.teacher.id] = availability

        # Load blocked time slots
        self.blocked_time_slots = defaultdict(set)  # time_slot_id -> set of (block_type, career_id, classroom_id)
        for blocked in BlockedTimeSlot.objects.filter(
            academic_period=self.period,
            is_active=True
        ).select_related('time_slot', 'career', 'classroom'):
            self.blocked_time_slots[blocked.time_slot.id].add((
                blocked.block_type,
                blocked.career_id,
                blocked.classroom_id
            ))

        # Get list of unavailable teachers
        unavailable_teacher_ids = [
            t_id for t_id, avail in self.teacher_availability.items()
            if avail.availability_type == 'unavailable'
        ]

        # Filter out assignments for unavailable teachers
        if career_assignments is not None:
            # Use provided career assignments
            all_assignments = career_assignments
        else:
            # Load all assignments for the period
            all_assignments = list(TeacherAssignment.objects.filter(
                subject_group__academic_period=self.period,
                status='active'
            ).select_related('subject_group__subject', 'teacher', 'subject_group'))

        self.assignments = [
            assignment for assignment in all_assignments
            if assignment.teacher.id not in unavailable_teacher_ids
        ]

        # Log excluded assignments
        excluded_count = len(all_assignments) - len(self.assignments)
        if excluded_count > 0:
            logger.info(f"Excluded {excluded_count} assignments from unavailable teachers")

        # Data structures for CSP
        self.domains = {}  # Assignment ID -> List of (timeslot, classroom) tuples
        self.schedule = {}  # Assignment ID -> (timeslot, classroom)

        # Tracking structures for conflict detection
        self.teacher_schedule = defaultdict(set)  # Teacher ID -> Set of timeslot IDs
        self.classroom_schedule = defaultdict(set)  # Classroom ID -> Set of timeslot IDs
        self.group_schedule = defaultdict(set)  # Group ID -> Set of timeslot IDs

        # NEW: Track classes by student cohort (career, year, group_code, day) -> count
        # This ensures students in "1st year Group A" don't exceed max classes per day
        self.student_cohort_schedule = defaultdict(int)  # (career_id, year, group_code, day) -> count

        # Results tracking
        self.conflicts = []
        self.warnings = []
        self.stats = {
            'nodes_explored': 0,
            'backtracks': 0,
            'constraint_checks': 0
        }

    def generate_schedule(self) -> ScheduleGeneration:
        """
        Main entry point for schedule generation
        Returns a ScheduleGeneration object with results
        """
        logger.info(f"Starting schedule generation for {self.period}")
        start_time = time.time()

        # Create generation record
        self.generation = ScheduleGeneration.objects.create(
            batch_id=self.batch_id,
            academic_period=self.period,
            career=self.career,
            configuration=self.config,
            status='running',
            total_sessions_to_schedule=self._calculate_total_sessions(),
            algorithm_used=self.config.algorithm,
            created_by=self.user
        )

        try:
            # Phase 1: Precondition validation
            logger.info("Phase 1: Validating preconditions...")
            if not self._validate_preconditions():
                self._finalize_generation(status='failed')
                return self.generation

            # Phase 2: Initialize domains
            logger.info("Phase 2: Initializing domains...")
            self._initialize_domains()

            # Phase 3: Order assignments (Most Constrained First heuristic)
            logger.info("Phase 3: Ordering assignments...")
            ordered_assignments = self._order_assignments_by_constraint()

            # Phase 4: Execute backtracking search
            logger.info("Phase 4: Running CSP backtracking algorithm...")
            success = self._backtracking_search(ordered_assignments, 0, start_time)

            execution_time = time.time() - start_time
            logger.info(f"Execution completed in {execution_time:.2f}s")

            # Phase 5: Save results
            if success:
                logger.info("Phase 5: Saving successful schedule...")
                self._save_schedule_sessions()
                self._calculate_optimization_score()
                self._finalize_generation(status='completed', execution_time=execution_time)
            else:
                logger.warning("Schedule generation failed or incomplete")
                self._analyze_failure_reasons()
                status = 'partial' if self.schedule else 'failed'
                self._finalize_generation(status=status, execution_time=execution_time)

        except Exception as e:
            logger.error(f"Error during schedule generation: {str(e)}", exc_info=True)
            self._finalize_generation(status='failed', error=str(e))

        return self.generation

    def _calculate_total_sessions(self) -> int:
        """Calculate total number of sessions to schedule"""
        return sum(assignment.weekly_hours for assignment in self.assignments)

    def _validate_preconditions(self) -> bool:
        """
        Validate that schedule generation is feasible
        Checks ALL conditions and accumulates ALL conflicts before returning
        Returns False if critical conflicts are detected
        """
        logger.info("Validating preconditions...")
        has_blocking_conflicts = False

        # Validation 1: Check if there are enough time slots
        total_required_hours = sum(a.weekly_hours for a in self.assignments)
        total_available_slots = len(self.time_slots) * len(self.classrooms)

        if total_required_hours > total_available_slots:
            self._add_conflict({
                'type': 'insufficient_time_slots',
                'severity': 'critical',
                'entity': 'System',
                'entity_name': 'Sistema',
                'description': f'Se requieren {total_required_hours} horas pero solo hay {total_available_slots} franjas disponibles',
                'details': {
                    'required': total_required_hours,
                    'available': total_available_slots,
                    'deficit': total_required_hours - total_available_slots
                },
                'possible_solutions': [
                    'Añadir más franjas horarias al día',
                    'Añadir más aulas',
                    'Reducir horas de asignaturas',
                    'Extender a más días de la semana'
                ],
                'blocking': True
            })
            has_blocking_conflicts = True
            logger.warning("✗ Insufficient time slots detected")

        # Validation 2: Check teacher workload (CHECK ALL TEACHERS)
        teacher_conflicts_count = 0
        for teacher in self.teachers:
            teacher_assignments = [a for a in self.assignments if a.teacher_id == teacher.id]
            if not teacher_assignments:
                continue

            required_hours = sum(a.weekly_hours for a in teacher_assignments)

            # Get teacher preferences
            try:
                prefs = TeacherPreferences.objects.get(teacher=teacher, academic_period=self.period)
                max_hours = prefs.max_hours_per_week
            except TeacherPreferences.DoesNotExist:
                max_hours = 20  # Default

            # Get role non-teaching hours
            role_hours = sum(
                tra.get_total_free_hours()
                for tra in TeacherRoleAssignment.objects.filter(
                    teacher=teacher,
                    academic_period=self.period,
                    is_active=True
                )
            )

            total_required = required_hours + role_hours

            if total_required > max_hours:
                self._add_conflict({
                    'type': 'teacher_overload',
                    'severity': 'critical',
                    'entity': 'Teacher',
                    'entity_id': teacher.id,
                    'entity_name': teacher.user.get_full_name(),
                    'description': f'Requiere {total_required}h ({required_hours}h lectivas + {role_hours}h no lectivas) pero max es {max_hours}h',
                    'details': {
                        'teaching_hours': required_hours,
                        'administrative_hours': role_hours,
                        'total_required': total_required,
                        'max_allowed': max_hours,
                        'deficit': total_required - max_hours
                    },
                    'affected_subjects': [a.subject_group.subject.name for a in teacher_assignments],
                    'possible_solutions': [
                        f'Aumentar max_hours_per_week del profesor a {total_required}',
                        'Asignar otro profesor a alguna asignatura',
                        'Reducir horas de roles administrativos'
                    ],
                    'blocking': True
                })
                teacher_conflicts_count += 1
                has_blocking_conflicts = True
                logger.warning(f"✗ Teacher overload: {teacher.user.get_full_name()} ({total_required}h required, {max_hours}h max)")

        if teacher_conflicts_count > 0:
            logger.warning(f"✗ Found {teacher_conflicts_count} teacher(s) with workload conflicts")

        # Validation 3: Check classroom capacity (CHECK ALL ASSIGNMENTS)
        classroom_conflicts_count = 0
        for assignment in self.assignments:
            group_size = assignment.subject_group.max_capacity
            suitable_classrooms = [
                c for c in self.classrooms
                if c.capacity >= group_size
            ]

            if not suitable_classrooms:
                self._add_conflict({
                    'type': 'no_suitable_classroom',
                    'severity': 'critical',
                    'entity': 'Assignment',
                    'entity_id': assignment.id,
                    'entity_name': f'{assignment.subject_group.subject.name} - {assignment.subject_group.code}',
                    'description': f'Grupo de {group_size} estudiantes sin aula adecuada',
                    'details': {
                        'group_size': group_size,
                        'largest_classroom': max(c.capacity for c in self.classrooms) if self.classrooms else 0
                    },
                    'possible_solutions': [
                        f'Añadir aulas con capacidad ≥{group_size}',
                        'Dividir el grupo en subgrupos'
                    ],
                    'blocking': True
                })
                classroom_conflicts_count += 1
                has_blocking_conflicts = True
                logger.warning(f"✗ No suitable classroom for: {assignment.subject_group.subject.name} (needs {group_size} capacity)")

        if classroom_conflicts_count > 0:
            logger.warning(f"✗ Found {classroom_conflicts_count} assignment(s) without suitable classrooms")

        # Validation 4: Check teacher qualifications (CHECK ALL ASSIGNMENTS)
        qualification_conflicts_count = 0
        for assignment in self.assignments:
            teacher = assignment.teacher
            subject = assignment.subject_group.subject

            # Check if teacher is qualified to teach this subject
            if not teacher.can_teach_subject(subject):
                self._add_conflict({
                    'type': 'teacher_not_qualified',
                    'severity': 'critical',
                    'entity': 'Assignment',
                    'entity_id': assignment.id,
                    'entity_name': f'{teacher.user.get_full_name()} - {subject.name}',
                    'description': f'El profesor {teacher.user.get_full_name()} no está calificado para impartir {subject.name}',
                    'details': {
                        'teacher_id': teacher.id,
                        'teacher_name': teacher.user.get_full_name(),
                        'subject_id': subject.id,
                        'subject_name': subject.name,
                        'subject_code': subject.code
                    },
                    'possible_solutions': [
                        f'Añadir la asignatura "{subject.name}" a las calificaciones del profesor',
                        f'Añadir la carrera correspondiente a las calificaciones del profesor',
                        'Asignar otro profesor calificado a esta asignatura'
                    ],
                    'blocking': True
                })
                qualification_conflicts_count += 1
                has_blocking_conflicts = True
                logger.warning(f"✗ Teacher not qualified: {teacher.user.get_full_name()} cannot teach {subject.name}")

        if qualification_conflicts_count > 0:
            logger.warning(f"✗ Found {qualification_conflicts_count} assignment(s) with unqualified teachers")

        # Summary
        if has_blocking_conflicts:
            total_conflicts = len(self.conflicts)
            logger.error(f"❌ Validation FAILED: {total_conflicts} blocking conflict(s) detected")
            logger.error("Please resolve ALL conflicts before attempting to generate the schedule")
            return False

        logger.info("✅ All preconditions validated successfully - no conflicts detected")
        return True

    def _initialize_domains(self):
        """
        Initialize possible domains for each assignment
        Domain = all possible (timeslot, classroom) combinations

        IMPORTANT: Each assignment needs multiple sessions based on weekly_hours
        We create a "session" for each hour needed
        """
        # Expand assignments into individual sessions
        self.session_assignments = []  # List of (assignment, session_number) tuples

        for assignment in self.assignments:
            # Create one session for each weekly hour
            for session_num in range(assignment.weekly_hours):
                self.session_assignments.append((assignment, session_num))

        logger.info(f"Expanded {len(self.assignments)} assignments into {len(self.session_assignments)} sessions")

        # Now create domains for each session
        for assignment, session_num in self.session_assignments:
            session_key = f"{assignment.id}_{session_num}"
            domain = []
            group_size = assignment.subject_group.max_capacity

            # Find suitable classrooms
            suitable_classrooms = [
                c for c in self.classrooms
                if c.capacity >= group_size
            ]

            # Create domain: all combinations of suitable classrooms and time slots
            for classroom in suitable_classrooms:
                for time_slot in self.time_slots:
                    domain.append((time_slot, classroom))

            self.domains[session_key] = domain

            if not domain:
                self._add_warning({
                    'type': 'empty_domain',
                    'entity': f'Session {session_key}',
                    'message': f'No valid slots for {assignment.subject_group.subject.name} session {session_num + 1}'
                })

    def _is_valid_assignment(self, assignment: TeacherAssignment,
                            time_slot: TimeSlot, classroom: Classroom) -> bool:
        """Check if assignment can be placed in this slot/classroom (hard constraints)"""
        self.stats['constraint_checks'] += 1

        teacher = assignment.teacher
        group = assignment.subject_group

        # Check if teacher is available (local schedule)
        if teacher.id in self.teacher_schedule:
            if time_slot.id in self.teacher_schedule[teacher.id]:
                return False

        # Check if teacher is available (global schedule across careers)
        if teacher.id in self.global_teacher_schedule:
            if time_slot.id in self.global_teacher_schedule[teacher.id]:
                return False

        # Check if classroom is available
        if classroom.id in self.classroom_schedule:
            if time_slot.id in self.classroom_schedule[classroom.id]:
                return False

        # Check if group is available
        if group.id in self.group_schedule:
            if time_slot.id in self.group_schedule[group.id]:
                return False

        # Check teacher availability restrictions (hard constraints)
        if teacher.id in self.teacher_availability:
            availability = self.teacher_availability[teacher.id]

            # Check if teacher can teach at this time slot
            if not availability.can_teach_at_time_slot(time_slot):
                return False

            # Check if teacher has reached max teaching hours
            if availability.max_teaching_hours is not None:
                current_hours = len(self.teacher_schedule.get(teacher.id, []))
                if current_hours >= availability.max_teaching_hours:
                    return False

        # Check teacher preferences (unavailable slots - soft constraints)
        try:
            prefs = TeacherPreferences.objects.get(teacher=teacher, academic_period=self.period)
            if time_slot in prefs.unavailable_time_slots.all():
                return False
        except TeacherPreferences.DoesNotExist:
            pass

        # Check max daily hours for teacher
        day = time_slot.day_of_week
        teacher_daily_hours = sum(
            1 for ts_id in self.teacher_schedule.get(teacher.id, [])
            if self.time_slot_cache.get(ts_id).day_of_week == day
        )
        if teacher_daily_hours >= self.config.max_daily_hours_per_teacher:
            return False

        # Check max classes per day for STUDENT COHORT (not just this subject group)
        # Students in the same year and group code take classes together across all subjects
        # We need to ensure they don't exceed max_classes_per_day across ALL their subjects

        # Get the career, year, and group code for this subject group
        subject = group.subject
        career_id = self.career.id if self.career else None
        year = subject.course_year
        group_code = group.code

        # Create cohort key: (career_id, year, group_code, day)
        cohort_key = (career_id, year, group_code, day)

        # Count classes already scheduled for this student cohort today
        cohort_classes_today = self.student_cohort_schedule[cohort_key]

        # Use max_classes_per_day as the primary limit (this is clearer - counts sessions/classes, not hours)
        max_classes_allowed = self.config.max_classes_per_day

        # Debug logging - log details about what's being checked
        if cohort_classes_today >= max_classes_allowed - 2:  # Log when getting close to limit
            logger.info(
                f"⚠️  Student cohort (Year {year} {group_code}) day {['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][day]}: "
                f"{cohort_classes_today} classes already assigned (trying to add {subject.name} at {time_slot.start_time}), "
                f"max allowed: {max_classes_allowed} classes/day"
            )

        if cohort_classes_today >= max_classes_allowed:
            logger.info(f"   ❌ REJECTED: Would exceed max of {max_classes_allowed} classes/day for student cohort")
            return False

        # Check max sessions per subject per day (prevent scheduling all weekly hours in one day)
        # Count how many sessions of THIS SPECIFIC assignment are already scheduled today
        assignment_sessions_today = 0
        for session_key in self.schedule.keys():
            if session_key.startswith(f"{assignment.id}_"):
                scheduled_slot, _, _ = self.schedule[session_key]
                if scheduled_slot.day_of_week == day:
                    assignment_sessions_today += 1

        # Use configured limit (default: 2 sessions per subject per day)
        max_sessions_per_subject = getattr(self.config, 'max_sessions_per_subject_per_day', 2)
        if assignment_sessions_today >= max_sessions_per_subject:
            logger.info(
                f"   ❌ REJECTED: Subject {assignment.subject_group.subject.name} already has "
                f"{assignment_sessions_today} sessions on {['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][day]}, "
                f"max allowed: {max_sessions_per_subject} sessions/day per subject"
            )
            return False

        # Check if time slot is blocked
        if time_slot.id in self.blocked_time_slots:
            for block_type, career_id, classroom_id in self.blocked_time_slots[time_slot.id]:
                # Global blocks affect everyone
                if block_type == 'global':
                    return False
                # Career-specific blocks
                elif block_type == 'career' and self.career and career_id == self.career.id:
                    return False
                # Classroom-specific blocks
                elif block_type == 'classroom' and classroom_id == classroom.id:
                    return False

        # Check minimum break between classes (for teacher and group)
        if self.config.min_break_between_classes > 0:
            # Check for teacher
            if teacher.id in self.teacher_schedule:
                for existing_slot_id in self.teacher_schedule[teacher.id]:
                    existing_slot = self.time_slot_cache.get(existing_slot_id)
                    if existing_slot and existing_slot.day_of_week == time_slot.day_of_week:
                        # Calculate time difference in minutes
                        if not self._has_minimum_break(existing_slot, time_slot, self.config.min_break_between_classes):
                            return False

            # Check for group
            if group.id in self.group_schedule:
                for existing_slot_id in self.group_schedule[group.id]:
                    existing_slot = self.time_slot_cache.get(existing_slot_id)
                    if existing_slot and existing_slot.day_of_week == time_slot.day_of_week:
                        # Calculate time difference in minutes
                        if not self._has_minimum_break(existing_slot, time_slot, self.config.min_break_between_classes):
                            return False

        return True

    def _has_minimum_break(self, slot1: TimeSlot, slot2: TimeSlot, min_break_minutes: int) -> bool:
        """
        Check if there is minimum break time between two time slots
        Returns True if slots don't conflict or have enough break time
        """
        from datetime import datetime, timedelta

        # Convert times to datetime for easy comparison
        dummy_date = datetime(2000, 1, 1)
        slot1_start = datetime.combine(dummy_date, slot1.start_time)
        slot1_end = datetime.combine(dummy_date, slot1.end_time)
        slot2_start = datetime.combine(dummy_date, slot2.start_time)
        slot2_end = datetime.combine(dummy_date, slot2.end_time)

        # If slots don't overlap, check break time
        if slot1_end <= slot2_start:
            # slot1 ends before slot2 starts
            break_time = (slot2_start - slot1_end).total_seconds() / 60
            return break_time >= min_break_minutes
        elif slot2_end <= slot1_start:
            # slot2 ends before slot1 starts
            break_time = (slot1_start - slot2_end).total_seconds() / 60
            return break_time >= min_break_minutes
        else:
            # Slots overlap - not allowed
            return False

    def _order_assignments_by_constraint(self) -> List[Tuple[TeacherAssignment, int]]:
        """
        Order sessions using Most Constrained First heuristic
        Sessions with fewer valid options are scheduled first
        """
        return sorted(
            self.session_assignments,
            key=lambda sa: len(self.domains.get(f"{sa[0].id}_{sa[1]}", []))
        )

    def _backtracking_search(self, sessions: List[Tuple[TeacherAssignment, int]],
                            index: int, start_time: float) -> bool:
        """
        Main CSP backtracking algorithm with forward checking
        Now works with individual sessions instead of assignments
        """
        # Check timeout
        if time.time() - start_time > self.config.max_execution_time_seconds:
            logger.warning("Timeout reached")
            return False

        # Base case: all sessions scheduled
        if index >= len(sessions):
            return True

        # Get current session (assignment, session_number)
        assignment, session_num = sessions[index]
        session_key = f"{assignment.id}_{session_num}"
        self.stats['nodes_explored'] += 1

        # Get domain for this session
        domain = self.domains.get(session_key, [])

        # Try each value in domain
        for time_slot, classroom in domain:
            # Check if still valid (forward checking)
            if not self._is_valid_assignment(assignment, time_slot, classroom):
                continue

            # Assign
            self.schedule[session_key] = (time_slot, classroom, assignment)
            self.teacher_schedule[assignment.teacher.id].add(time_slot.id)
            self.classroom_schedule[classroom.id].add(time_slot.id)
            self.group_schedule[assignment.subject_group.id].add(time_slot.id)

            # Update student cohort schedule
            subject = assignment.subject_group.subject
            career_id = self.career.id if self.career else None
            year = subject.course_year
            group_code = assignment.subject_group.code
            day = time_slot.day_of_week
            cohort_key = (career_id, year, group_code, day)
            self.student_cohort_schedule[cohort_key] += 1

            # Recurse
            if self._backtracking_search(sessions, index + 1, start_time):
                return True

            # Backtrack
            self.stats['backtracks'] += 1
            del self.schedule[session_key]
            self.teacher_schedule[assignment.teacher.id].discard(time_slot.id)
            self.classroom_schedule[classroom.id].discard(time_slot.id)
            self.group_schedule[assignment.subject_group.id].discard(time_slot.id)

            # Restore student cohort schedule
            self.student_cohort_schedule[cohort_key] -= 1

        # No valid assignment found
        return False

    @transaction.atomic
    def _save_schedule_sessions(self):
        """Save generated schedule to database"""
        logger.info("Saving schedule sessions to database...")

        for session_key, (time_slot, classroom, assignment) in self.schedule.items():
            ScheduleSession.objects.create(
                schedule_generation=self.generation,
                teacher_assignment=assignment,
                subject_group=assignment.subject_group,
                teacher=assignment.teacher,
                time_slot=time_slot,
                classroom=classroom,
                duration_slots=1,
                session_type='lecture'
            )

        self.generation.sessions_scheduled = len(self.schedule)
        self.generation.save()
        logger.info(f"✓ Saved {len(self.schedule)} sessions")

        # Post-validation: verify no group exceeds max daily hours
        self._validate_final_schedule()

    def _validate_final_schedule(self):
        """
        Post-generation validation to verify constraints are met
        Checks that no group has more classes per day than allowed
        """
        logger.info("Validating final schedule constraints...")

        # Use max_classes_per_day as the limit (counts number of classes/sessions, not hours)
        max_classes_allowed = self.config.max_classes_per_day

        violations = []
        group_sessions_by_day = defaultdict(lambda: defaultdict(list))

        # Group all sessions by group and day
        for session_key, (time_slot, classroom, assignment) in self.schedule.items():
            group_id = assignment.subject_group.id
            day = time_slot.day_of_week
            group_sessions_by_day[group_id][day].append({
                'time': time_slot.start_time,
                'subject': assignment.subject_group.subject.name,
                'group_code': assignment.subject_group.code
            })

        # Check for violations
        for group_id, days_dict in group_sessions_by_day.items():
            for day, sessions in days_dict.items():
                if len(sessions) > max_classes_allowed:
                    group_code = sessions[0]['group_code']
                    day_name = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][day]
                    violations.append({
                        'group': group_code,
                        'day': day_name,
                        'sessions_count': len(sessions),
                        'max_allowed': max_classes_allowed,
                        'excess': len(sessions) - max_classes_allowed,
                        'times': [s['time'].strftime('%H:%M') for s in sorted(sessions, key=lambda x: x['time'])]
                    })

        if violations:
            logger.error(f"❌ CONSTRAINT VIOLATIONS DETECTED! {len(violations)} violation(s):")
            for v in violations:
                logger.error(
                    f"   Group {v['group']} on {v['day']}: {v['sessions_count']} classes "
                    f"(max: {v['max_allowed']}) - Times: {', '.join(v['times'])}"
                )
            # Add violations to warnings
            for v in violations:
                self._add_warning({
                    'type': 'max_daily_hours_violation',
                    'entity': f"Group {v['group']}",
                    'message': f"{v['group']} has {v['sessions_count']} classes on {v['day']} (max: {v['max_allowed']})",
                    'details': v
                })
        else:
            logger.info("✅ All groups respect max daily hours constraint")

    def _calculate_optimization_score(self):
        """Calculate quality score based on soft constraints"""
        if not self.schedule:
            return 0.0

        score = 100.0  # Start with perfect score
        penalties = 0

        # Penalty 1: Teacher gaps (minimize empty periods between classes)
        for teacher_id, slots in self.teacher_schedule.items():
            slots_by_day = defaultdict(list)
            for slot_id in slots:
                slot = self.time_slot_cache.get(slot_id)
                if slot:
                    slots_by_day[slot.day_of_week].append(slot)

            for day, day_slots in slots_by_day.items():
                sorted_slots = sorted(day_slots, key=lambda s: s.start_time)
                gaps = len(sorted_slots) - 1
                if gaps > 0 and not self.config.allow_teacher_gaps:
                    penalties += gaps * self.config.weight_minimize_teacher_gaps

        # Penalty 2: Unbalanced distribution (balance workload across the week)
        sessions_per_day = defaultdict(int)
        for time_slot, classroom, assignment in self.schedule.values():
            sessions_per_day[time_slot.day_of_week] += 1

        if sessions_per_day:
            avg = sum(sessions_per_day.values()) / len(sessions_per_day)
            variance = sum((count - avg) ** 2 for count in sessions_per_day.values()) / len(sessions_per_day)
            penalties += variance * self.config.weight_balanced_distribution

        # Penalty 3: Teacher preferences (prioritize preferred time slots)
        if self.config.weight_teacher_preferences > 0:
            teacher_prefs = TeacherPreferences.objects.filter(
                academic_period=self.period
            ).select_related('teacher').prefetch_related('unavailable_time_slots')

            for pref in teacher_prefs:
                teacher_id = pref.teacher.id
                if teacher_id in self.teacher_schedule:
                    for slot_id in self.teacher_schedule[teacher_id]:
                        slot = self.time_slot_cache.get(slot_id)
                        if not slot:
                            continue

                        # Penalize if slot is in unavailable time slots
                        if pref.unavailable_time_slots.filter(id=slot_id).exists():
                            penalties += self.config.weight_teacher_preferences * 2

                        # Penalize if outside preferred time range
                        if pref.preferred_start_time and slot.start_time < pref.preferred_start_time:
                            penalties += self.config.weight_teacher_preferences * 0.5
                        if pref.preferred_end_time and slot.end_time > pref.preferred_end_time:
                            penalties += self.config.weight_teacher_preferences * 0.5

        # Penalty 4: Classroom proximity (minimize classroom changes for same teacher on same day)
        if self.config.weight_classroom_proximity > 0:
            teacher_classrooms_by_day = defaultdict(lambda: defaultdict(set))

            for time_slot, classroom, assignment in self.schedule.values():
                teacher_id = assignment.teacher.id
                day = time_slot.day_of_week
                teacher_classrooms_by_day[teacher_id][day].add(classroom.id)

            # Penalize teachers with multiple classrooms on the same day
            for teacher_id, days in teacher_classrooms_by_day.items():
                for day, classrooms in days.items():
                    if len(classrooms) > 1:
                        # Penalty increases with number of different classrooms
                        penalties += (len(classrooms) - 1) * self.config.weight_classroom_proximity

        # Penalty 5: Minimize daily classroom changes (reduce transitions)
        if self.config.weight_minimize_daily_changes > 0:
            teacher_schedule_details = defaultdict(lambda: defaultdict(list))

            for time_slot, classroom, assignment in self.schedule.values():
                teacher_id = assignment.teacher.id
                day = time_slot.day_of_week
                teacher_schedule_details[teacher_id][day].append({
                    'time_slot': time_slot,
                    'classroom': classroom
                })

            # Count classroom transitions for each teacher on each day
            for teacher_id, days in teacher_schedule_details.items():
                for day, sessions in days.items():
                    # Sort sessions by time
                    sorted_sessions = sorted(sessions, key=lambda s: s['time_slot'].start_time)

                    # Count transitions between different classrooms
                    transitions = 0
                    for i in range(len(sorted_sessions) - 1):
                        if sorted_sessions[i]['classroom'].id != sorted_sessions[i+1]['classroom'].id:
                            transitions += 1

                    penalties += transitions * self.config.weight_minimize_daily_changes

        # Calculate final score
        max_possible_penalties = len(self.schedule) * 10
        score = max(0, 100 - (penalties / max_possible_penalties * 100))

        self.generation.optimization_score = round(score, 2)
        self.generation.save()
        logger.info(f"✓ Optimization score: {score:.2f}/100")
        logger.info(f"   Total penalties: {penalties:.2f}")

    def _analyze_failure_reasons(self):
        """Analyze why schedule generation failed"""
        logger.info("Analyzing failure reasons...")

        # Check which sessions couldn't be scheduled
        scheduled_sessions_by_assignment = defaultdict(int)
        for session_key in self.schedule.keys():
            assignment_id = int(session_key.split('_')[0])
            scheduled_sessions_by_assignment[assignment_id] += 1

        for assignment in self.assignments:
            scheduled = scheduled_sessions_by_assignment.get(assignment.id, 0)
            required = assignment.weekly_hours

            if scheduled < required:
                self._add_conflict({
                    'type': 'incomplete_assignment',
                    'severity': 'high',
                    'entity': 'Assignment',
                    'entity_id': assignment.id,
                    'entity_name': f'{assignment.subject_group.subject.name} - {assignment.subject_group.code}',
                    'description': f'Solo se pudieron asignar {scheduled} de {required} sesiones',
                    'details': {
                        'teacher': assignment.teacher.user.get_full_name(),
                        'sessions_scheduled': scheduled,
                        'sessions_required': required,
                        'sessions_missing': required - scheduled
                    },
                    'blocking': False
                })

    def _finalize_generation(self, status: str, execution_time: float = None, error: str = None):
        """Finalize generation record with results"""
        self.generation.status = status
        self.generation.completed_at = timezone.now()

        if execution_time:
            self.generation.execution_time_seconds = execution_time

        self.generation.conflicts_detected = self.conflicts
        self.generation.warnings = self.warnings
        self.generation.calculate_success_rate()

        if error:
            self.generation.notes = f"Error: {error}"

        self.generation.algorithm_parameters = {
            'stats': self.stats,
            'config': {
                'algorithm': self.config.algorithm,
                'max_time': self.config.max_execution_time_seconds,
                'allow_gaps': self.config.allow_teacher_gaps
            }
        }

        self.generation.save()
        logger.info(f"Generation finalized with status: {status}")

    def _add_conflict(self, conflict: Dict[str, Any]):
        """Add a conflict to the list"""
        self.conflicts.append(conflict)
        logger.warning(f"Conflict: {conflict['type']} - {conflict['description']}")

    def _add_warning(self, warning: Dict[str, Any]):
        """Add a warning to the list"""
        self.warnings.append(warning)
        logger.info(f"Warning: {warning.get('type')} - {warning.get('message')}")

    @staticmethod
    def format_conflict(conflict: Dict[str, Any]) -> str:
        """
        Formatea un conflicto de manera legible en lugar de JSON
        """
        lines = []

        # Encabezado con severidad
        severity_emoji = {
            'critical': '🔴',
            'high': '🟠',
            'medium': '🟡',
            'low': '🟢'
        }
        emoji = severity_emoji.get(conflict.get('severity', 'medium'), '⚠️')

        # Título
        entity_name = conflict.get('entity_name', conflict.get('entity', 'Sistema'))
        lines.append(f"\n{emoji} CONFLICTO - {entity_name}")
        lines.append("─" * 60)

        # Descripción principal
        lines.append(f"📋 {conflict.get('description', 'Sin descripción')}")

        # Detalles específicos según el tipo
        if 'details' in conflict:
            details = conflict['details']
            lines.append("\n📊 Detalles:")

            if conflict.get('type') == 'insufficient_time_slots':
                lines.append(f"   • Horas requeridas: {details.get('required', 0)}")
                lines.append(f"   • Franjas disponibles: {details.get('available', 0)}")
                lines.append(f"   • Déficit: {details.get('deficit', 0)} horas")

            elif conflict.get('type') == 'teacher_overload':
                lines.append(f"   • Horas lectivas: {details.get('teaching_hours', 0)}h")
                if details.get('administrative_hours', 0) > 0:
                    lines.append(f"   • Horas administrativas: {details.get('administrative_hours', 0)}h")
                lines.append(f"   • Total requerido: {details.get('total_required', 0)}h")
                lines.append(f"   • Máximo permitido: {details.get('max_allowed', 0)}h")
                lines.append(f"   • Exceso: {details.get('deficit', 0)}h")

            elif conflict.get('type') == 'teacher_unavailable':
                lines.append(f"   • Horas asignadas: {details.get('assigned_hours', 0)}h")
                lines.append(f"   • Razón: {details.get('reason', 'No especificada')}")

        # Asignaturas afectadas
        if 'affected_subjects' in conflict:
            subjects = conflict['affected_subjects']
            if subjects:
                lines.append("\n📚 Asignaturas afectadas:")
                for subject in subjects[:5]:  # Limitar a 5
                    lines.append(f"   • {subject}")
                if len(subjects) > 5:
                    lines.append(f"   ... y {len(subjects) - 5} más")

        # Soluciones posibles
        if 'possible_solutions' in conflict:
            solutions = conflict['possible_solutions']
            if solutions:
                lines.append("\n💡 Soluciones posibles:")
                for i, solution in enumerate(solutions, 1):
                    lines.append(f"   {i}. {solution}")

        # Indicador de bloqueo
        if conflict.get('blocking'):
            lines.append("\n⛔ Este conflicto BLOQUEA la generación de horarios")

        lines.append("─" * 60)

        return "\n".join(lines)

    @staticmethod
    def format_conflicts_list(conflicts: List[Dict[str, Any]]) -> str:
        """
        Formatea una lista de conflictos de manera legible
        """
        if not conflicts:
            return "✅ No se detectaron conflictos"

        lines = []
        lines.append(f"\n{'='*60}")
        lines.append(f"⚠️  SE DETECTARON {len(conflicts)} CONFLICTO(S)")
        lines.append(f"{'='*60}")

        for i, conflict in enumerate(conflicts, 1):
            lines.append(f"\n[Conflicto {i}/{len(conflicts)}]")
            lines.append(ScheduleGeneratorService.format_conflict(conflict))

        return "\n".join(lines)
