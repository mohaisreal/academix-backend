from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator

class User(AbstractUser):
    """
    Extended base user model from AbstractUser
    """
    ROLE_CHOICES = [
        ('student', 'Estudiante'),
        ('teacher', 'Profesor'),
        ('admin', 'Administrador'),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    profile_image = models.ImageField(upload_to='profiles/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return f"{self.get_full_name()} ({self.get_role_display()})"


class Student(models.Model):
    """
    Extended profile for students
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
    student_id = models.CharField(max_length=20, unique=True)
    enrollment_date = models.DateField(auto_now_add=True)
    current_year = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text='Año actual de la carrera del estudiante (1-10)'
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ('active', 'Activo'),
            ('inactive', 'Inactivo'),
            ('graduated', 'Graduado'),
            ('suspended', 'Suspendido'),
        ],
        default='active'
    )

    class Meta:
        db_table = 'students'
        verbose_name = 'Student'
        verbose_name_plural = 'Students'

    def __str__(self):
        return f"{self.student_id} - {self.user.get_full_name()}"

    def get_academic_record(self):
        """Get complete academic record for the student"""
        from enrollment.models import SubjectEnrollment
        from grades.models import FinalGrade
        from django.db.models import Avg, Sum

        enrollments = SubjectEnrollment.objects.filter(
            student=self,
            status__in=['completed', 'failed']
        ).select_related(
            'subject_group__subject',
            'subject_group__academic_period'
        ).prefetch_related('final_grade')

        # Calculate statistics
        total_subjects = enrollments.count()
        passed_subjects = enrollments.filter(
            final_grade__status='passed'
        ).count()

        final_grades = FinalGrade.objects.filter(
            subject_enrollment__student=self,
            is_published=True,
            final_score__isnull=False
        )

        avg_grade = final_grades.aggregate(
            average=Avg('final_score')
        )['average']

        total_credits = enrollments.filter(
            final_grade__status='passed'
        ).aggregate(
            total=Sum('subject_group__subject__credits')
        )['total'] or 0

        return {
            'total_subjects': total_subjects,
            'passed_subjects': passed_subjects,
            'failed_subjects': total_subjects - passed_subjects,
            'average_grade': round(avg_grade, 2) if avg_grade else None,
            'total_credits': total_credits,
            'enrollments': enrollments,
            'completion_rate': round((passed_subjects / total_subjects * 100), 2) if total_subjects > 0 else 0
        }

    def get_current_subjects(self):
        """Get currently enrolled subjects"""
        from enrollment.models import SubjectEnrollment

        return SubjectEnrollment.objects.filter(
            student=self,
            status='enrolled'
        ).select_related(
            'subject_group__subject',
            'subject_group__academic_period'
        )


class Teacher(models.Model):
    """
    Extended profile for teachers
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='teacher_profile')
    employee_id = models.CharField(max_length=20, unique=True)
    department = models.CharField(max_length=100, blank=True, null=True)
    specialization = models.CharField(max_length=200, blank=True, null=True)
    hire_date = models.DateField()
    status = models.CharField(
        max_length=20,
        choices=[
            ('active', 'Activo'),
            ('inactive', 'Inactivo'),
            ('on_leave', 'De Permiso'),
        ],
        default='active'
    )

    class Meta:
        db_table = 'teachers'
        verbose_name = 'Teacher'
        verbose_name_plural = 'Teachers'

    def __str__(self):
        return f"{self.employee_id} - {self.user.get_full_name()}"

    def get_current_schedule(self, academic_period=None):
        """Get teacher's schedule for a specific academic period"""
        from schedules.models import Schedule

        schedules = Schedule.objects.filter(
            teacher=self,
            is_active=True
        ).select_related(
            'subject_group__subject',
            'subject_group__academic_period',
            'classroom',
            'time_slot'
        ).order_by('time_slot__day_of_week', 'time_slot__start_time')

        if academic_period:
            schedules = schedules.filter(subject_group__academic_period=academic_period)

        return schedules

    def get_assigned_subjects(self, academic_period=None):
        """Get all subjects assigned to this teacher"""
        from schedules.models import TeacherAssignment

        assignments = TeacherAssignment.objects.filter(
            teacher=self,
            status='active'
        ).select_related(
            'subject_group__subject',
            'subject_group__academic_period'
        )

        if academic_period:
            assignments = assignments.filter(subject_group__academic_period=academic_period)

        return assignments

    def get_student_list(self, subject_group):
        """Get list of students enrolled in a specific subject group"""
        from enrollment.models import SubjectEnrollment

        return SubjectEnrollment.objects.filter(
            subject_group=subject_group,
            status='enrolled'
        ).select_related('student__user').order_by('student__student_id')

    def get_all_qualified_subjects(self):
        """
        Get all subjects this teacher is qualified to teach.
        Combines individual subject qualifications and subjects from qualified careers.
        Returns a QuerySet of Subject objects.
        """
        from academic.models import Subject
        from django.db.models import Q

        # Get IDs of individually qualified subjects
        individual_subject_ids = list(self.qualified_subjects.values_list('subject_id', flat=True))

        # Get IDs of careers this teacher is qualified for
        qualified_career_ids = list(self.qualified_careers.values_list('career_id', flat=True))

        # Build query
        query = Q()

        if individual_subject_ids:
            query |= Q(id__in=individual_subject_ids)

        if qualified_career_ids:
            query |= Q(study_plans__study_plan__career__id__in=qualified_career_ids)

        # Return empty queryset if no qualifications
        if not query:
            return Subject.objects.none()

        # Return combined queryset with distinct to avoid duplicates
        return Subject.objects.filter(query).distinct()

    def can_teach_subject(self, subject):
        """
        Check if this teacher is qualified to teach a specific subject.
        Returns True if the subject is in their individual qualifications or
        part of a career they're qualified for.
        """
        # Check individual qualifications
        if self.qualified_subjects.filter(subject=subject).exists():
            return True

        # Check career qualifications
        qualified_career_ids = self.qualified_careers.values_list('career_id', flat=True)
        # Check if the subject is part of any qualified career's study plan
        # subject.study_plans gives StudyPlanSubject objects
        # Then we access study_plan.career
        if subject.study_plans.filter(study_plan__career_id__in=qualified_career_ids).exists():
            return True

        return False

    def get_qualified_careers_list(self):
        """
        Get list of careers this teacher is qualified for.
        Returns a QuerySet of Career objects.
        """
        from academic.models import Career
        return Career.objects.filter(
            id__in=self.qualified_careers.values_list('career_id', flat=True)
        )


class TeacherQualifiedSubject(models.Model):
    """
    Represents an individual subject that a teacher is qualified to teach.
    This allows fine-grained control over teacher subject assignments.
    """
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='qualified_subjects')
    subject = models.ForeignKey('academic.Subject', on_delete=models.CASCADE)
    qualification_date = models.DateField(auto_now_add=True)
    notes = models.TextField(blank=True, help_text='Certifications, specialization notes, etc.')

    class Meta:
        db_table = 'teacher_qualified_subjects'
        verbose_name = 'Teacher Qualified Subject'
        verbose_name_plural = 'Teacher Qualified Subjects'
        unique_together = ['teacher', 'subject']

    def __str__(self):
        return f"{self.teacher.user.get_full_name()} - {self.subject.name}"


class TeacherQualifiedCareer(models.Model):
    """
    Represents a career that a teacher is qualified to teach all subjects for.
    This provides a quick way to qualify a teacher for all subjects in a career.
    """
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='qualified_careers')
    career = models.ForeignKey('academic.Career', on_delete=models.CASCADE)
    qualification_date = models.DateField(auto_now_add=True)
    notes = models.TextField(blank=True, help_text='Certifications, specialization notes, etc.')

    class Meta:
        db_table = 'teacher_qualified_careers'
        verbose_name = 'Teacher Qualified Career'
        verbose_name_plural = 'Teacher Qualified Careers'
        unique_together = ['teacher', 'career']

    def __str__(self):
        return f"{self.teacher.user.get_full_name()} - {self.career.name}"
