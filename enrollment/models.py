from django.db import models
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from users.models import Student
from academic.models import Career, Subject, AcademicPeriod, StudyPlan

class CareerEnrollment(models.Model):
    """
    Model for student enrollment in careers
    """
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='career_enrollments')
    career = models.ForeignKey(Career, on_delete=models.CASCADE, related_name='enrollments')
    study_plan = models.ForeignKey(StudyPlan, on_delete=models.CASCADE, related_name='enrollments')
    enrollment_date = models.DateField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ('active', 'Activo'),
            ('completed', 'Completado'),
            ('dropped', 'Abandonado'),
            ('suspended', 'Suspendido'),
        ],
        default='active'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'career_enrollments'
        verbose_name = 'Career Enrollment'
        verbose_name_plural = 'Career Enrollments'
        unique_together = [['student', 'career', 'study_plan']]
        ordering = ['-enrollment_date']

    def __str__(self):
        return f"{self.student.user.get_full_name()} - {self.career.name}"


class SubjectGroup(models.Model):
    """
    Model for subject groups/sections
    """
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='groups')
    academic_period = models.ForeignKey(AcademicPeriod, on_delete=models.CASCADE, related_name='subject_groups')
    code = models.CharField(max_length=20)
    max_capacity = models.IntegerField(validators=[MinValueValidator(1)])
    current_enrollment = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'subject_groups'
        verbose_name = 'Subject Group'
        verbose_name_plural = 'Subject Groups'
        unique_together = [['subject', 'academic_period', 'code']]
        ordering = ['subject', 'code']

    def __str__(self):
        return f"{self.subject.code} - {self.code} ({self.academic_period.name})"

    def has_capacity(self):
        return self.current_enrollment < self.max_capacity


class SubjectEnrollment(models.Model):
    """
    Model for student enrollment in subjects
    """
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='subject_enrollments')
    subject_group = models.ForeignKey(SubjectGroup, on_delete=models.CASCADE, related_name='enrollments')
    career_enrollment = models.ForeignKey(CareerEnrollment, on_delete=models.CASCADE, related_name='subject_enrollments')
    enrollment_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ('enrolled', 'Inscrito'),
            ('dropped', 'Retirado'),
            ('completed', 'Completado'),
            ('failed', 'Reprobado'),
        ],
        default='enrolled'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'subject_enrollments'
        verbose_name = 'Subject Enrollment'
        verbose_name_plural = 'Subject Enrollments'
        unique_together = [['student', 'subject_group']]
        ordering = ['-enrollment_date']

    def __str__(self):
        return f"{self.student.user.get_full_name()} - {self.subject_group.subject.name}"

    def clean(self):
        """Validate enrollment prerequisites and capacity"""
        # Check if group has capacity
        if not self.subject_group.has_capacity():
            raise ValidationError("El grupo ha alcanzado su capacidad máxima.")

        # Check if enrollment period is active
        if not self.subject_group.academic_period.is_active:
            raise ValidationError("El periodo académico no está activo para inscripciones.")

        # Check enrollment dates
        now = timezone.now().date()
        if now < self.subject_group.academic_period.enrollment_start:
            raise ValidationError("El periodo de inscripción aún no ha comenzado.")
        if now > self.subject_group.academic_period.enrollment_end:
            raise ValidationError("El periodo de inscripción ha finalizado.")

        # Check prerequisites
        missing_prerequisites = self.check_prerequisites()
        if missing_prerequisites:
            prereq_names = [prereq['name'] for prereq in missing_prerequisites]
            raise ValidationError(
                f"No cumples con los prerequisitos: {', '.join(prereq_names)}"
            )

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)

        # Update group enrollment count if new enrollment
        if is_new and self.status == 'enrolled':
            self.subject_group.current_enrollment += 1
            self.subject_group.save()

    def check_schedule_conflicts(self):
        """Check if there are schedule conflicts with other enrolled subjects"""
        from schedules.models import Schedule

        # Get all schedules for this subject group
        new_schedules = Schedule.objects.filter(
            subject_group=self.subject_group,
            is_active=True
        ).select_related('time_slot')

        # Get all schedules for student's enrolled subjects
        student_enrollments = SubjectEnrollment.objects.filter(
            student=self.student,
            status='enrolled',
            subject_group__academic_period=self.subject_group.academic_period
        ).exclude(pk=self.pk)

        existing_schedules = Schedule.objects.filter(
            subject_group__in=[e.subject_group for e in student_enrollments],
            is_active=True
        ).select_related('time_slot')

        conflicts = []
        for new_schedule in new_schedules:
            for existing_schedule in existing_schedules:
                if self._schedules_overlap(new_schedule, existing_schedule):
                    conflicts.append({
                        'subject': existing_schedule.subject_group.subject.name,
                        'time': str(existing_schedule.time_slot)
                    })

        return conflicts

    def _schedules_overlap(self, schedule1, schedule2):
        """Check if two schedules overlap"""
        if schedule1.time_slot.day_of_week != schedule2.time_slot.day_of_week:
            return False

        start1 = schedule1.time_slot.start_time
        end1 = schedule1.time_slot.end_time
        start2 = schedule2.time_slot.start_time
        end2 = schedule2.time_slot.end_time

        return (start1 < end2 and end1 > start2)

    def check_prerequisites(self):
        """Check if student has completed all prerequisites for this subject"""
        from academic.models import StudyPlanSubject
        from grades.models import FinalGrade

        # Get the study plan subject that includes prerequisites
        study_plan_subject = StudyPlanSubject.objects.filter(
            study_plan=self.career_enrollment.study_plan,
            subject=self.subject_group.subject
        ).first()

        if not study_plan_subject:
            return []

        # Get all prerequisites for this subject
        prerequisites = study_plan_subject.prerequisites.all()

        if not prerequisites.exists():
            return []

        missing_prerequisites = []

        for prerequisite in prerequisites:
            # Check if student has passed this prerequisite
            passed = FinalGrade.objects.filter(
                subject_enrollment__student=self.student,
                subject_enrollment__subject_group__subject=prerequisite,
                status='passed',
                is_published=True
            ).exists()

            if not passed:
                missing_prerequisites.append({
                    'code': prerequisite.code,
                    'name': prerequisite.name
                })

        return missing_prerequisites


class WaitingList(models.Model):
    """
    Model for subject waiting lists
    """
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='waiting_lists')
    subject_group = models.ForeignKey(SubjectGroup, on_delete=models.CASCADE, related_name='waiting_list')
    position = models.IntegerField(validators=[MinValueValidator(1)])
    status = models.CharField(
        max_length=20,
        choices=[
            ('waiting', 'En Espera'),
            ('enrolled', 'Inscrito'),
            ('expired', 'Expirado'),
            ('cancelled', 'Cancelado'),
        ],
        default='waiting'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'waiting_lists'
        verbose_name = 'Waiting List'
        verbose_name_plural = 'Waiting Lists'
        unique_together = [['student', 'subject_group']]
        ordering = ['subject_group', 'position']

    def __str__(self):
        return f"{self.student.user.get_full_name()} - {self.subject_group.subject.name} (Pos: {self.position})"
